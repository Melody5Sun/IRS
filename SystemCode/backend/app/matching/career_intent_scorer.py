from __future__ import annotations

import hashlib
import re
from pathlib import Path
from threading import Lock

import numpy as np

from app.knowledge.role_taxonomy import RoleTaxonomy
from app.matching.embedding_provider import EmbeddingProvider
from app.schemas.job import JobRequirementDocument
from app.schemas.match import CareerIntentScoreResponse, StandardRoleSimilarity


class CareerIntentScorer:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        taxonomy_path: Path,
        model_name: str,
        similarity_floor: float = 0.40,
        similarity_full: float = 0.85,
    ) -> None:
        if not -1 <= similarity_floor < similarity_full <= 1:
            raise ValueError("similarity thresholds must satisfy -1 <= floor < full <= 1")
        self.embedding_provider = embedding_provider
        self.taxonomy = RoleTaxonomy.load(taxonomy_path)
        self.model_name = model_name
        self.similarity_floor = similarity_floor
        self.similarity_full = similarity_full
        self._role_embeddings: np.ndarray | None = None
        self._load_lock = Lock()

    def score(
        self,
        target_roles: list[str],
        job: JobRequirementDocument,
    ) -> CareerIntentScoreResponse:
        job_text = self._job_text(job)
        if not target_roles or not job_text:
            return CareerIntentScoreResponse(
                job_id=job.job_id,
                intent_calculable=False,
                intent_similarity=0,
                intent_coverage=0,
                career_intent_points=0,
            )

        role_embeddings = self._get_role_embeddings()
        job_embeddings = self._normalized_array(self.embedding_provider.encode([job_text]))
        if job_embeddings.shape[0] != 1 or job_embeddings.shape[1] != role_embeddings.shape[1]:
            raise ValueError("job and role embeddings have inconsistent dimensions")

        similarities = role_embeddings @ job_embeddings[0]
        similarity_by_role = self._similarity_by_role(similarities)
        target_matches = sorted(
            (
                StandardRoleSimilarity(
                    role=role,
                    similarity=self._round(similarity_by_role[role], 4),
                )
                for role in target_roles
            ),
            key=lambda item: item.similarity,
            reverse=True,
        )
        return self._response(
            job_id=job.job_id,
            target_matches=target_matches,
            top_standard_roles=self._top_matches(similarities, top_k=3),
        )

    def classify(
        self, job: JobRequirementDocument, top_k: int = 3
    ) -> list[StandardRoleSimilarity]:
        job_text = self._job_text(job)
        if not job_text:
            return []
        role_embeddings = self._get_role_embeddings()
        job_embeddings = self._normalized_array(self.embedding_provider.encode([job_text]))
        if job_embeddings.shape[0] != 1 or job_embeddings.shape[1] != role_embeddings.shape[1]:
            raise ValueError("job and role embeddings have inconsistent dimensions")
        return self._top_matches(role_embeddings @ job_embeddings[0], top_k=top_k)

    def score_from_role_matches(
        self,
        target_roles: list[str],
        job_id: int | None,
        top_standard_roles: list[StandardRoleSimilarity],
    ) -> CareerIntentScoreResponse:
        if not target_roles or not top_standard_roles:
            return CareerIntentScoreResponse(
                job_id=job_id,
                intent_calculable=False,
                intent_similarity=0,
                intent_coverage=0,
                career_intent_points=0,
                top_standard_roles=top_standard_roles,
            )
        similarity_by_role = {
            match.role: match.similarity for match in top_standard_roles
        }
        target_matches = sorted(
            (
                StandardRoleSimilarity(
                    role=role,
                    similarity=similarity_by_role.get(role, 0.0),
                )
                for role in target_roles
            ),
            key=lambda item: item.similarity,
            reverse=True,
        )
        return self._response(
            job_id=job_id,
            target_matches=target_matches,
            top_standard_roles=top_standard_roles,
        )

    def input_hash(self, job: JobRequirementDocument) -> str:
        return hashlib.sha256(self._job_text(job).encode("utf-8")).hexdigest()

    def _get_role_embeddings(self) -> np.ndarray:
        if self._role_embeddings is not None:
            return self._role_embeddings
        with self._load_lock:
            if self._role_embeddings is None:
                self._role_embeddings = self._build_embeddings()
        return self._role_embeddings

    def _build_embeddings(self) -> np.ndarray:
        texts = [profile.embedding_text() for profile in self.taxonomy.profiles]
        embeddings = self._normalized_array(self.embedding_provider.encode(texts))
        if embeddings.shape[0] != len(self.taxonomy.profiles):
            raise ValueError("embedding provider returned an unexpected role count")
        return embeddings

    def _top_matches(self, similarities: np.ndarray, top_k: int) -> list[StandardRoleSimilarity]:
        top_indices = np.argsort(similarities)[::-1][:top_k]
        return [
            StandardRoleSimilarity(
                role=self.taxonomy.profiles[int(index)].role,
                similarity=self._round(float(similarities[index]), 4),
            )
            for index in top_indices
        ]

    def _similarity_by_role(self, similarities: np.ndarray) -> dict[str, float]:
        return {
            profile.role: float(similarities[index])
            for index, profile in enumerate(self.taxonomy.profiles)
        }

    def _response(
        self,
        *,
        job_id: int | None,
        target_matches: list[StandardRoleSimilarity],
        top_standard_roles: list[StandardRoleSimilarity],
    ) -> CareerIntentScoreResponse:
        best = target_matches[0]
        coverage = self._coverage(best.similarity)
        return CareerIntentScoreResponse(
            job_id=job_id,
            intent_calculable=True,
            best_target_role=best.role,
            intent_similarity=best.similarity,
            intent_coverage=self._round(coverage),
            career_intent_points=self._round(0.10 * coverage),
            target_role_matches=target_matches,
            top_standard_roles=top_standard_roles,
        )

    def _coverage(self, similarity: float) -> float:
        normalized = (similarity - self.similarity_floor) / (
            self.similarity_full - self.similarity_floor
        )
        return 100 * min(1.0, max(0.0, normalized))

    @staticmethod
    def _job_text(job: JobRequirementDocument) -> str:
        sections: list[str] = []
        if title := CareerIntentScorer._clean(job.title):
            sections.append(f"Role: {title}")
        if summary := CareerIntentScorer._clean(job.summary):
            sections.append(f"Summary: {summary}")
        responsibilities = CareerIntentScorer._clean_items(job.responsibilities)
        if responsibilities:
            sections.append(f"Responsibilities: {'; '.join(responsibilities)}")
        required = CareerIntentScorer._clean_items(job.required_skills)
        if required:
            sections.append(f"Required skills: {', '.join(required)}")
        preferred = CareerIntentScorer._clean_items(job.preferred_skills)
        if preferred:
            sections.append(f"Preferred skills: {', '.join(preferred)}")
        return "\n".join(sections)

    @staticmethod
    def _clean_items(values: list[str]) -> list[str]:
        return [clean for value in values if (clean := CareerIntentScorer._clean(value))]

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _normalized_array(values) -> np.ndarray:
        array = np.asarray(values, dtype=np.float32)
        if array.ndim != 2 or not array.size or not array.shape[1]:
            raise ValueError("embedding provider returned empty or invalid vectors")
        norms = np.linalg.norm(array, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise ValueError("embedding provider returned a zero vector")
        return array / norms

    @staticmethod
    def _round(value: float, digits: int = 2) -> float:
        return round(value + 1e-12, digits)
