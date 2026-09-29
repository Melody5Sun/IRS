from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import (
    CandidateType,
    Degree,
    EmploymentType,
    Location,
    RemotePolicy,
)
from app.schemas.profile import TARGET_INDUSTRIES


class JobAnalysisRequest(BaseModel):
    job_id: str
    title: str
    company: str
    description: str = Field(..., min_length=1)
    location: str | None = None
    degree_required: str | None = None


class JobAnalysis(BaseModel):
    job_id: str
    title: str
    company: str
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    summary: str


class JobPosting(BaseModel):
    id: int | None = None
    source: str
    company: str
    external_id: str
    title: str
    location: str | None = None
    description: str
    url: str
    employment_type: str | None = None
    collected_at: datetime
    last_seen_at: datetime
    content_hash: str
    status: Literal["active", "expired", "inactive"] = "active"
    raw_json: dict = Field(default_factory=dict)


class JobListResponse(BaseModel):
    jobs: list[JobPosting]


class CompanySource(BaseModel):
    name: str
    company: str
    provider: str
    identifier: str
    enabled: bool = True
    priority: int = 100


class CompanySourceResponse(BaseModel):
    sources: list[CompanySource]


class JobSyncSourceResult(BaseModel):
    source: str
    company: str
    status: Literal["ok", "failed", "skipped"]
    fetched_count: int
    changed_count: int
    message: str | None = None


class JobSyncResponse(BaseModel):
    fetched_count: int
    changed_count: int
    expired_count: int
    sources: list[JobSyncSourceResult]


class JobRequirementDocument(BaseModel):
    job_id: int | None = None
    source_job_id: str | None = None
    company: str
    title: str
    industry: str = "Software & IT Services"
    summary: str = ""
    employment_type: EmploymentType = "not_stated"
    candidate_type: CandidateType = "not_stated"
    location: Location | None = None
    remote_policy: RemotePolicy = "not_stated"
    degree_required: Degree = "not_stated"
    major_required: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    source_evidence: list[str] = Field(default_factory=list)
    @field_validator("industry")
    @classmethod
    def validate_industry(cls, value: str) -> str:
        if value not in TARGET_INDUSTRIES:
            raise ValueError("industry must be chosen from TARGET_INDUSTRIES")
        return value


class JobMatchFeatures(BaseModel):
    job_id: int
    normalized_skill_set: list[str] = Field(default_factory=list)
    constraint_flags: dict[str, str] = Field(default_factory=dict)
    kg_expanded_skills: list[str] = Field(default_factory=list)
    semantic_embedding_ref: str | None = None
    updated_at: datetime
