import hashlib
from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from openai import APIError
from pdfminer.high_level import extract_text

from app.repositories.job_repository import JobRepository
from app.repositories.job_semantic_repository import JobSemanticRepository
from app.repositories.resume_history_repository import ResumeRewriteRepository
from app.resume.llm_resume_parser import ResumeParsingError
from app.resume.resume_rewriter import ResumeRewriteError, ResumeRewriter
from app.schemas.profile import UserProfile
from app.schemas.resume import ResumeDocument, ResumeHistoryEntry, ResumeUpload
from app.schemas.resume_rewrite import ResumeRewriteRequest, ResumeRewriteResult, SavedResumeRewrite
from app.services.profile_service import profile_service
from app.services.resume_service import ResumeService

router = APIRouter()
resume_service = ResumeService()
job_repository = JobRepository()
semantic_repository = JobSemanticRepository()
rewrite_repository = ResumeRewriteRepository()
resume_rewriter = ResumeRewriter()


@router.post("/parse-pdf", response_model=ResumeUpload)
def parse_resume_pdf(file: UploadFile = File(...)) -> ResumeUpload:
    if file.content_type not in ("application/pdf", "application/octet-stream") and not (
        file.filename or ""
    ).lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持上传 PDF 文件")

    text = extract_text(BytesIO(file.file.read())).strip()
    if not text:
        raise HTTPException(
            status_code=422, detail="无法从 PDF 中提取文本，可能是扫描件图片版 PDF"
        )

    try:
        parsed = resume_service.parse_text(text)
    except (ResumeParsingError, APIError) as error:
        # LLM 输出两次都不合法，或 LLM 服务本身出错（限流、503 过载等），与改写接口一致返回 502
        raise HTTPException(status_code=502, detail=f"LLM 简历解析失败：{error}") from error
    # 只存进上传记录，不动画像：解析结果往往不完整，要用户补全后通过 PUT /profile 保存
    history_id = profile_service.resume_history.add(parsed, file.filename)
    return profile_service.resume_history.get(history_id)


@router.get("/history", response_model=list[ResumeHistoryEntry])
def list_resume_history() -> list[ResumeHistoryEntry]:
    return profile_service.resume_history.list()


@router.get("/history/{history_id}", response_model=ResumeUpload)
def get_resume_history(history_id: int) -> ResumeUpload:
    """返回某条上传记录的完整简历，不改画像；要换成这份简历，补全后通过 PUT /profile 保存。"""
    upload = profile_service.resume_history.get(history_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="未找到该历史版本")
    return upload


@router.post("/rewrite", response_model=ResumeRewriteResult)
def rewrite_resume(request: ResumeRewriteRequest) -> ResumeRewriteResult:
    """按用户选的岗位改写画像里的简历：返回每块的原稿/改写稿/理由/待补充事项和待确认的删除建议，不改画像。"""
    profile = _saved_profile()
    _ensure_job_exists(request.job_id)
    job = semantic_repository.get_analyzed_job(request.job_id)
    if job is None:
        raise HTTPException(status_code=409, detail="该岗位还没有结构化分析结果，无法改写")
    try:
        # 只用画像里的简历，求职约束不参与改写
        return resume_rewriter.rewrite(
            profile.resume, job, semantic_repository.load_role_categories(request.job_id)
        )
    except (ResumeRewriteError, APIError) as error:
        # LLM 输出两次都不合法，或 LLM 服务本身出错（限流、503 过载等）
        raise HTTPException(status_code=502, detail=f"LLM 改写失败：{error}") from error


@router.put("/rewrites/{job_id}", response_model=SavedResumeRewrite)
def save_resume_rewrite(job_id: int, resume: ResumeDocument) -> SavedResumeRewrite:
    """保存用户确认删除、回填占位后的改写稿，按（当前画像的上传记录, 岗位）覆盖；不再跑改写检查，回填的是用户的真实数据。"""
    profile = _saved_profile()
    _ensure_job_exists(job_id)
    # ponytail: 哈希取的是 PUT 时的画像，若在 POST 改写和 PUT 保存之间改了画像会被误判为不过时；
    # 需要时让 POST 返回 source_hash、PUT 时带回来
    return rewrite_repository.save(profile.resume_upload_id, job_id, resume, _resume_hash(profile.resume))


@router.get("/rewrites/{job_id}", response_model=SavedResumeRewrite)
def get_resume_rewrite(job_id: int) -> SavedResumeRewrite:
    """读取当前画像这份简历针对该岗位保存的改写稿；stale=true 表示画像在保存之后又改过。"""
    profile = _saved_profile()
    saved = rewrite_repository.get(profile.resume_upload_id, job_id, _resume_hash(profile.resume))
    if saved is None:
        raise HTTPException(status_code=404, detail="这份简历还没有保存该岗位的改写稿")
    return saved


def _saved_profile() -> UserProfile:
    profile = profile_service.get()
    if profile is None or profile.resume_upload_id is None:
        raise HTTPException(status_code=409, detail="请先上传简历并补全保存画像")
    return profile


def _ensure_job_exists(job_id: int) -> None:
    if job_repository.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail=f"未找到岗位 {job_id}")


def _resume_hash(resume: ResumeDocument) -> str:
    # 同一个模型的序列化结果是稳定的，不用额外规范化
    return hashlib.sha256(resume.model_dump_json().encode()).hexdigest()
