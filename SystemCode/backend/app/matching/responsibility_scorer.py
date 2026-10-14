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

_SECTION_HEADING = re.compile(r"^(?P<heading>[^:：\n]{2,60})[:：]\s*(?P<body>.+)$")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。！？])\s+|[;；]\s+(?=[A-Z0-9])")
_MAX_SEGMENT_WORDS = 70
_MIN_TRAILING_WORDS = 8


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
            responsibility_points=self._round(0.60 * coverage),
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
            title = ResponsibilityScorer._clean(experience.title)
            for segment in ResponsibilityScorer._split_evidence_text(
                experience.description
            ):
                text = f"Experience: {title}. {segment}" if title else segment
                evidence.append(_EvidenceUnit("experience", index, title, text))

        for index, project in enumerate(candidate.projects):
            title = ResponsibilityScorer._clean(project.title)
            role = ResponsibilityScorer._clean(project.role or "")
            for segment in ResponsibilityScorer._split_evidence_text(project.summary):
                parts = [f"Project: {title}." if title else "Project."]
                if role:
                    parts.append(f"Role: {role}.")
                parts.append(segment)
                evidence.append(
                    _EvidenceUnit(
                        "project",
                        index,
                        title,
                        ResponsibilityScorer._clean(" ".join(parts)),
                    )
                )

        for index, research in enumerate(candidate.research):
            title = ResponsibilityScorer._clean(research.title)
            for segment in ResponsibilityScorer._split_evidence_text(research.summary):
                text = f"Research: {title}. {segment}" if title else segment
                evidence.append(_EvidenceUnit("research", index, title, text))

        return evidence

    @classmethod
    def _split_evidence_text(cls, value: str) -> list[str]:
        segments: list[str] = []
        for raw_line in value.splitlines():
            line = cls._clean(raw_line.lstrip("-•▪◦\t "))
            if not line:
                continue

            heading = ""
            body = line
            if match := _SECTION_HEADING.match(line):
                heading = cls._clean(match.group("heading"))
                body = cls._clean(match.group("body"))

            heading_words = len(heading.split()) + (1 if heading else 0)
            body_limit = max(20, _MAX_SEGMENT_WORDS - heading_words)
            for chunk in cls._chunk_text(body, body_limit):
                segment = f"{heading}: {chunk}" if heading else chunk
                segments.append(cls._clean(segment))

        return cls._unique_nonempty(segments)

    @classmethod
    def _chunk_text(cls, text: str, word_limit: int) -> list[str]:
        if len(text.split()) <= word_limit:
            return [text]

        sentences = [
            cls._clean(part)
            for part in _SENTENCE_BOUNDARY.split(text)
            if cls._clean(part)
        ]
        chunks: list[str] = []
        current: list[str] = []
        current_words = 0

        for sentence in sentences:
            words = sentence.split()
            if len(words) > word_limit:
                if current:
                    chunks.append(" ".join(current))
                    current = []
                    current_words = 0
                chunks.extend(cls._word_chunks(words, word_limit))
                continue

            if current and current_words + len(words) > word_limit:
                chunks.append(" ".join(current))
                current = []
                current_words = 0
            current.append(sentence)
            current_words += len(words)

        if current:
            chunks.append(" ".join(current))
        return chunks

    @staticmethod
    def _word_chunks(words: list[str], word_limit: int) -> list[str]:
        chunks = [
            words[index : index + word_limit]
            for index in range(0, len(words), word_limit)
        ]
        if (
            len(chunks) > 1
            and len(chunks[-1]) < _MIN_TRAILING_WORDS
            and len(chunks[-2]) + len(chunks[-1]) <= _MAX_SEGMENT_WORDS
        ):
            chunks[-2].extend(chunks.pop())
        return [" ".join(chunk) for chunk in chunks]

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
