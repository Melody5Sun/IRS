from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from pdfminer.high_level import extract_text

from app.schemas.resume import ResumeHistoryEntry, ResumeUpload
from app.services.profile_service import profile_service
from app.services.resume_service import ResumeService

router = APIRouter()
resume_service = ResumeService()


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

    parsed = resume_service.parse_text(text)
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
