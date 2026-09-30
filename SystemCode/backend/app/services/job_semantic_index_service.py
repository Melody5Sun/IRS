from __future__ import annotations

from app.schemas.job import JobRequirementDocument
from app.services.career_intent_match_service import CareerIntentMatchService
from app.services.responsibility_match_service import ResponsibilityMatchService


class JobSemanticIndexService:
    def __init__(
        self,
        responsibility_service: ResponsibilityMatchService | None = None,
        career_intent_service: CareerIntentMatchService | None = None,
    ) -> None:
        self.responsibility_service = (
            responsibility_service or ResponsibilityMatchService()
        )
        self.career_intent_service = career_intent_service or CareerIntentMatchService()

    def index(self, job: JobRequirementDocument) -> None:
        if job.job_id is None:
            raise ValueError("job_id is required before indexing JD semantics")
        self.responsibility_service.ensure_job_embeddings(job)
        self.career_intent_service.ensure_role_matches(job)
