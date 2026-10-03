from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from sqlalchemy import text

from app.db.postgres import get_postgres_engine
from app.schemas.job import JobRequirementDocument


@dataclass(frozen=True)
class StoredRoleMatch:
    role: str
    similarity: float
    rank: int


class JobSemanticRepository:
    """Store reusable JD semantics without persisting transient query vectors."""

    @staticmethod
    def content_hash(value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def load_responsibility_embeddings(
        self,
        job_id: int,
        responsibilities: list[str],
        model_name: str,
    ) -> list[list[float]] | None:
        expected_hashes = [self.content_hash(item) for item in responsibilities]
        with get_postgres_engine().connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT jr.embedding_content_hash, jr.embedding
                    FROM job_responsibilities jr
                    WHERE jr.job_id = :job_id
                      AND jr.embedding_model = :model_name
                      AND jr.embedding IS NOT NULL
                    ORDER BY jr.sequence_no
                    """
                ),
                {"job_id": job_id, "model_name": model_name},
            ).mappings().all()
        by_hash = {
            row["embedding_content_hash"]: self._vector_values(row["embedding"])
            for row in rows
            if row["embedding_content_hash"]
        }
        if any(item_hash not in by_hash for item_hash in expected_hashes):
            return None
        return [by_hash[item_hash] for item_hash in expected_hashes]

    def save_responsibility_embeddings(
        self,
        job_id: int,
        responsibilities: list[str],
        embeddings: list[list[float]],
        model_name: str,
    ) -> None:
        if len(responsibilities) != len(embeddings):
            raise ValueError("responsibilities and embeddings must have equal length")
        vectors_by_hash = {
            self.content_hash(item): self._vector_literal(vector)
            for item, vector in zip(responsibilities, embeddings, strict=True)
        }
        with get_postgres_engine().begin() as connection:
            self._require_analyzed_job(connection, job_id)
            rows = connection.execute(
                text(
                    """
                    SELECT id, responsibility_text
                    FROM job_responsibilities
                    WHERE job_id = :job_id
                    ORDER BY sequence_no
                    """
                ),
                {"job_id": job_id},
            ).mappings().all()
            for row in rows:
                item_hash = self.content_hash(row["responsibility_text"])
                vector = vectors_by_hash.get(item_hash)
                if vector is None:
                    continue
                connection.execute(
                    text(
                        """
                        UPDATE job_responsibilities
                        SET embedding = CAST(:embedding AS vector),
                            embedding_model = :model_name,
                            embedding_content_hash = :content_hash,
                            embedded_at = CURRENT_TIMESTAMP
                        WHERE id = :responsibility_id
                        """
                    ),
                    {
                        "embedding": vector,
                        "model_name": model_name,
                        "content_hash": item_hash,
                        "responsibility_id": row["id"],
                    },
                )

    def load_role_matches(
        self,
        job_id: int,
        *,
        model_name: str,
        algorithm_version: str,
        input_hash: str,
        taxonomy_hash: str,
    ) -> list[StoredRoleMatch] | None:
        with get_postgres_engine().connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT r.canonical_name AS role, jvr.similarity, jvr.rank
                    FROM job_roles jvr
                    JOIN roles r ON r.id = jvr.role_id
                    WHERE jvr.job_id = :job_id
                      AND jvr.model_name = :model_name
                      AND jvr.algorithm_version = :algorithm_version
                      AND jvr.input_hash = :input_hash
                      AND jvr.taxonomy_hash = :taxonomy_hash
                    ORDER BY jvr.rank
                    """
                ),
                {
                    "job_id": job_id,
                    "model_name": model_name,
                    "algorithm_version": algorithm_version,
                    "input_hash": input_hash,
                    "taxonomy_hash": taxonomy_hash,
                },
            ).mappings().all()
        if not rows:
            return None
        return [
            StoredRoleMatch(
                role=row["role"],
                similarity=float(row["similarity"]),
                rank=int(row["rank"]),
            )
            for row in rows
        ]

    def save_role_matches(
        self,
        job_id: int,
        matches: list[StoredRoleMatch],
        *,
        model_name: str,
        algorithm_version: str,
        input_hash: str,
        taxonomy_hash: str,
    ) -> None:
        with get_postgres_engine().begin() as connection:
            self._require_analyzed_job(connection, job_id)
            connection.execute(
                text(
                    """
                    DELETE FROM job_roles
                    WHERE job_id = :job_id
                      AND model_name = :model_name
                      AND algorithm_version = :algorithm_version
                    """
                ),
                {
                    "job_id": job_id,
                    "model_name": model_name,
                    "algorithm_version": algorithm_version,
                },
            )
            for match in matches:
                role_id = connection.execute(
                    text("SELECT id FROM roles WHERE canonical_name = :role"),
                    {"role": match.role},
                ).scalar_one()
                connection.execute(
                    text(
                        """
                        INSERT INTO job_roles (
                            job_id, role_id, rank, similarity,
                            model_name, algorithm_version, input_hash,
                            taxonomy_hash
                        ) VALUES (
                            :job_id, :role_id, :rank, :similarity,
                            :model_name, :algorithm_version, :input_hash,
                            :taxonomy_hash
                        )
                        """
                    ),
                    {
                        "job_id": job_id,
                        "role_id": role_id,
                        "rank": match.rank,
                        "similarity": match.similarity,
                        "model_name": model_name,
                        "algorithm_version": algorithm_version,
                        "input_hash": input_hash,
                        "taxonomy_hash": taxonomy_hash,
                    },
                )

    def list_analyzed_jobs(self, limit: int = 1000) -> list[JobRequirementDocument]:
        with get_postgres_engine().connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT jp.id AS job_id, ja.raw_analysis,
                           COALESCE(industry.name, 'Software & IT Services') AS industry
                    FROM job_postings jp
                    JOIN job_analyses ja ON ja.job_id = jp.id
                    JOIN companies c ON c.id = jp.company_id
                    LEFT JOIN industries industry ON industry.id = c.industry_id
                    ORDER BY jp.id
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings().all()
        documents: list[JobRequirementDocument] = []
        for row in rows:
            payload = row["raw_analysis"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            payload = dict(payload)
            payload["job_id"] = row["job_id"]
            payload["industry"] = row["industry"]
            documents.append(JobRequirementDocument.model_validate(payload))
        return documents

    def get_analyzed_job(self, job_id: int) -> JobRequirementDocument | None:
        with get_postgres_engine().connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT jp.id AS job_id, ja.raw_analysis,
                           COALESCE(industry.name, 'Software & IT Services') AS industry
                    FROM job_postings jp
                    JOIN job_analyses ja ON ja.job_id = jp.id
                    JOIN companies c ON c.id = jp.company_id
                    LEFT JOIN industries industry ON industry.id = c.industry_id
                    WHERE jp.id = :job_id
                    """
                ),
                {"job_id": job_id},
            ).mappings().one_or_none()
        if row is None:
            return None
        payload = row["raw_analysis"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        payload = dict(payload)
        payload["job_id"] = row["job_id"]
        payload["industry"] = row["industry"]
        return JobRequirementDocument.model_validate(payload)

    def load_role_categories(self, job_id: int) -> list[str]:
        """岗位在 job_roles 里对应的标准岗位所属的大类（去重）；还没有分类结果时为空列表。"""
        with get_postgres_engine().connect() as connection:
            return list(
                connection.execute(
                    text(
                        """
                        SELECT DISTINCT r.category
                        FROM job_roles jr
                        JOIN roles r ON r.id = jr.role_id
                        WHERE jr.job_id = :job_id AND r.category IS NOT NULL
                        ORDER BY r.category
                        """
                    ),
                    {"job_id": job_id},
                ).scalars()
            )

    @staticmethod
    def _require_analyzed_job(connection, job_id: int) -> None:
        found = connection.execute(
            text(
                """
                SELECT job_id
                FROM job_analyses
                WHERE job_id = :job_id
                """
            ),
            {"job_id": job_id},
        ).scalar_one_or_none()
        if found is None:
            raise ValueError(f"Job {job_id} has no analysis.")

    @staticmethod
    def _vector_literal(vector: list[float]) -> str:
        if len(vector) != 384:
            raise ValueError("responsibility embeddings must have 384 dimensions")
        return "[" + ",".join(str(float(value)) for value in vector) + "]"

    @staticmethod
    def _vector_values(value) -> list[float]:
        values = json.loads(value) if isinstance(value, str) else list(value)
        return [float(item) for item in values]
