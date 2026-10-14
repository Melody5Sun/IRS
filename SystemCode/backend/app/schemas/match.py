from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ConstraintStatus
from app.schemas.job import JobRequirementDocument
from app.schemas.profile import TARGET_ROLES
from app.schemas.resume import ResumeDocument


class ConstraintCheck(BaseModel):
    name: str
    status: ConstraintStatus
    reason: str


class SkillMatch(BaseModel):
    name: str
    source: str
    evidence: str | None = None


class MatchResult(BaseModel):
    resume_id: str | None = None
    job_id: int
    score: float = Field(..., ge=0, le=1)
    eligible: bool
    constraint_checks: list[ConstraintCheck] = Field(default_factory=list)
    matched_required_skills: list[SkillMatch] = Field(default_factory=list)
    matched_preferred_skills: list[SkillMatch] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)


class SkillScoreRequest(BaseModel):
    candidate: ResumeDocument
    job: JobRequirementDocument


class DirectSkillMatch(BaseModel):
    jd_skill: str
    candidate_skill: str


class GraphSkillMatch(BaseModel):
    jd_skill: str
    candidate_skill: str
    relation: str
    relation_score: float = Field(..., ge=0, le=1)
    path: list[str] = Field(default_factory=list)


class SkillScoreResponse(BaseModel):
    job_id: int | None = None
    required_skills_calculable: bool
    preferred_skills_available: bool
    required_direct_coverage: float = Field(..., ge=0, le=100)
    required_direct_points: float = Field(..., ge=0, le=20)
    required_graph_coverage: float = Field(..., ge=0, le=100)
    required_graph_points: float = Field(..., ge=0, le=20)
    preferred_direct_coverage: float = Field(..., ge=0, le=100)
    preferred_graph_coverage: float = Field(..., ge=0, le=100)
    preferred_skill_coverage: float = Field(..., ge=0, le=100)
    preferred_bonus: float = Field(..., ge=0, le=5)
    partial_score: float = Field(..., ge=0, le=45)
    direct_required_matches: list[DirectSkillMatch] = Field(default_factory=list)
    graph_required_matches: list[GraphSkillMatch] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    direct_preferred_matches: list[DirectSkillMatch] = Field(default_factory=list)
    graph_preferred_matches: list[GraphSkillMatch] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)


class ResponsibilityScoreRequest(BaseModel):
    candidate: ResumeDocument
    job: JobRequirementDocument


class ResponsibilityEvidenceMatch(BaseModel):
    responsibility: str
    evidence_type: Literal["experience", "project", "research"] | None = None
    evidence_index: int | None = Field(default=None, ge=0)
    evidence_title: str | None = None
    evidence_text: str | None = None
    similarity: float = Field(..., ge=-1, le=1)
    coverage: float = Field(..., ge=0, le=100)
    status: Literal["matched", "partial", "missing"]


class ResponsibilityScoreResponse(BaseModel):
    job_id: int | None = None
    responsibilities_calculable: bool
    resume_evidence_available: bool
    responsibility_count: int = Field(..., ge=0)
    evidence_count: int = Field(..., ge=0)
    responsibility_coverage: float = Field(..., ge=0, le=100)
    responsibility_points: float = Field(..., ge=0, le=60)
    matches: list[ResponsibilityEvidenceMatch] = Field(default_factory=list)
    unmatched_responsibilities: list[str] = Field(default_factory=list)


class CareerIntentScoreRequest(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    job: JobRequirementDocument

    @field_validator("target_roles")
    @classmethod
    def validate_target_roles(cls, value: list[str]) -> list[str]:
        valid_roles = frozenset(TARGET_ROLES)
        invalid = [role for role in value if role not in valid_roles]
        if invalid:
            raise ValueError(f"target_roles must be chosen from TARGET_ROLES: {invalid}")
        return list(dict.fromkeys(value))


class StandardRoleSimilarity(BaseModel):
    role: str
    similarity: float = Field(..., ge=-1, le=1)


class CareerIntentScoreResponse(BaseModel):
    job_id: int | None = None
    intent_calculable: bool
    best_target_role: str | None = None
    intent_similarity: float = Field(..., ge=-1, le=1)
    intent_coverage: float = Field(..., ge=0, le=100)
    career_intent_points: float = Field(..., ge=0, le=10)
    target_role_matches: list[StandardRoleSimilarity] = Field(default_factory=list)
    top_standard_roles: list[StandardRoleSimilarity] = Field(default_factory=list)
