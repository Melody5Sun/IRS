from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import DifficultyLevel


class DifficultyMix(BaseModel):
    easy: int = Field(default=4, ge=0)
    medium: int = Field(default=4, ge=0)
    hard: int = Field(default=2, ge=0)

    @property
    def total(self) -> int:
        return self.easy + self.medium + self.hard


class InterviewQuestionSampleRequest(BaseModel):
    count: int = Field(default=10, ge=5, le=20)
    difficulty_mix: DifficultyMix | None = None
    exclude_question_ids: list[int] = Field(default_factory=list)
    seed: int | None = None

    @field_validator("exclude_question_ids")
    @classmethod
    def deduplicate_question_ids(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_difficulty_total(self):
        if self.difficulty_mix is not None and self.difficulty_mix.total != self.count:
            raise ValueError("difficulty_mix must add up to count")
        return self


class InterviewRoleAllocation(BaseModel):
    role: str
    similarity: float
    normalized_weight: float
    requested_quota: int
    actual_count: int


class SampledInterviewQuestion(BaseModel):
    sequence: int
    id: int
    question_type: Literal["basic_programming", "role_specific"]
    allocated_role: str
    question_text: str
    standard_answer: str
    question_text_en: str
    standard_answer_en: str
    difficulty_level: DifficultyLevel
    roles: list[str]
    source: str
    company: str | None = None


class InterviewQuestionSampleResponse(BaseModel):
    job_id: int
    job_title: str
    seed: int
    generated_at: datetime
    requested_count: int
    returned_count: int
    role_allocation: list[InterviewRoleAllocation]
    basic_question_count: int
    difficulty_distribution: DifficultyMix
    questions: list[SampledInterviewQuestion]
    warnings: list[str] = Field(default_factory=list)
