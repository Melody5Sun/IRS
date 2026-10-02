from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import EmploymentType


EvidenceSource = Literal["skills", "experience", "project", "research", "career_intent"]
MatchType = Literal[
    "direct_skill",
    "knowledge_graph",
    "responsibility_semantic",
    "career_intent",
    "preferred_skill",
]
GapType = Literal[
    "transferable",
    "hard_gap",
    "optional_gap",
    "experience_gap",
    "intent_gap",
]
GapImportance = Literal["required", "preferred", "responsibility", "career_intent"]


class JobMatchDetailJob(BaseModel):
    job_id: int
    source: str
    company: str
    title: str
    location: str | None = None
    employment_type: EmploymentType = "not_stated"
    url: str
    description: str
    summary: str
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    collected_at: datetime


class JobMatchComponentPoints(BaseModel):
    required_skill_direct: float = Field(..., ge=0, le=40)
    responsibility: float = Field(..., ge=0, le=30)
    required_skill_graph: float = Field(..., ge=0, le=20)
    career_intent: float = Field(..., ge=0, le=10)


class JobMatchDetailScore(BaseModel):
    calculable: bool
    final_score: float = Field(..., ge=0, le=100)
    core_score: float = Field(..., ge=0, le=100)
    preferred_skill_bonus: float = Field(..., ge=0, le=5)
    active_core_weight: float = Field(..., ge=0, le=100)
    component_points: JobMatchComponentPoints
    effective_weights: dict[str, float] = Field(default_factory=dict)
    normalized_contributions: dict[str, float] = Field(default_factory=dict)


class JobMatchEvidence(BaseModel):
    requirement: str
    candidate_evidence: str
    evidence_source: EvidenceSource
    match_type: MatchType
    similarity: float | None = Field(default=None, ge=-1, le=1)
    relation: str | None = None
    path: list[str] = Field(default_factory=list)


class JobMatchRecommendation(BaseModel):
    summary: str
    highlights: list[str] = Field(default_factory=list)
    evidence: list[JobMatchEvidence] = Field(default_factory=list)


class JobMatchGap(BaseModel):
    name: str
    gap_type: GapType
    importance: GapImportance
    current_evidence: str | None = None
    reason: str
    suggestion: str


class JobMatchDetailMeta(BaseModel):
    algorithm_version: str
    generated_at: datetime


class JobMatchDetailResponse(BaseModel):
    job: JobMatchDetailJob
    match: JobMatchDetailScore
    recommendation: JobMatchRecommendation
    gaps: list[JobMatchGap] = Field(default_factory=list)
    meta: JobMatchDetailMeta
