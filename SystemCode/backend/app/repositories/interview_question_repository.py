from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3

from sqlalchemy import text

from app.db.postgres import get_postgres_engine
from app.db.sqlite import connect, initialize_database
from app.repositories.postgres_helpers import (
    ensure_company,
    ensure_role,
)
from app.schemas.interview_question import InterviewQuestion


class InterviewQuestionRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path
        # 延迟到第一次真正访问数据库时才建表/迁移，避免 import app 时就改写 data/careerpilot.db
        self._initialized = False

    @property
    def _use_postgres(self) -> bool:
        return self.db_path is None

    def _connect(self) -> sqlite3.Connection:
        if self.db_path is None:
            raise RuntimeError("SQLite is available only with an explicit test database path.")
        if not self._initialized:
            initialize_database(self.db_path)
            self._initialized = True
        return connect(self.db_path)

    def upsert_many(self, questions: list[InterviewQuestion]) -> int:
        if self._use_postgres:
            return self._upsert_many_postgres(questions)
        changed_count = 0
        with self._connect() as connection:
            for question in questions:
                existing = connection.execute(
                    "SELECT question_text FROM interview_questions WHERE source = ? AND external_id = ?",
                    (question.source, question.external_id),
                ).fetchone()
                if existing is None or existing["question_text"] != question.question_text:
                    changed_count += 1

                connection.execute(
                    """
                    INSERT INTO interview_questions (
                        source, external_id, question_text, standard_answer,
                        question_text_en, standard_answer_en, roles_json,
                        difficulty_level, company, collected_at,
                        question_embedding_json, skills_json, keywords_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source, external_id) DO UPDATE SET
                        question_text = excluded.question_text,
                        standard_answer = excluded.standard_answer,
                        question_text_en = excluded.question_text_en,
                        standard_answer_en = excluded.standard_answer_en,
                        roles_json = excluded.roles_json,
                        difficulty_level = excluded.difficulty_level,
                        company = excluded.company,
                        collected_at = excluded.collected_at,
                        question_embedding_json = excluded.question_embedding_json,
                        skills_json = excluded.skills_json,
                        keywords_json = excluded.keywords_json
                    """,
                    (
                        question.source,
                        question.external_id,
                        question.question_text,
                        question.standard_answer,
                        question.question_text_en,
                        question.standard_answer_en,
                        json.dumps(question.roles, ensure_ascii=False),
                        question.difficulty_level,
                        question.company,
                        question.collected_at.isoformat(),
                        json.dumps(question.question_embedding) if question.question_embedding else None,
                        json.dumps(question.skills, ensure_ascii=False),
                        json.dumps(question.keywords, ensure_ascii=False),
                    ),
                )
        return changed_count

    def list_questions(self, company: str | None = None, limit: int = 100) -> list[InterviewQuestion]:
        if self._use_postgres:
            return self._list_questions_postgres(company, limit)
        query = "SELECT * FROM interview_questions"
        params: list[str | int] = []
        if company:
            query += " WHERE company = ?"
            params.append(company)
        query += " ORDER BY collected_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_question(row) for row in rows]

    def count(self) -> int:
        if self._use_postgres:
            with get_postgres_engine().connect() as connection:
                return int(
                    connection.execute(text("SELECT COUNT(*) FROM interview_questions")).scalar_one()
                )
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM interview_questions").fetchone()
        return int(row["count"])

    def _row_to_question(self, row) -> InterviewQuestion:
        return InterviewQuestion(
            id=row["id"],
            source=row["source"],
            external_id=row["external_id"],
            question_text=row["question_text"],
            standard_answer=row["standard_answer"],
            question_text_en=row["question_text_en"],
            standard_answer_en=row["standard_answer_en"],
            roles=json.loads(row["roles_json"]),
            difficulty_level=row["difficulty_level"],
            company=row["company"],
            collected_at=datetime.fromisoformat(row["collected_at"]),
            question_embedding=json.loads(row["question_embedding_json"]) if row["question_embedding_json"] else None,
            skills=json.loads(row["skills_json"]),
            keywords=json.loads(row["keywords_json"]),
        )

    def _upsert_many_postgres(self, questions: list[InterviewQuestion]) -> int:
        changed_count = 0
        with get_postgres_engine().begin() as connection:
            for question in questions:
                existing = connection.execute(
                    text(
                        """
                        SELECT iq.id, iq.question_text
                        FROM question_sources qs
                        JOIN interview_questions iq ON iq.id = qs.question_id
                        WHERE qs.source = :source AND qs.external_id = :external_id
                        """
                    ),
                    {"source": question.source, "external_id": question.external_id},
                ).mappings().one_or_none()
                if existing is None or existing["question_text"] != question.question_text:
                    changed_count += 1
                company_id = (
                    ensure_company(connection, question.company) if question.company else None
                )
                if existing is None:
                    question_id = int(
                        connection.execute(
                            text(
                                """
                                INSERT INTO interview_questions (
                                    question_text, standard_answer, question_text_en,
                                    standard_answer_en, difficulty_level, company_id,
                                    company_text, normalized_hash, collected_at
                                ) VALUES (
                                    :question_text, :standard_answer, :question_text_en,
                                    :standard_answer_en, :difficulty_level, :company_id,
                                    :company_text, :normalized_hash, :collected_at
                                ) RETURNING id
                                """
                            ),
                            {
                                "question_text": question.question_text,
                                "standard_answer": question.standard_answer,
                                "question_text_en": question.question_text_en,
                                "standard_answer_en": question.standard_answer_en,
                                "difficulty_level": question.difficulty_level,
                                "company_id": company_id,
                                "company_text": question.company,
                                "normalized_hash": self._question_hash(question.question_text),
                                "collected_at": question.collected_at,
                            },
                        ).scalar_one()
                    )
                    connection.execute(
                        text(
                            """
                            INSERT INTO question_sources (question_id, source, external_id)
                            VALUES (:question_id, :source, :external_id)
                            """
                        ),
                        {
                            "question_id": question_id,
                            "source": question.source,
                            "external_id": question.external_id,
                        },
                    )
                else:
                    question_id = int(existing["id"])
                    connection.execute(
                        text(
                            """
                            UPDATE interview_questions
                            SET question_text = :question_text,
                                standard_answer = :standard_answer,
                                question_text_en = :question_text_en,
                                standard_answer_en = :standard_answer_en,
                                difficulty_level = :difficulty_level,
                                company_id = :company_id,
                                company_text = :company_text,
                                normalized_hash = :normalized_hash,
                                collected_at = :collected_at
                            WHERE id = :question_id
                            """
                        ),
                        {
                            "question_id": question_id,
                            "question_text": question.question_text,
                            "standard_answer": question.standard_answer,
                            "question_text_en": question.question_text_en,
                            "standard_answer_en": question.standard_answer_en,
                            "difficulty_level": question.difficulty_level,
                            "company_id": company_id,
                            "company_text": question.company,
                            "normalized_hash": self._question_hash(question.question_text),
                            "collected_at": question.collected_at,
                        },
                    )
                    connection.execute(
                        text("DELETE FROM question_roles WHERE question_id = :question_id"),
                        {"question_id": question_id},
                    )
                for sequence_no, role in enumerate(question.roles):
                    connection.execute(
                        text(
                            """
                            INSERT INTO question_roles (question_id, role_id, sequence_no)
                            VALUES (:question_id, :role_id, :sequence_no)
                            ON CONFLICT (question_id, role_id) DO NOTHING
                            """
                        ),
                        {
                            "question_id": question_id,
                            "role_id": ensure_role(connection, role),
                            "sequence_no": sequence_no,
                        },
                    )
        return changed_count

    @staticmethod
    def _question_hash(question_text: str) -> str:
        normalized = " ".join(question_text.casefold().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _list_questions_postgres(
        self, company: str | None, limit: int
    ) -> list[InterviewQuestion]:
        query = """
            SELECT iq.id, qs.source, qs.external_id, iq.question_text,
                   iq.standard_answer, iq.question_text_en, iq.standard_answer_en,
                   iq.difficulty_level, iq.company_text AS company, iq.collected_at,
                   COALESCE((
                       SELECT jsonb_agg(r.canonical_name ORDER BY qr.sequence_no)
                       FROM question_roles qr
                       JOIN roles r ON r.id = qr.role_id
                       WHERE qr.question_id = iq.id
                   ), '[]'::jsonb) AS roles
            FROM interview_questions iq
            JOIN LATERAL (
                SELECT source, external_id
                FROM question_sources
                WHERE question_id = iq.id
                ORDER BY id
                LIMIT 1
            ) qs ON TRUE
        """
        parameters: dict[str, object] = {"limit": limit}
        if company:
            query += " WHERE iq.company_text = :company"
            parameters["company"] = company
        query += " ORDER BY iq.collected_at DESC LIMIT :limit"
        with get_postgres_engine().connect() as connection:
            rows = connection.execute(text(query), parameters).mappings().all()
        return [
            InterviewQuestion(
                id=row["id"],
                source=row["source"],
                external_id=row["external_id"],
                question_text=row["question_text"],
                standard_answer=row["standard_answer"],
                question_text_en=row["question_text_en"],
                standard_answer_en=row["standard_answer_en"],
                roles=list(row["roles"]),
                difficulty_level=row["difficulty_level"],
                company=row["company"],
                collected_at=row["collected_at"],
                question_embedding=None,
                skills=[],
                keywords=[],
            )
            for row in rows
        ]
