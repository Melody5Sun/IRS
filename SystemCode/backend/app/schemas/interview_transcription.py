from typing import Literal

from pydantic import BaseModel


class InterviewTranscriptionResponse(BaseModel):
    job_id: int
    question_id: int
    transcript: str
    language: Literal["en"] = "en"
    model: str
