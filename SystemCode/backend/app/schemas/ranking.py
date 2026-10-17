from pydantic import BaseModel, Field

from app.schemas.common import EmploymentType, Location


class OverallScore(BaseModel):
    calculable: bool
    active_core_weight: float = Field(..., ge=0, le=100)
    effective_weights: dict[str, float] = Field(default_factory=dict)
    normalized_contributions: dict[str, float] = Field(default_factory=dict)
    core_score: float = Field(..., ge=0, le=100)
    preferred_bonus: float = Field(..., ge=0, le=5)
    professional_score: float = Field(..., ge=0, le=100)
    intent_fit: float | None = Field(default=None, ge=0, le=100)
    final_score: float = Field(..., ge=0, le=100)


class RankedJob(BaseModel):
    rank: int = Field(..., ge=1)
    job_id: int
    company: str
    title: str
    location: Location | None = None
    employment_type: EmploymentType = "not_stated"
    professional_score: float = Field(..., ge=0, le=100)
    intent_fit: float | None = Field(default=None, ge=0, le=100)
    final_score: float = Field(..., ge=0, le=100)


class RankingResponse(BaseModel):
    # passed_count 还会排除职责缺失、无法可靠评分的岗位。
    total_jobs: int
    passed_count: int
    returned_count: int
    rejected_by_rule: dict[str, int] = Field(default_factory=dict)
    # 只返回通过硬约束且具备职责数据的前 30 个岗位。
    results: list[RankedJob] = Field(default_factory=list)
