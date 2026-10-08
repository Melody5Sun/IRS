from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from openai import APIError
from pdfminer.high_level import extract_text

from app.repositories.job_repository import JobRepository
from app.repositories.job_semantic_repository import JobSemanticRepository
from app.repositories.resume_history_repository import ResumeRewriteRepository
from app.repositories.target_job_repository import TargetJobRepository
from app.resume.llm_resume_parser import ResumeParsingError
from app.resume.resume_rewriter import LIST_ATTR, TEXT_FIELD, ResumeRewriteError, ResumeRewriter
from app.resume.rewrite_applier import placeholders
from app.schemas.job import JobRequirementDocument
from app.schemas.profile import UserProfile
from app.schemas.resume import ResumeDocument, ResumeHistoryEntry, ResumeUpload
from app.schemas.resume_rewrite import (
    BlockFillRequest,
    BlockFillResult,
    ResumeRewriteRequest,
    ResumeRewriteResult,
    SavedResumeRewrite,
)
from app.services.profile_service import profile_service, resume_hash
from app.services.openai_client_service import LLMNotConfiguredError
from app.services.resume_service import ResumeService

router = APIRouter()
resume_service = ResumeService()
job_repository = JobRepository()
semantic_repository = JobSemanticRepository()
rewrite_repository = ResumeRewriteRepository()
target_repository = TargetJobRepository()
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
    except LLMNotConfiguredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
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
    _ensure_target(request.job_id)
    job = _analyzed_job(request.job_id)
    try:
        # 只用画像里的简历，求职约束不参与改写
        return resume_rewriter.rewrite(
            profile.resume, job, semantic_repository.load_role_categories(request.job_id)
        )
    except LLMNotConfiguredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (ResumeRewriteError, APIError) as error:
        # LLM 输出两次都不合法，或 LLM 服务本身出错（限流、503 过载等）
        raise HTTPException(status_code=502, detail=f"LLM 改写失败：{error}") from error


@router.post("/rewrite/fill", response_model=BlockFillResult)
def fill_rewrite_block(request: BlockFillRequest) -> BlockFillResult:
    """待补充块（status=needs_input）的一轮问答：把用户的回答写进草稿、跳过的改成中性表述，回答含糊时追问。
    返回的 needs_user_input 为空表示补全完成，前端把 value 回填进改写后的简历；不落库。"""
    profile = _saved_profile()
    _ensure_job_exists(request.job_id)
    _ensure_target(request.job_id)
    job = _analyzed_job(request.job_id)
    entries = getattr(profile.resume, LIST_ATTR[request.section])
    if request.index >= len(entries):
        raise HTTPException(status_code=404, detail=f"简历里没有 {request.section}[{request.index}]")
    # 只接受这块草稿里确实待回答的问询，没有占位的块不需要补充
    unknown = {answer.placeholder for answer in request.answers} - placeholders(request.text)
    if unknown:
        raise HTTPException(status_code=422, detail=f"草稿里没有这些占位：{sorted(unknown)}")
    try:
        fill = resume_rewriter.fill_block(
            request.text, request.answers, job, getattr(entries[request.index], "technologies", [])
        )
    except LLMNotConfiguredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (ResumeRewriteError, APIError) as error:
        raise HTTPException(status_code=502, detail=f"LLM 改写失败：{error}") from error
    return BlockFillResult(
        **fill.model_dump(), section=request.section, index=request.index, field=TEXT_FIELD[request.section]
    )


@router.put("/rewrites/{job_id}", response_model=SavedResumeRewrite)
def save_resume_rewrite(job_id: int, resume: ResumeDocument) -> SavedResumeRewrite:
    """保存用户确认删除、回填占位后的改写稿，按（当前画像的上传记录, 岗位）覆盖；不再跑改写检查，回填的是用户的真实数据。"""
    profile = _saved_profile()
    _ensure_job_exists(job_id)
    _ensure_target(job_id)
    # 改写产生、还没回答或跳过的占位不能进终稿；原简历里本来就有的方括号内容不算
    unresolved = placeholders(_rewritable_text(resume)) - placeholders(_rewritable_text(profile.resume))
    if unresolved:
        raise HTTPException(
            status_code=409, detail=f"改写稿里还有待补充的占位：{sorted(unresolved)}，请先回答或跳过对应问询"
        )
    # ponytail: 哈希取的是 PUT 时的画像，若在 POST 改写和 PUT 保存之间改了画像会被误判为不过时；
    # 需要时让 POST 返回 source_hash、PUT 时带回来
    return rewrite_repository.save(profile.resume_upload_id, job_id, resume, resume_hash(profile.resume))


@router.get("/rewrites/{job_id}", response_model=SavedResumeRewrite)
def get_resume_rewrite(job_id: int) -> SavedResumeRewrite:
    """读取当前画像这份简历针对该岗位保存的改写稿；stale=true 表示画像在保存之后又改过。"""
    profile = _saved_profile()
    saved = rewrite_repository.get(profile.resume_upload_id, job_id, resume_hash(profile.resume))
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


def _analyzed_job(job_id: int) -> JobRequirementDocument:
    job = semantic_repository.get_analyzed_job(job_id)
    if job is None:
        raise HTTPException(status_code=409, detail="该岗位还没有结构化分析结果，无法改写")
    return job


def _rewritable_text(resume: ResumeDocument) -> str:
    # 会出现占位的只有经历/项目/研究的正文
    return "\n".join(
        [
            *(item.description for item in resume.experiences),
            *(item.summary for item in resume.projects),
            *(item.summary for item in resume.research),
        ]
    )


def _ensure_target(job_id: int) -> None:
    # 只有设为目标的岗位才能改写简历；移出目标时改写稿会一起删除
    if not target_repository.exists(job_id):
        raise HTTPException(status_code=409, detail="请先把该岗位设为目标岗位")
