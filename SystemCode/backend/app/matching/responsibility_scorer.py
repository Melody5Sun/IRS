from __future__ import annotations

import math
import re
from dataclasses import dataclass
from threading import Lock
from typing import Literal

from app.matching.embedding_provider import EmbeddingProvider
from app.schemas.job import JobRequirementDocument
from app.schemas.match import (
    ResponsibilityEvidenceMatch,
    ResponsibilityScoreResponse,
)
from app.schemas.resume import ResumeDocument


EvidenceType = Literal["experience", "project", "research"]


@dataclass(frozen=True)
class _EvidenceUnit:
    evidence_type: EvidenceType
    evidence_index: int
    title: str
    text: str


@dataclass(frozen=True)
class PreparedResumeEvidence:
    evidence: list[_EvidenceUnit]
    embeddings: list[list[float]]


class ResponsibilityScorer:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        similarity_floor: float = 0.35,
        similarity_full: float = 0.75,
        cache_size: int = 256,
    ) -> None:
        if not -1 <= similarity_floor < similarity_full <= 1:
            raise ValueError("similarity thresholds must satisfy -1 <= floor < full <= 1")
        self.embedding_provider = embedding_provider
        self.similarity_floor = similarity_floor
        self.similarity_full = similarity_full
        self.cache_size = cache_size
        self._job_embedding_cache: dict[tuple[str, ...], list[list[float]]] = {}
        self._cache_lock = Lock()

    def score(
        self,
        candidate: ResumeDocument,
        job: JobRequirementDocument,
        responsibility_embeddings: list[list[float]] | None = None,
        prepared_evidence: PreparedResumeEvidence | None = None,
    ) -> ResponsibilityScoreResponse:
        responsibilities = self.responsibility_texts(job)
        evidence = (
            prepared_evidence.evidence
            if prepared_evidence is not None
            else self._build_evidence(candidate)
        )

        if not responsibilities:
            return ResponsibilityScoreResponse(
                job_id=job.job_id,
                responsibilities_calculable=False,
                resume_evidence_available=bool(evidence),
                responsibility_count=0,
                evidence_count=len(evidence),
                responsibility_coverage=0,
                responsibility_points=0,
            )

        if not evidence:
            matches = [self._missing_match(item) for item in responsibilities]
            return ResponsibilityScoreResponse(
                job_id=job.job_id,
                responsibilities_calculable=True,
                resume_evidence_available=False,
                responsibility_count=len(responsibilities),
                evidence_count=0,
                responsibility_coverage=0,
                responsibility_points=0,
                matches=matches,
                unmatched_responsibilities=responsibilities,
            )

        responsibility_embeddings = (
            responsibility_embeddings
            if responsibility_embeddings is not None
            else self._responsibility_embeddings(responsibilities)
        )
        evidence_embeddings = (
            prepared_evidence.embeddings
            if prepared_evidence is not None
            else self.embedding_provider.encode([item.text for item in evidence])
        )
        self._validate_embeddings(responsibility_embeddings, evidence_embeddings)

        matches = [
            self._best_match(responsibility, vector, evidence, evidence_embeddings)
            for responsibility, vector in zip(
                responsibilities, responsibility_embeddings, strict=True
            )
        ]
        coverage = sum(match.coverage for match in matches) / len(matches)
        return ResponsibilityScoreResponse(
            job_id=job.job_id,
            responsibilities_calculable=True,
            resume_evidence_available=True,
            responsibility_count=len(responsibilities),
            evidence_count=len(evidence),
            responsibility_coverage=self._round(coverage),
            responsibility_points=self._round(0.30 * coverage),
            matches=matches,
            unmatched_responsibilities=[
                match.responsibility
                for match in matches
                if match.status == "missing"
            ],
        )

    def _best_match(
        self,
        responsibility: str,
        responsibility_vector: list[float],
        evidence: list[_EvidenceUnit],
        evidence_embeddings: list[list[float]],
    ) -> ResponsibilityEvidenceMatch:
        similarities = [
            self._cosine_similarity(responsibility_vector, vector)
            for vector in evidence_embeddings
        ]
        best_index = max(range(len(similarities)), key=similarities.__getitem__)
        best_similarity = similarities[best_index]
        best_evidence = evidence[best_index]
        coverage = self._coverage(best_similarity)

        if best_similarity >= self.similarity_full:
            status = "matched"
        elif best_similarity > self.similarity_floor:
            status = "partial"
        else:
            status = "missing"

        return ResponsibilityEvidenceMatch(
            responsibility=responsibility,
            evidence_type=best_evidence.evidence_type,
            evidence_index=best_evidence.evidence_index,
            evidence_title=best_evidence.title,
            evidence_text=best_evidence.text,
            similarity=self._round(best_similarity, digits=4),
            coverage=self._round(coverage),
            status=status,
        )

    def _responsibility_embeddings(
        self, responsibilities: list[str]
    ) -> list[list[float]]:
        key = tuple(responsibilities)
        with self._cache_lock:
            cached = self._job_embedding_cache.get(key)
        if cached is not None:
            return cached

        embeddings = self.embedding_provider.encode(responsibilities)
        with self._cache_lock:
            if len(self._job_embedding_cache) >= self.cache_size:
                self._job_embedding_cache.clear()
            self._job_embedding_cache[key] = embeddings
        return embeddings

    def encode_responsibilities(self, responsibilities: list[str]) -> list[list[float]]:
        return self._responsibility_embeddings(responsibilities)

    def prepare_candidate(self, candidate: ResumeDocument) -> PreparedResumeEvidence:
        evidence = self._build_evidence(candidate)
        embeddings = (
            self.embedding_provider.encode([item.text for item in evidence])
            if evidence
            else []
        )
        return PreparedResumeEvidence(evidence=evidence, embeddings=embeddings)

    @classmethod
    def responsibility_texts(cls, job: JobRequirementDocument) -> list[str]:
        return cls._unique_nonempty(job.responsibilities)

    def _coverage(self, similarity: float) -> float:
        normalized = (similarity - self.similarity_floor) / (
            self.similarity_full - self.similarity_floor
        )
        return 100 * min(1.0, max(0.0, normalized))

    @staticmethod
    def _build_evidence(candidate: ResumeDocument) -> list[_EvidenceUnit]:
        evidence: list[_EvidenceUnit] = []

        for index, experience in enumerate(candidate.experiences):
            description = ResponsibilityScorer._clean(experience.description)
            if not description:
                continue
            title = ResponsibilityScorer._clean(experience.title)
            text = f"Experience: {title}. {description}" if title else description
            evidence.append(_EvidenceUnit("experience", index, title, text))

        for index, project in enumerate(candidate.projects):
            summary = ResponsibilityScorer._clean(project.summary)
            if not summary:
                continue
            title = ResponsibilityScorer._clean(project.title)
            parts = [f"Project: {title}." if title else "Project."]
            if role := ResponsibilityScorer._clean(project.role or ""):
                parts.append(f"Role: {role}.")
            parts.append(summary)
            technologies = [
                clean
                for item in project.technologies
                if (clean := ResponsibilityScorer._clean(item))
            ]
            if technologies:
                parts.append(f"Technologies: {', '.join(technologies)}.")
            evidence.append(
                _EvidenceUnit("project", index, title, ResponsibilityScorer._clean(" ".join(parts)))
            )

        for index, research in enumerate(candidate.research):
            summary = ResponsibilityScorer._clean(research.summary)
            if not summary:
                continue
            title = ResponsibilityScorer._clean(research.title)
            text = f"Research: {title}. {summary}" if title else summary
            evidence.append(_EvidenceUnit("research", index, title, text))

        return evidence

    @staticmethod
    def _unique_nonempty(values: list[str]) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for value in values:
            clean = ResponsibilityScorer._clean(value)
            key = clean.casefold()
            if clean and key not in seen:
                seen.add(key)
                unique.append(clean)
        return unique

    @staticmethod
    def _missing_match(responsibility: str) -> ResponsibilityEvidenceMatch:
        return ResponsibilityEvidenceMatch(
            responsibility=responsibility,
            similarity=0,
            coverage=0,
            status="missing",
        )

    @staticmethod
    def _validate_embeddings(
        responsibilities: list[list[float]], evidence: list[list[float]]
    ) -> None:
        vectors = [*responsibilities, *evidence]
        if not vectors or not vectors[0]:
            raise ValueError("embedding provider returned empty vectors")
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1:
            raise ValueError("embedding provider returned inconsistent dimensions")

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        similarity = sum(a * b for a, b in zip(left, right, strict=True)) / (
            left_norm * right_norm
        )
        return min(1.0, max(-1.0, similarity))

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _round(value: float, digits: int = 2) -> float:
        return round(value + 1e-12, digits)
