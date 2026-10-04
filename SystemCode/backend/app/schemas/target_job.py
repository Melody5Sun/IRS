from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# 申请阶段，中文标签由前端映射；not_applied 以外的阶段都表示已提交申请
ApplicationStage = Literal[
    "not_applied",
    "submitted",
    "written_test",
    "interview_1",
    "interview_2",
    "interview_3",
    "hr_interview",
    "manager_interview",
    "offer",
    "rejected",
]
# none = 当前画像这份简历还没有保存该岗位的改写稿；stale = 保存后画像又改过
RewriteStatus = Literal["none", "saved", "stale"]


class TargetJobCreate(BaseModel):
    job_id: int
    # 排序接口给出的匹配度，存为快照
    match_score: float | None = None


class TargetJobUpdate(BaseModel):
    """只改传了的字段。"""

    stage: ApplicationStage | None = None
    stage_note: str | None = None
    # true 记为当前时间完成，false 清除
    interview_done: bool | None = None


class TargetJobRecord(BaseModel):
    """target_jobs 一行加上岗位基本信息。"""

    job_id: int
    title: str
    company: str
    location: str | None = None
    url: str
    match_score: float | None = None
    stage: ApplicationStage
    stage_note: str
    interview_done_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TargetJob(TargetJobRecord):
    rewrite_status: RewriteStatus
    rewrite_updated_at: datetime | None = None
