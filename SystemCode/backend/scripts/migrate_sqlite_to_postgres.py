from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection


BACKEND_ROOT = Path(__file__).resolve().parents[1]
LEGACY_TABLE_KEYS = {
    "jobs": "id",
    "company_sources": "name",
    "industries": "name",
    "company_industries": "normalized_company",
    "job_analysis": "job_id",
    "user_profile": "id",
    "resume_uploads": "id",
    "interview_questions": "id",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def normalized_name(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def normalized_text_hash(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sqlite_rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"').fetchall()]


def archive_legacy_rows(
    source: sqlite3.Connection,
    target: Connection,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    statement = text(
        """
        INSERT INTO migration_legacy_rows (
            source_table, source_primary_key, row_payload, row_sha256
        ) VALUES (
            :source_table, :source_primary_key, CAST(:row_payload AS JSONB), :row_sha256
        )
        """
    )
    for table_name, key_name in LEGACY_TABLE_KEYS.items():
        rows = sqlite_rows(source, table_name)
        counts[table_name] = len(rows)
        for row in rows:
            payload = canonical_json(row)
            target.execute(
                statement,
                {
                    "source_table": table_name,
                    "source_primary_key": str(row[key_name]),
                    "row_payload": payload,
                    "row_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                },
            )
    return counts


def insert_returning_id(target: Connection, sql: str, parameters: dict[str, Any]) -> int:
    return int(target.execute(text(sql), parameters).scalar_one())


def ensure_company(
    target: Connection,
    company_ids: dict[str, int],
    company_name: str,
) -> int:
    key = normalized_name(company_name)
    if not key:
        company_name = "Unknown"
        key = "unknown"
    if key not in company_ids:
        company_ids[key] = insert_returning_id(
            target,
            """
            INSERT INTO companies (name, normalized_name)
            VALUES (:name, :normalized_name)
            ON CONFLICT (normalized_name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            {"name": company_name, "normalized_name": key},
        )
    return company_ids[key]


def ensure_skill(
    target: Connection,
    skill_ids: dict[str, int],
    skill_name: str,
) -> int:
    key = normalized_name(skill_name)
    if not key:
        key = hashlib.sha256(skill_name.encode("utf-8")).hexdigest()
    if key not in skill_ids:
        skill_ids[key] = insert_returning_id(
            target,
            """
            INSERT INTO skills (canonical_name, normalized_name)
            VALUES (:canonical_name, :normalized_name)
            ON CONFLICT (normalized_name) DO UPDATE SET canonical_name = skills.canonical_name
            RETURNING id
            """,
            {"canonical_name": skill_name, "normalized_name": key},
        )
    return skill_ids[key]


def seed_roles(target: Connection) -> dict[str, int]:
    role_ids: dict[str, int] = {}
    taxonomy_path = BACKEND_ROOT / "data" / "role_taxonomy" / "roles.json"
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    for role in taxonomy:
        role_id = insert_returning_id(
            target,
            """
            INSERT INTO roles (canonical_name, category, description)
            VALUES (:name, :category, :description)
            ON CONFLICT (canonical_name) DO UPDATE SET
                category = EXCLUDED.category,
                description = EXCLUDED.description
            RETURNING id
            """,
            {
                "name": role["role"],
                "category": role.get("category"),
                "description": role.get("description", ""),
            },
        )
        role_ids[role["role"]] = role_id
        for alias in role.get("aliases", []):
            target.execute(
                text(
                    """
                    INSERT INTO role_aliases (role_id, alias, normalized_alias)
                    VALUES (:role_id, :alias, :normalized_alias)
                    ON CONFLICT (normalized_alias) DO NOTHING
                    """
                ),
                {
                    "role_id": role_id,
                    "alias": alias,
                    "normalized_alias": normalized_name(alias),
                },
            )
    return role_ids


def ensure_role(target: Connection, role_ids: dict[str, int], role_name: str) -> int:
    if role_name not in role_ids:
        role_ids[role_name] = insert_returning_id(
            target,
            """
            INSERT INTO roles (canonical_name)
            VALUES (:name)
            ON CONFLICT (canonical_name) DO UPDATE SET canonical_name = EXCLUDED.canonical_name
            RETURNING id
            """,
            {"name": role_name},
        )
    return role_ids[role_name]


def migrate_reference_data(
    source: sqlite3.Connection,
    target: Connection,
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    company_ids: dict[str, int] = {}
    industry_ids: dict[str, int] = {}
    source_ids: dict[str, int] = {}

    company_names: list[str] = []
    for table_name in ("company_sources", "jobs", "company_industries"):
        company_names.extend(row["company"] for row in sqlite_rows(source, table_name))
    company_names.extend(
        row["company"]
        for row in sqlite_rows(source, "interview_questions")
        if row.get("company")
    )
    for company_name in company_names:
        ensure_company(target, company_ids, company_name)

    for row in sqlite_rows(source, "industries"):
        industry_ids[row["name"]] = insert_returning_id(
            target,
            "INSERT INTO industries (name) VALUES (:name) RETURNING id",
            {"name": row["name"]},
        )

    for row in sqlite_rows(source, "company_industries"):
        target.execute(
            text(
                """
                INSERT INTO company_industries (company_id, industry_id)
                VALUES (:company_id, :industry_id)
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "company_id": ensure_company(target, company_ids, row["company"]),
                "industry_id": industry_ids[row["industry"]],
            },
        )

    for row in sqlite_rows(source, "company_sources"):
        source_ids[row["name"]] = insert_returning_id(
            target,
            """
            INSERT INTO job_sources (
                company_id, name, provider, identifier, enabled, priority,
                last_checked_at, last_status, last_message, updated_at
            ) VALUES (
                :company_id, :name, :provider, :identifier, :enabled, :priority,
                CAST(:last_checked_at AS TIMESTAMPTZ), :last_status, :last_message,
                CAST(:updated_at AS TIMESTAMPTZ)
            ) RETURNING id
            """,
            {
                "company_id": ensure_company(target, company_ids, row["company"]),
                "name": row["name"],
                "provider": row["provider"],
                "identifier": row["identifier"],
                "enabled": bool(row["enabled"]),
                "priority": row["priority"],
                "last_checked_at": row["last_checked_at"],
                "last_status": row["last_status"],
                "last_message": row["last_message"],
                "updated_at": row["updated_at"],
            },
        )

    for row in sqlite_rows(source, "jobs"):
        if row["source"] in source_ids:
            continue
        company_id = ensure_company(target, company_ids, row["company"])
        synthetic_identifier = f"legacy:{row['source']}"
        source_ids[row["source"]] = insert_returning_id(
            target,
            """
            INSERT INTO job_sources (company_id, name, provider, identifier, enabled)
            VALUES (:company_id, :name, 'legacy', :identifier, FALSE)
            RETURNING id
            """,
            {
                "company_id": company_id,
                "name": row["source"],
                "identifier": synthetic_identifier,
            },
        )
    return company_ids, industry_ids, source_ids


def migrate_jobs(
    source: sqlite3.Connection,
    target: Connection,
    company_ids: dict[str, int],
    source_ids: dict[str, int],
    skill_ids: dict[str, int],
) -> None:
    jobs = {row["id"]: row for row in sqlite_rows(source, "jobs")}
    analyses = {row["job_id"]: row for row in sqlite_rows(source, "job_analysis")}
    for job_id, row in jobs.items():
        raw_payload = parse_json(row["raw_json"], {})
        target.execute(
            text(
                """
                INSERT INTO job_postings (
                    id, company_id, source_id, external_id, title, location_text,
                    source_employment_type, source_url, status, inactive_reason,
                    first_seen_at, last_seen_at
                ) VALUES (
                    :id, :company_id, :source_id, :external_id, :title, :location,
                    :employment_type, :source_url, :status, :inactive_reason,
                    CAST(:first_seen_at AS TIMESTAMPTZ), CAST(:last_seen_at AS TIMESTAMPTZ)
                )
                """
            ),
            {
                "id": job_id,
                "company_id": ensure_company(target, company_ids, row["company"]),
                "source_id": source_ids[row["source"]],
                "external_id": row["external_id"],
                "title": row["title"],
                "location": row["location"],
                "employment_type": row["employment_type"],
                "source_url": row["url"],
                "status": row["status"],
                "inactive_reason": raw_payload.get("inactive_reason"),
                "first_seen_at": row["collected_at"],
                "last_seen_at": row["last_seen_at"],
            },
        )
        target.execute(
            text(
                """
                INSERT INTO job_versions (
                    id, job_id, content_hash, description, raw_payload, collected_at
                ) VALUES (
                    :id, :job_id, :content_hash, :description,
                    CAST(:raw_payload AS JSONB), CAST(:collected_at AS TIMESTAMPTZ)
                )
                """
            ),
            {
                "id": job_id,
                "job_id": job_id,
                "content_hash": row["content_hash"],
                "description": row["description"],
                "raw_payload": canonical_json(raw_payload),
                "collected_at": row["collected_at"],
            },
        )
        analysis = analyses.get(job_id)
        if analysis is None:
            continue
        target.execute(
            text(
                """
                INSERT INTO job_analyses (
                    job_version_id, summary, employment_type, candidate_type,
                    remote_policy, degree_required, raw_analysis
                ) VALUES (
                    :job_version_id, :summary, :employment_type, :candidate_type,
                    :remote_policy, :degree_required, CAST(:raw_analysis AS JSONB)
                )
                """
            ),
            {
                "job_version_id": job_id,
                "summary": analysis["summary"],
                "employment_type": analysis["employment_type"],
                "candidate_type": analysis["candidate_type"],
                "remote_policy": analysis["remote_policy"],
                "degree_required": analysis["degree_required"],
                "raw_analysis": canonical_json(parse_json(analysis["analysis_json"], {})),
            },
        )
        for sequence_no, responsibility in enumerate(
            parse_json(analysis["responsibilities_json"], [])
        ):
            target.execute(
                text(
                    """
                    INSERT INTO job_responsibilities (
                        job_version_id, sequence_no, responsibility_text
                    ) VALUES (:job_version_id, :sequence_no, :value)
                    """
                ),
                {"job_version_id": job_id, "sequence_no": sequence_no, "value": responsibility},
            )
        for requirement_type, column_name in (
            ("required", "required_skills_json"),
            ("preferred", "preferred_skills_json"),
        ):
            for sequence_no, skill_name in enumerate(parse_json(analysis[column_name], [])):
                target.execute(
                    text(
                        """
                        INSERT INTO job_skill_requirements (
                            job_version_id, skill_id, requirement_type, sequence_no, source_text
                        ) VALUES (
                            :job_version_id, :skill_id, :requirement_type, :sequence_no, :source_text
                        )
                        """
                    ),
                    {
                        "job_version_id": job_id,
                        "skill_id": ensure_skill(target, skill_ids, skill_name),
                        "requirement_type": requirement_type,
                        "sequence_no": sequence_no,
                        "source_text": skill_name,
                    },
                )
        for table_name, column_name, value_column in (
            ("job_major_requirements", "major_required_json", "major_text"),
            ("job_keywords", "keywords_json", "keyword_text"),
            ("job_source_evidence", "source_evidence_json", "evidence_text"),
        ):
            for sequence_no, value in enumerate(parse_json(analysis[column_name], [])):
                target.execute(
                    text(
                        f"""
                        INSERT INTO {table_name} (job_version_id, sequence_no, {value_column})
                        VALUES (:job_version_id, :sequence_no, :value)
                        """
                    ),
                    {"job_version_id": job_id, "sequence_no": sequence_no, "value": value},
                )


def migrate_questions(
    source: sqlite3.Connection,
    target: Connection,
    company_ids: dict[str, int],
    role_ids: dict[str, int],
    skill_ids: dict[str, int],
) -> None:
    for row in sqlite_rows(source, "interview_questions"):
        company_id = (
            ensure_company(target, company_ids, row["company"]) if row.get("company") else None
        )
        target.execute(
            text(
                """
                INSERT INTO interview_questions (
                    id, question_text, standard_answer, question_text_en,
                    standard_answer_en, difficulty_level, company_id, company_text,
                    normalized_hash, collected_at
                ) VALUES (
                    :id, :question_text, :standard_answer, :question_text_en,
                    :standard_answer_en, :difficulty_level, :company_id, :company_text,
                    :normalized_hash, CAST(:collected_at AS TIMESTAMPTZ)
                )
                """
            ),
            {
                "id": row["id"],
                "question_text": row["question_text"],
                "standard_answer": row["standard_answer"],
                "question_text_en": row["question_text_en"],
                "standard_answer_en": row["standard_answer_en"],
                "difficulty_level": row["difficulty_level"],
                "company_id": company_id,
                "company_text": row["company"],
                "normalized_hash": normalized_text_hash(row["question_text"]),
                "collected_at": row["collected_at"],
            },
        )
        target.execute(
            text(
                """
                INSERT INTO question_sources (question_id, source, external_id)
                VALUES (:question_id, :source, :external_id)
                """
            ),
            {"question_id": row["id"], "source": row["source"], "external_id": row["external_id"]},
        )
        for sequence_no, role_name in enumerate(parse_json(row["roles_json"], [])):
            target.execute(
                text(
                    """
                    INSERT INTO question_roles (question_id, role_id, sequence_no)
                    VALUES (:question_id, :role_id, :sequence_no)
                    ON CONFLICT (question_id, role_id) DO NOTHING
                    """
                ),
                {
                    "question_id": row["id"],
                    "role_id": ensure_role(target, role_ids, role_name),
                    "sequence_no": sequence_no,
                },
            )
        for sequence_no, skill_name in enumerate(parse_json(row["skills_json"], [])):
            target.execute(
                text(
                    """
                    INSERT INTO question_skills (
                        question_id, skill_id, sequence_no, source_text
                    ) VALUES (:question_id, :skill_id, :sequence_no, :source_text)
                    ON CONFLICT (question_id, skill_id) DO NOTHING
                    """
                ),
                {
                    "question_id": row["id"],
                    "skill_id": ensure_skill(target, skill_ids, skill_name),
                    "sequence_no": sequence_no,
                    "source_text": skill_name,
                },
            )
        for sequence_no, keyword in enumerate(parse_json(row["keywords_json"], [])):
            target.execute(
                text(
                    """
                    INSERT INTO question_keywords (question_id, sequence_no, keyword_text)
                    VALUES (:question_id, :sequence_no, :keyword)
                    """
                ),
                {"question_id": row["id"], "sequence_no": sequence_no, "keyword": keyword},
            )
        raw_embedding = parse_json(row["question_embedding_json"], None)
        if raw_embedding is not None:
            vector_value = (
                "[" + ",".join(str(value) for value in raw_embedding) + "]"
                if len(raw_embedding) == 384
                else None
            )
            target.execute(
                text(
                    """
                    INSERT INTO question_embeddings (question_id, embedding, raw_embedding)
                    VALUES (
                        :question_id, CAST(:embedding AS vector), CAST(:raw_embedding AS JSONB)
                    )
                    """
                ),
                {
                    "question_id": row["id"],
                    "embedding": vector_value,
                    "raw_embedding": canonical_json(raw_embedding),
                },
            )


def migrate_users(
    source: sqlite3.Connection,
    target: Connection,
    role_ids: dict[str, int],
    industry_ids: dict[str, int],
    skill_ids: dict[str, int],
) -> None:
    profiles = sqlite_rows(source, "user_profile")
    resume_rows = sqlite_rows(source, "resume_uploads")
    if not profiles and not resume_rows:
        return
    target.execute(text("INSERT INTO users (id) VALUES (1)"))
    for row in profiles:
        profile = parse_json(row["profile_json"], {})
        constraints = profile.get("constraints", {})
        target.execute(
            text(
                """
                INSERT INTO user_profiles (user_id, profile_payload, notes, updated_at)
                VALUES (
                    1, CAST(:payload AS JSONB), :notes, CAST(:updated_at AS TIMESTAMPTZ)
                )
                """
            ),
            {
                "payload": canonical_json(profile),
                "notes": constraints.get("notes", ""),
                "updated_at": row["updated_at"],
            },
        )
        for priority, role_name in enumerate(constraints.get("target_roles", []), start=1):
            target.execute(
                text(
                    """
                    INSERT INTO user_target_roles (user_id, role_id, priority)
                    VALUES (1, :role_id, :priority)
                    ON CONFLICT (user_id, role_id) DO NOTHING
                    """
                ),
                {"role_id": ensure_role(target, role_ids, role_name), "priority": priority},
            )
        for industry_name in constraints.get("target_industries", []):
            if industry_name in industry_ids:
                target.execute(
                    text(
                        """
                        INSERT INTO user_target_industries (user_id, industry_id)
                        VALUES (1, :industry_id) ON CONFLICT DO NOTHING
                        """
                    ),
                    {"industry_id": industry_ids[industry_name]},
                )
    for row in resume_rows:
        resume = parse_json(row["resume_json"], {})
        target.execute(
            text(
                """
                INSERT INTO resumes (
                    id, user_id, legacy_resume_upload_id, filename, parsed_payload, uploaded_at
                ) VALUES (
                    :id, 1, :id, :filename, CAST(:payload AS JSONB),
                    CAST(:uploaded_at AS TIMESTAMPTZ)
                )
                """
            ),
            {
                "id": row["id"],
                "filename": row["filename"],
                "payload": canonical_json(resume),
                "uploaded_at": row["uploaded_at"],
            },
        )
        for sequence_no, skill_name in enumerate(resume.get("skills", [])):
            target.execute(
                text(
                    """
                    INSERT INTO resume_skills (resume_id, skill_id, sequence_no, source_text)
                    VALUES (:resume_id, :skill_id, :sequence_no, :source_text)
                    ON CONFLICT (resume_id, skill_id) DO NOTHING
                    """
                ),
                {
                    "resume_id": row["id"],
                    "skill_id": ensure_skill(target, skill_ids, skill_name),
                    "sequence_no": sequence_no,
                    "source_text": skill_name,
                },
            )
        evidence_groups = (
            ("experience", resume.get("experiences", []), "title", "company", "description"),
            ("project", resume.get("projects", []), "title", None, "summary"),
            ("research", resume.get("research", []), "title", "institution", "summary"),
        )
        for evidence_type, entries, title_key, organization_key, summary_key in evidence_groups:
            for sequence_no, entry in enumerate(entries):
                target.execute(
                    text(
                        """
                        INSERT INTO resume_evidence (
                            resume_id, evidence_type, sequence_no, title,
                            organization, summary, raw_payload
                        ) VALUES (
                            :resume_id, :evidence_type, :sequence_no, :title,
                            :organization, :summary, CAST(:raw_payload AS JSONB)
                        )
                        """
                    ),
                    {
                        "resume_id": row["id"],
                        "evidence_type": evidence_type,
                        "sequence_no": sequence_no,
                        "title": entry.get(title_key, ""),
                        "organization": entry.get(organization_key) if organization_key else None,
                        "summary": entry.get(summary_key, ""),
                        "raw_payload": canonical_json(entry),
                    },
                )


def reset_sequences(target: Connection, table_names: Iterable[str]) -> None:
    for table_name in table_names:
        if not re.fullmatch(r"[a-z_]+", table_name):
            raise ValueError(f"Unsafe table name: {table_name!r}")
        target.execute(
            text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{table_name}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table_name}), 1),
                    EXISTS (SELECT 1 FROM {table_name})
                )
                """
            )
        )


def assert_empty_target(target: Connection) -> None:
    occupied = {}
    for table_name in ("job_postings", "interview_questions", "migration_legacy_rows"):
        count = int(target.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one())
        if count:
            occupied[table_name] = count
    if occupied:
        raise RuntimeError(f"Target database is not empty; migration refused: {occupied}")


def run_migration(source_path: Path, target_url: str) -> dict[str, int]:
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", target_url)
    command.upgrade(alembic_config, "head")

    source = sqlite3.connect(source_path.resolve().as_uri() + "?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"Source SQLite integrity check failed: {integrity}")

    engine = create_engine(target_url, future=True)
    with engine.begin() as target:
        assert_empty_target(target)
        legacy_counts = archive_legacy_rows(source, target)
        company_ids, industry_ids, source_ids = migrate_reference_data(source, target)
        role_ids = seed_roles(target)
        skill_ids: dict[str, int] = {}
        migrate_jobs(source, target, company_ids, source_ids, skill_ids)
        migrate_questions(source, target, company_ids, role_ids, skill_ids)
        migrate_users(source, target, role_ids, industry_ids, skill_ids)
        reset_sequences(
            target,
            (
                "companies",
                "industries",
                "job_sources",
                "roles",
                "skills",
                "job_postings",
                "job_versions",
                "interview_questions",
                "users",
                "resumes",
            ),
        )
    source.close()
    return legacy_counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate CareerPilot SQLite data to PostgreSQL.")
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to an archived SQLite source database outside the runtime project.",
    )
    parser.add_argument("--target-url", required=True)
    args = parser.parse_args()
    started_at = datetime.now(timezone.utc)
    counts = run_migration(args.source, args.target_url)
    print(canonical_json({"status": "ok", "started_at": started_at.isoformat(), "rows": counts}))


if __name__ == "__main__":
    main()
