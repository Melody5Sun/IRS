from pydantic import BaseModel, Field

from app.schemas.common import EmploymentType, Location


class OverallScore(BaseModel):
    calculable: bool
    active_core_weight: float = Field(..., ge=0, le=100)
    effective_weights: dict[str, float] = Field(default_factory=dict)
    normalized_contributions: dict[str, float] = Field(default_factory=dict)
    core_score: float = Field(..., ge=0, le=100)
    preferred_bonus: float = Field(..., ge=0, le=5)
    final_score: float = Field(..., ge=0, le=100)


class RankedJob(BaseModel):
    rank: int = Field(..., ge=1)
    job_id: int
    company: str
    title: str
    location: Location | None = None
    employment_type: EmploymentType = "not_stated"
    final_score: float = Field(..., ge=0, le=100)


class RankingResponse(BaseModel):
    # 统计沿用规则筛选的口径，见 RulesScreeningResponse
    total_jobs: int
    passed_count: int
    returned_count: int
    rejected_by_rule: dict[str, int] = Field(default_factory=dict)
    # 只返回通过硬约束后的前 30 个岗位，按 final_score 降序。
    results: list[RankedJob] = Field(default_factory=list)
