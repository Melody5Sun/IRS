from app.core.config import settings
from app.matching.embedding_provider import SentenceTransformerEmbeddingProvider
from app.matching.responsibility_scorer import (
    PreparedResumeEvidence,
    ResponsibilityScorer,
)
from app.repositories.job_semantic_repository import JobSemanticRepository
from app.schemas.match import ResponsibilityScoreRequest, ResponsibilityScoreResponse


class ResponsibilityMatchService:
    def __init__(
        self,
        scorer: ResponsibilityScorer | None = None,
        repository: JobSemanticRepository | None = None,
        persist: bool | None = None,
    ) -> None:
        uses_default_scorer = scorer is None
        self.scorer = scorer or ResponsibilityScorer(
            embedding_provider=SentenceTransformerEmbeddingProvider(
                settings.responsibility_embedding_model
            ),
            similarity_floor=settings.responsibility_similarity_floor,
            similarity_full=settings.responsibility_similarity_full,
        )
        should_persist = uses_default_scorer if persist is None else persist
        self.repository = repository or (JobSemanticRepository() if should_persist else None)
        self.model_name = settings.responsibility_embedding_model

    def score(
        self,
        request: ResponsibilityScoreRequest,
        prepared_evidence: PreparedResumeEvidence | None = None,
    ) -> ResponsibilityScoreResponse:
        embeddings = self.ensure_job_embeddings(request.job)
        return self.scorer.score(
            request.candidate,
            request.job,
            responsibility_embeddings=embeddings,
            prepared_evidence=prepared_evidence,
        )

    def prepare_candidate(self, candidate) -> PreparedResumeEvidence:
        return self.scorer.prepare_candidate(candidate)

    def ensure_job_embeddings(self, job) -> list[list[float]] | None:
        responsibilities = self.scorer.responsibility_texts(job)
        if not responsibilities:
            return None
        if job.job_id is not None and self.repository is not None:
            stored = self.repository.load_responsibility_embeddings(
                job.job_id,
                responsibilities,
                self.model_name,
            )
            if stored is not None:
                return stored
        embeddings = self.scorer.encode_responsibilities(responsibilities)
        if job.job_id is not None and self.repository is not None:
            self.repository.save_responsibility_embeddings(
                job.job_id,
                responsibilities,
                embeddings,
                self.model_name,
            )
        return embeddings
