from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy import bindparam, text

from app.db.postgres import get_postgres_engine
from app.schemas.common import DifficultyLevel


@dataclass(frozen=True)
class InterviewJobContext:
    job_id: int
    title: str


@dataclass(frozen=True)
class InterviewRoleMatch:
    role: str
    similarity: float
    rank: int


@dataclass(frozen=True)
class InterviewCandidateQuestion:
    id: int
    question_text: str
    standard_answer: str
    question_text_en: str
    standard_answer_en: str
    difficulty_level: DifficultyLevel
    roles: tuple[str, ...]
    source: str
    company: str | None


class InterviewRecommendationRepository:
    def get_job_context(self, job_id: int) -> InterviewJobContext | None:
        with get_postgres_engine().connect() as connection:
            row = connection.execute(
                text("SELECT id, title FROM job_postings WHERE id = :job_id"),
                {"job_id": job_id},
            ).mappings().one_or_none()
        if row is None:
            return None
        return InterviewJobContext(job_id=int(row["id"]), title=row["title"])

    def list_role_matches(self, job_id: int, limit: int = 3) -> list[InterviewRoleMatch]:
        with get_postgres_engine().connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT r.canonical_name AS role, jr.similarity, jr.rank
                    FROM job_roles jr
                    JOIN roles r ON r.id = jr.role_id
                    WHERE jr.job_id = :job_id
                    ORDER BY jr.rank
                    LIMIT :limit
                    """
                ),
                {"job_id": job_id, "limit": limit},
            ).mappings().all()
        return [
            InterviewRoleMatch(
                role=row["role"],
                similarity=float(row["similarity"]),
                rank=int(row["rank"]),
            )
            for row in rows
        ]

    def list_candidates(
        self,
        roles: list[str],
        exclude_question_ids: list[int] | None = None,
    ) -> list[InterviewCandidateQuestion]:
        if not roles:
            return []
        query = text(
            """
            SELECT iq.id, iq.question_text, iq.standard_answer,
                   iq.question_text_en, iq.standard_answer_en,
                   iq.difficulty_level, iq.company_text AS company,
                   COALESCE(source.source, 'unknown') AS source,
                   COALESCE((
                       SELECT jsonb_agg(r_all.canonical_name ORDER BY qr_all.sequence_no)
                       FROM question_roles qr_all
                       JOIN roles r_all ON r_all.id = qr_all.role_id
                       WHERE qr_all.question_id = iq.id
                   ), '[]'::jsonb) AS roles
            FROM interview_questions iq
            LEFT JOIN LATERAL (
                SELECT qs.source
                FROM question_sources qs
                WHERE qs.question_id = iq.id
                ORDER BY qs.id
                LIMIT 1
            ) source ON TRUE
            WHERE EXISTS (
                SELECT 1
                FROM question_roles qr
                JOIN roles r ON r.id = qr.role_id
                WHERE qr.question_id = iq.id
                  AND r.canonical_name IN :roles
            )
            ORDER BY iq.id
            """
        ).bindparams(bindparam("roles", expanding=True))
        excluded = set(exclude_question_ids or [])
        with get_postgres_engine().connect() as connection:
            rows = connection.execute(query, {"roles": roles}).mappings().all()
        return [
            InterviewCandidateQuestion(
                id=int(row["id"]),
                question_text=row["question_text"],
                standard_answer=row["standard_answer"],
                question_text_en=row["question_text_en"] or "",
                standard_answer_en=row["standard_answer_en"] or "",
                difficulty_level=row["difficulty_level"],
                roles=tuple(row["roles"]),
                source=row["source"],
                company=row["company"],
            )
            for row in rows
            if int(row["id"]) not in excluded
        ]
