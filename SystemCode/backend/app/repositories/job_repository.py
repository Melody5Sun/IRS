from datetime import datetime
import json
from pathlib import Path
import sqlite3

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from app.db.postgres import get_postgres_engine
from app.db.sqlite import connect, initialize_database
from app.ingestion.source_registry import JobSource
from app.parsers.job_industry_classifier import (
    classify_company_industry,
    normalize_company_name,
)
from app.repositories.postgres_helpers import ensure_company, ensure_skill
from app.schemas.job import (
    JobLibraryStatus,
    JobPosting,
    JobRequirementDocument,
)


class JobRepository:
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

    def upsert_many(self, jobs: list[JobPosting]) -> int:
        if self._use_postgres:
            return self._upsert_many_postgres(jobs)
        changed_count = 0
        with self._connect() as connection:
            for job in jobs:
                existing = connection.execute(
                    "SELECT content_hash FROM jobs WHERE source = ? AND external_id = ?",
                    (job.source, job.external_id),
                ).fetchone()
                if existing is None or existing["content_hash"] != job.content_hash:
                    changed_count += 1

                connection.execute(
                    """
                    INSERT INTO jobs (
                        source, company, external_id, title, location, description, url,
                        employment_type, collected_at, last_seen_at,
                        content_hash, status, raw_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source, external_id) DO UPDATE SET
                        company = excluded.company,
                        title = excluded.title,
                        location = excluded.location,
                        description = excluded.description,
                        url = excluded.url,
                        employment_type = excluded.employment_type,
                        last_seen_at = excluded.last_seen_at,
                        content_hash = excluded.content_hash,
                        status = CASE
                            WHEN jobs.status = 'inactive'
                                 AND jobs.content_hash = excluded.content_hash
                            THEN jobs.status
                            ELSE excluded.status
                        END,
                        raw_json = excluded.raw_json
                    """,
                    (
                        job.source,
                        job.company,
                        job.external_id,
                        job.title,
                        job.location,
                        job.description,
                        job.url,
                        job.employment_type,
                        job.collected_at.isoformat(),
                        job.last_seen_at.isoformat(),
                        job.content_hash,
                        job.status,
                        json.dumps(job.raw_json, ensure_ascii=False),
                    ),
                )
        return changed_count

    def list_jobs(
        self,
        status: str = "active",
        company: str | None = None,
        limit: int = 100,
    ) -> list[JobPosting]:
        if self._use_postgres:
            return self._list_jobs_postgres(status=status, company=company, limit=limit)
        query = "SELECT * FROM jobs WHERE status = ?"
        params: list[str | int] = [status]
        if company:
            query += " AND company = ?"
            params.append(company)
        query += " ORDER BY collected_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_job(row) for row in rows]

    def library_status(self) -> JobLibraryStatus:
        # 每次同步 upsert 都会把看到的岗位 last_seen_at 刷成本次时间，取最大值即最近同步时间
        if self._use_postgres:
            with get_postgres_engine().connect() as connection:
                row = connection.execute(
                    text(
                        """
                        SELECT MAX(last_seen_at) AS synced_at,
                               COUNT(*) FILTER (WHERE status = 'active') AS active_job_count
                        FROM job_postings
                        """
                    )
                ).mappings().one()
            return JobLibraryStatus.model_validate(dict(row))
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT MAX(last_seen_at) AS synced_at,
                       COALESCE(SUM(status = 'active'), 0) AS active_job_count
                FROM jobs
                """
            ).fetchone()
        return JobLibraryStatus.model_validate(dict(row))

    def get_job(self, job_id: int) -> JobPosting | None:
        if self._use_postgres:
            return self._get_job_postgres(job_id)
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def save_job_analysis(self, document: JobRequirementDocument) -> None:
        if document.job_id is None:
            raise ValueError("job_id is required before saving job analysis.")
        if self._use_postgres:
            self._save_job_analysis_postgres(document)
            return

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO company_industries (normalized_company, company, industry)
                VALUES (?, ?, ?)
                ON CONFLICT(normalized_company) DO UPDATE SET
                    company = excluded.company,
                    industry = excluded.industry
                """,
                (
                    normalize_company_name(document.company),
                    document.company,
                    classify_company_industry(document.company),
                ),
            )
            connection.execute(
                """
                INSERT INTO job_analysis (
                    job_id, summary, responsibilities_json, required_skills_json,
                    preferred_skills_json, employment_type,
                    candidate_type, remote_policy,
                    degree_required, major_required_json, keywords_json,
                    source_evidence_json, analysis_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    summary = excluded.summary,
                    responsibilities_json = excluded.responsibilities_json,
                    required_skills_json = excluded.required_skills_json,
                    preferred_skills_json = excluded.preferred_skills_json,
                    employment_type = excluded.employment_type,
                    candidate_type = excluded.candidate_type,
                    remote_policy = excluded.remote_policy,
                    degree_required = excluded.degree_required,
                    major_required_json = excluded.major_required_json,
                    keywords_json = excluded.keywords_json,
                    source_evidence_json = excluded.source_evidence_json,
                    analysis_json = excluded.analysis_json
                """,
                (
                    document.job_id,
                    document.summary,
                    json.dumps(document.responsibilities, ensure_ascii=False),
                    json.dumps(document.required_skills, ensure_ascii=False),
                    json.dumps(document.preferred_skills, ensure_ascii=False),
                    document.employment_type,
                    document.candidate_type,
                    document.remote_policy,
                    document.degree_required,
                    json.dumps(document.major_required, ensure_ascii=False),
                    json.dumps(document.keywords, ensure_ascii=False),
                    json.dumps(document.source_evidence, ensure_ascii=False),
                    document.model_dump_json(exclude={"industry"}),
                ),
            )

    def count_job_analysis(self) -> int:
        if self._use_postgres:
            with get_postgres_engine().connect() as connection:
                return int(connection.execute(text("SELECT COUNT(*) FROM job_analyses")).scalar_one())
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM job_analysis").fetchone()
        return int(row["count"])

    def mark_job_inactive(self, job_id: int, reason: str | None = None) -> None:
        if self._use_postgres:
            self._mark_job_inactive_postgres(job_id, reason)
            return
        with self._connect() as connection:
            row = connection.execute("SELECT raw_json FROM jobs WHERE id = ?", (job_id,)).fetchone()
            raw_json = {}
            if row is not None:
                raw_json = json.loads(row["raw_json"])
            raw_json["inactive_reason"] = reason or "No required or preferred skills were extracted."
            connection.execute(
                """
                UPDATE jobs
                SET status = 'inactive',
                    raw_json = ?
                WHERE id = ?
                """,
                (json.dumps(raw_json, ensure_ascii=False), job_id),
            )
            connection.execute("DELETE FROM job_analysis WHERE job_id = ?", (job_id,))

    def ensure_company_sources(self, sources: list[JobSource]) -> None:
        if self._use_postgres:
            self._ensure_company_sources_postgres(sources)
            return
        now = datetime.now().astimezone().isoformat()
        with self._connect() as connection:
            for source in sources:
                connection.execute(
                    """
                    INSERT INTO company_sources (
                        name, company, provider, identifier, enabled, priority, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        company = excluded.company,
                        provider = excluded.provider,
                        identifier = excluded.identifier,
                        enabled = excluded.enabled,
                        priority = excluded.priority,
                        updated_at = excluded.updated_at
                    """,
                    (
                        source.name,
                        source.company,
                        source.provider,
                        source.identifier,
                        1 if source.enabled else 0,
                        source.priority,
                        now,
                    ),
                )

    def list_company_sources(self, enabled_only: bool = False) -> list[JobSource]:
        if self._use_postgres:
            return self._list_company_sources_postgres(enabled_only)
        query = "SELECT * FROM company_sources"
        params: list[int] = []
        if enabled_only:
            query += " WHERE enabled = ?"
            params.append(1)
        query += " ORDER BY priority ASC, company ASC, name ASC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            JobSource(
                name=row["name"],
                company=row["company"],
                provider=row["provider"],
                identifier=row["identifier"],
                enabled=bool(row["enabled"]),
                priority=row["priority"],
            )
            for row in rows
        ]

    def update_company_source_run_status(
        self,
        source_name: str,
        status: str,
        message: str | None = None,
    ) -> None:
        if self._use_postgres:
            with get_postgres_engine().begin() as connection:
                connection.execute(
                    text(
                        """
                        UPDATE job_sources
                        SET last_checked_at = CURRENT_TIMESTAMP,
                            last_status = :status,
                            last_message = :message,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE name = :source_name
                        """
                    ),
                    {"status": status, "message": message, "source_name": source_name},
                )
            return
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE company_sources
                SET last_checked_at = ?,
                    last_status = ?,
                    last_message = ?
                WHERE name = ?
                """,
                (
                    datetime.now().astimezone().isoformat(),
                    status,
                    message,
                    source_name,
                ),
            )

    def clear_all_job_data(self) -> None:
        if self._use_postgres:
            with get_postgres_engine().begin() as connection:
                connection.execute(text("DELETE FROM job_postings"))
            return
        with self._connect() as connection:
            connection.execute("DELETE FROM job_analysis")
            connection.execute("DELETE FROM jobs")
            connection.execute(
                """
                DELETE FROM sqlite_sequence
                WHERE name = 'jobs'
                """
            )

    @staticmethod
    def _ensure_source(connection: Connection, source_name: str, company_id: int) -> int:
        source_id = connection.execute(
            text("SELECT id FROM job_sources WHERE name = :name"),
            {"name": source_name},
        ).scalar_one_or_none()
        if source_id is not None:
            return int(source_id)
        return int(
            connection.execute(
                text(
                    """
                    INSERT INTO job_sources (
                        company_id, name, provider, identifier, enabled, priority
                    ) VALUES (
                        :company_id, :name, 'runtime', :identifier, FALSE, 100
                    )
                    RETURNING id
                    """
                ),
                {
                    "company_id": company_id,
                    "name": source_name,
                    "identifier": source_name,
                },
            ).scalar_one()
        )

    def _upsert_many_postgres(self, jobs: list[JobPosting]) -> int:
        changed_count = 0
        with get_postgres_engine().begin() as connection:
            for job in jobs:
                company_id = ensure_company(connection, job.company)
                source_id = self._ensure_source(connection, job.source, company_id)
                existing = connection.execute(
                    text(
                        """
                        SELECT jp.id, jp.content_hash
                        FROM job_postings jp
                        WHERE jp.source_id = :source_id
                          AND jp.external_id = :external_id
                        """
                    ),
                    {"source_id": source_id, "external_id": job.external_id},
                ).mappings().one_or_none()
                if existing is None or existing["content_hash"] != job.content_hash:
                    changed_count += 1

                job_id = int(
                    connection.execute(
                        text(
                            """
                            INSERT INTO job_postings (
                                company_id, source_id, external_id, title, location_text,
                                source_employment_type, source_url, status,
                                first_seen_at, last_seen_at, description, content_hash,
                                raw_payload, collected_at
                            ) VALUES (
                                :company_id, :source_id, :external_id, :title, :location,
                                :employment_type, :source_url, :status,
                                :first_seen_at, :last_seen_at, :description, :content_hash,
                                CAST(:raw_payload AS JSONB), :collected_at
                            )
                            ON CONFLICT (source_id, external_id) DO UPDATE SET
                                company_id = EXCLUDED.company_id,
                                title = EXCLUDED.title,
                                location_text = EXCLUDED.location_text,
                                source_employment_type = EXCLUDED.source_employment_type,
                                source_url = EXCLUDED.source_url,
                                last_seen_at = EXCLUDED.last_seen_at,
                                description = EXCLUDED.description,
                                content_hash = EXCLUDED.content_hash,
                                raw_payload = EXCLUDED.raw_payload,
                                collected_at = EXCLUDED.collected_at,
                                status = CASE
                                    WHEN job_postings.status = 'inactive'
                                     AND :content_unchanged
                                    THEN job_postings.status
                                    ELSE EXCLUDED.status
                                END,
                                updated_at = CURRENT_TIMESTAMP
                            RETURNING id
                            """
                        ),
                        {
                            "company_id": company_id,
                            "source_id": source_id,
                            "external_id": job.external_id,
                            "title": job.title,
                            "location": job.location,
                            "employment_type": job.employment_type,
                            "source_url": job.url,
                            "status": job.status,
                            "first_seen_at": job.collected_at,
                            "last_seen_at": job.last_seen_at,
                            "description": job.description,
                            "content_hash": job.content_hash,
                            "raw_payload": json.dumps(job.raw_json, ensure_ascii=False),
                            "collected_at": job.collected_at,
                            "content_unchanged": bool(
                                existing is not None
                                and existing["content_hash"] == job.content_hash
                            ),
                        },
                    ).scalar_one()
                )
                if existing is not None and existing["content_hash"] != job.content_hash:
                    connection.execute(
                        text("DELETE FROM job_analyses WHERE job_id = :job_id"),
                        {"job_id": job_id},
                    )
        return changed_count

    @staticmethod
    def _job_select_sql() -> str:
        return """
            SELECT jp.id, js.name AS source, c.name AS company, jp.external_id,
                   jp.title, jp.location_text AS location, jp.description,
                   jp.source_url AS url, jp.source_employment_type AS employment_type,
                   jp.collected_at, jp.last_seen_at, jp.content_hash,
                   jp.status, jp.raw_payload AS raw_json
            FROM job_postings jp
            JOIN companies c ON c.id = jp.company_id
            JOIN job_sources js ON js.id = jp.source_id
        """

    def _list_jobs_postgres(
        self, status: str, company: str | None, limit: int
    ) -> list[JobPosting]:
        query = self._job_select_sql() + " WHERE jp.status = :status"
        parameters: dict[str, object] = {"status": status, "limit": limit}
        if company:
            query += " AND c.name = :company"
            parameters["company"] = company
        query += " ORDER BY jp.collected_at DESC LIMIT :limit"
        with get_postgres_engine().connect() as connection:
            rows = connection.execute(text(query), parameters).mappings().all()
        return [self._postgres_row_to_job(row) for row in rows]

    def _get_job_postgres(self, job_id: int) -> JobPosting | None:
        query = self._job_select_sql() + " WHERE jp.id = :job_id"
        with get_postgres_engine().connect() as connection:
            row = connection.execute(text(query), {"job_id": job_id}).mappings().one_or_none()
        return self._postgres_row_to_job(row) if row else None

    def _save_job_analysis_postgres(self, document: JobRequirementDocument) -> None:
        assert document.job_id is not None
        with get_postgres_engine().begin() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT jp.company_id
                    FROM job_postings jp
                    WHERE jp.id = :job_id
                    """
                ),
                {"job_id": document.job_id},
            ).mappings().one_or_none()
            if row is None:
                raise ValueError(f"Job {document.job_id} does not exist.")
            industry_id = connection.execute(
                text("SELECT id FROM industries WHERE name = :name"),
                {"name": classify_company_industry(document.company)},
            ).scalar_one()
            connection.execute(
                text(
                    """
                    UPDATE companies
                    SET industry_id = :industry_id, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :company_id
                    """
                ),
                {"company_id": row["company_id"], "industry_id": industry_id},
            )
            connection.execute(
                text("DELETE FROM job_analyses WHERE job_id = :job_id"),
                {"job_id": document.job_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO job_analyses (
                        job_id, summary, employment_type, candidate_type,
                        remote_policy, degree_required, raw_analysis
                    ) VALUES (
                        :job_id, :summary, :employment_type, :candidate_type,
                        :remote_policy, :degree_required, CAST(:raw_analysis AS JSONB)
                    )
                    """
                ),
                {
                    "job_id": document.job_id,
                    "summary": document.summary,
                    "employment_type": document.employment_type,
                    "candidate_type": document.candidate_type,
                    "remote_policy": document.remote_policy,
                    "degree_required": document.degree_required,
                    "raw_analysis": document.model_dump_json(exclude={"industry"}),
                },
            )
            for sequence_no, value in enumerate(document.responsibilities):
                connection.execute(
                    text(
                        """
                        INSERT INTO job_responsibilities (
                            job_id, sequence_no, responsibility_text
                        ) VALUES (:job_id, :sequence_no, :value)
                        """
                    ),
                    {"job_id": document.job_id, "sequence_no": sequence_no, "value": value},
                )
            for requirement_type, values in (
                ("required", document.required_skills),
                ("preferred", document.preferred_skills),
            ):
                for sequence_no, value in enumerate(values):
                    connection.execute(
                        text(
                            """
                            INSERT INTO job_skill_requirements (
                                job_id, skill_id, requirement_type,
                                sequence_no, source_text
                            ) VALUES (
                                :job_id, :skill_id, :requirement_type,
                                :sequence_no, :value
                            )
                            """
                        ),
                        {
                            "job_id": document.job_id,
                            "skill_id": ensure_skill(connection, value),
                            "requirement_type": requirement_type,
                            "sequence_no": sequence_no,
                            "value": value,
                        },
                    )

    def _mark_job_inactive_postgres(self, job_id: int, reason: str | None) -> None:
        inactive_reason = reason or "No required or preferred skills were extracted."
        with get_postgres_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE job_postings
                    SET status = 'inactive', inactive_reason = :reason,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :job_id
                    """
                ),
                {"reason": inactive_reason, "job_id": job_id},
            )
            connection.execute(
                text(
                    """
                    UPDATE job_postings
                    SET raw_payload = raw_payload || jsonb_build_object('inactive_reason', :reason)
                    WHERE id = :job_id
                    """
                ),
                {"reason": inactive_reason, "job_id": job_id},
            )
            connection.execute(
                text(
                    """
                    DELETE FROM job_analyses WHERE job_id = :job_id
                    """
                ),
                {"job_id": job_id},
            )

    def _ensure_company_sources_postgres(self, sources: list[JobSource]) -> None:
        with get_postgres_engine().begin() as connection:
            for source in sources:
                company_id = ensure_company(connection, source.company)
                connection.execute(
                    text(
                        """
                        INSERT INTO job_sources (
                            company_id, name, provider, identifier, enabled, priority
                        ) VALUES (
                            :company_id, :name, :provider, :identifier, :enabled, :priority
                        )
                        ON CONFLICT (name) DO UPDATE SET
                            company_id = EXCLUDED.company_id,
                            provider = EXCLUDED.provider,
                            identifier = EXCLUDED.identifier,
                            enabled = EXCLUDED.enabled,
                            priority = EXCLUDED.priority,
                            updated_at = CURRENT_TIMESTAMP
                        """
                    ),
                    {
                        "company_id": company_id,
                        "name": source.name,
                        "provider": source.provider,
                        "identifier": source.identifier,
                        "enabled": source.enabled,
                        "priority": source.priority,
                    },
                )

    def _list_company_sources_postgres(self, enabled_only: bool) -> list[JobSource]:
        query = """
            SELECT js.name, c.name AS company, js.provider, js.identifier,
                   js.enabled, js.priority
            FROM job_sources js
            JOIN companies c ON c.id = js.company_id
        """
        if enabled_only:
            query += " WHERE js.enabled IS TRUE"
        query += " ORDER BY js.priority ASC, c.name ASC, js.name ASC"
        with get_postgres_engine().connect() as connection:
            rows = connection.execute(text(query)).mappings().all()
        return [JobSource(**dict(row)) for row in rows]

    @staticmethod
    def _postgres_row_to_job(row: RowMapping) -> JobPosting:
        raw_json = row["raw_json"] or {}
        return JobPosting(
            id=row["id"],
            source=row["source"],
            company=row["company"],
            external_id=row["external_id"],
            title=row["title"],
            location=row["location"],
            description=row["description"],
            url=row["url"],
            employment_type=row["employment_type"],
            collected_at=row["collected_at"],
            last_seen_at=row["last_seen_at"],
            content_hash=row["content_hash"],
            status=row["status"],
            raw_json=raw_json if isinstance(raw_json, dict) else json.loads(raw_json),
        )

    def _row_to_job(self, row) -> JobPosting:
        return JobPosting(
            id=row["id"],
            source=row["source"],
            company=row["company"],
            external_id=row["external_id"],
            title=row["title"],
            location=row["location"],
            description=row["description"],
            url=row["url"],
            employment_type=row["employment_type"],
            collected_at=datetime.fromisoformat(row["collected_at"]),
            last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
            content_hash=row["content_hash"],
            status=row["status"],
            raw_json=json.loads(row["raw_json"]),
        )
