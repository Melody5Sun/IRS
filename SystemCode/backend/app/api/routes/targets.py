from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response

from app.repositories.job_repository import JobRepository
from app.repositories.resume_history_repository import ResumeRewriteRepository
from app.repositories.target_job_repository import TargetJobRepository
from app.schemas.profile import UserProfile
from app.schemas.target_job import TargetJob, TargetJobCreate, TargetJobRecord, TargetJobUpdate
from app.services.profile_service import profile_service, resume_hash

router = APIRouter()
target_repository = TargetJobRepository()
rewrite_repository = ResumeRewriteRepository()
job_repository = JobRepository()
NOT_TARGET = "该岗位不在目标岗位列表中"


@router.get("", response_model=list[TargetJob])
def list_targets() -> list[TargetJob]:
    profile = profile_service.get()
    return [_with_rewrite_status(record, profile) for record in target_repository.list()]


@router.post("", response_model=TargetJob, status_code=201)
def add_target(request: TargetJobCreate) -> TargetJob:
    """设为目标岗位；已经是目标时原样返回，不重置进度。"""
    if job_repository.get_job(request.job_id) is None:
        raise HTTPException(status_code=404, detail=f"未找到岗位 {request.job_id}")
    target_repository.add(request.job_id, request.match_score)
    return _get_target(request.job_id)


@router.patch("/{job_id}", response_model=TargetJob)
def update_target(job_id: int, update: TargetJobUpdate) -> TargetJob:
    current = target_repository.get(job_id)
    if current is None:
        raise HTTPException(status_code=404, detail=NOT_TARGET)
    stage = update.stage or current.stage
    stage_note = current.stage_note if update.stage_note is None else update.stage_note.strip()
    if stage == "not_applied":
        # 还没提交申请就没有进度可写；撤回到未申请时一并清空备注
        if update.stage_note and update.stage_note.strip():
            raise HTTPException(status_code=409, detail="请先标记已提交申请，再填写申请进度")
        stage_note = ""
    interview_done_at = current.interview_done_at
    if update.interview_done is not None:
        interview_done_at = datetime.now(timezone.utc) if update.interview_done else None
    target_repository.update(job_id, stage, stage_note, interview_done_at)
    return _get_target(job_id)


@router.delete("/{job_id}", status_code=204)
def remove_target(job_id: int) -> Response:
    """移出目标岗位：申请进度和该岗位的简历改写稿一并删除，无法恢复。"""
    if not target_repository.delete(job_id):
        raise HTTPException(status_code=404, detail=NOT_TARGET)
    return Response(status_code=204)


def _get_target(job_id: int) -> TargetJob:
    record = target_repository.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=NOT_TARGET)
    return _with_rewrite_status(record, profile_service.get())


def _with_rewrite_status(record: TargetJobRecord, profile: UserProfile | None) -> TargetJob:
    # 改写稿按（当前画像的上传记录, 岗位）存，沿用改写接口的过时判断；没有画像就当没有改写稿
    # ponytail: 每个目标查一次改写稿，目标岗位只有几十个；多了再改成一条 LEFT JOIN
    saved = None
    if profile is not None and profile.resume_upload_id is not None:
        saved = rewrite_repository.get(profile.resume_upload_id, record.job_id, resume_hash(profile.resume))
    if saved is None:
        return TargetJob(**record.model_dump(), rewrite_status="none")
    return TargetJob(
        **record.model_dump(),
        rewrite_status="stale" if saved.stale else "saved",
        rewrite_updated_at=saved.updated_at,
    )
