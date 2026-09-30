from app.core.config import settings
from app.matching.career_intent_scorer import CareerIntentScorer
from app.matching.embedding_provider import SentenceTransformerEmbeddingProvider
from app.repositories.job_semantic_repository import (
    JobSemanticRepository,
    StoredRoleMatch,
)
from app.schemas.match import CareerIntentScoreRequest, CareerIntentScoreResponse
from app.schemas.match import StandardRoleSimilarity


class CareerIntentMatchService:
    def __init__(
        self,
        scorer: CareerIntentScorer | None = None,
        repository: JobSemanticRepository | None = None,
        persist: bool | None = None,
    ) -> None:
        uses_default_scorer = scorer is None
        self.scorer = scorer or CareerIntentScorer(
            embedding_provider=SentenceTransformerEmbeddingProvider(
                settings.career_intent_embedding_model
            ),
            taxonomy_path=settings.role_taxonomy_path,
            model_name=settings.career_intent_embedding_model,
            similarity_floor=settings.career_intent_similarity_floor,
            similarity_full=settings.career_intent_similarity_full,
        )
        should_persist = uses_default_scorer if persist is None else persist
        self.repository = repository or (JobSemanticRepository() if should_persist else None)
        self.algorithm_version = settings.career_intent_algorithm_version
        self.top_k = settings.career_intent_top_k

    def score(self, request: CareerIntentScoreRequest) -> CareerIntentScoreResponse:
        if request.job.job_id is None:
            return self.scorer.score(request.target_roles, request.job)
        matches = self.ensure_role_matches(request.job)
        return self.scorer.score_from_role_matches(
            request.target_roles,
            request.job.job_id,
            matches,
        )

    def ensure_role_matches(self, job) -> list[StandardRoleSimilarity]:
        if job.job_id is None:
            return self.scorer.classify(job, self.top_k)
        input_hash = self.scorer.input_hash(job)
        if self.repository is None:
            return self.scorer.classify(job, self.top_k)
        stored = self.repository.load_role_matches(
            job.job_id,
            model_name=self.scorer.model_name,
            algorithm_version=self.algorithm_version,
            input_hash=input_hash,
            taxonomy_hash=self.scorer.taxonomy.source_hash,
        )
        if stored is not None:
            return [
                StandardRoleSimilarity(role=item.role, similarity=item.similarity)
                for item in stored
            ]
        matches = self.scorer.classify(job, self.top_k)
        self.repository.save_role_matches(
            job.job_id,
            [
                StoredRoleMatch(role=item.role, similarity=item.similarity, rank=index)
                for index, item in enumerate(matches, start=1)
            ],
            model_name=self.scorer.model_name,
            algorithm_version=self.algorithm_version,
            input_hash=input_hash,
            taxonomy_hash=self.scorer.taxonomy.source_hash,
        )
        return matches
