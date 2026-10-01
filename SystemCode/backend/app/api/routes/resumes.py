from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from pdfminer.high_level import extract_text

from app.repositories.resume_history_repository import ResumeHistoryRepository
from app.schemas.profile import UserProfile
from app.schemas.resume import ResumeDocument, ResumeHistoryEntry
from app.services.profile_service import profile_service
from app.services.resume_service import ResumeService

router = APIRouter()
resume_service = ResumeService()
resume_history = ResumeHistoryRepository()


@router.post("/parse-pdf", response_model=ResumeDocument)
def parse_resume_pdf(file: UploadFile = File(...)) -> ResumeDocument:
    if file.content_type not in ("application/pdf", "application/octet-stream") and not (
        file.filename or ""
    ).lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持上传 PDF 文件")

    text = extract_text(BytesIO(file.file.read())).strip()
    if not text:
        raise HTTPException(
            status_code=422, detail="无法从 PDF 中提取文本，可能是扫描件图片版 PDF"
        )

    parsed = resume_service.parse_text(text)
    # 每次上传都留一条历史记录，供之后挑选版本套用
    resume_history.add(parsed, file.filename)
    # 解析结果先存入画像（about 合并进 notes），用户之后通过 GET /profile 读取并修改
    profile_service.save_resume(parsed)
    # response_model 是 ResumeDocument，响应里不带 about
    return parsed


@router.get("/history", response_model=list[ResumeHistoryEntry])
def list_resume_history() -> list[ResumeHistoryEntry]:
    return resume_history.list()


@router.post("/history/{history_id}/apply", response_model=UserProfile)
def apply_resume_history(history_id: int) -> UserProfile:
    """把某条历史记录套用为当前画像的简历部分，约束沿用 save_resume 的合并规则。"""
    parsed = resume_history.get(history_id)
    if parsed is None:
        raise HTTPException(status_code=404, detail="未找到该历史版本")
    profile_service.save_resume(parsed)
    assert profile_service.profile is not None
    return profile_service.profile
