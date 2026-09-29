from pathlib import Path
import sqlite3


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(db_path: Path) -> None:
    with connect(db_path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.execute("DROP INDEX IF EXISTS idx_jobs_deadline_at")
        for column_name in ("deadline_at", "posted_at"):
            _drop_column_if_exists(connection, "jobs", column_name)
        for column_name in (
            "required_languages_json",
            "location_json",
            "min_experience_years",
            "seniority_level",
            "visa_sponsorship",
            "work_authorization_notes",
            "industry",
            "analysis_version",
            "analysis_method",
            "analyzed_at",
        ):
            _drop_column_if_exists(connection, "job_analysis", column_name)
        _drop_column_if_exists(connection, "interview_questions", "published_at")
        for column_name in ("question_text_en", "standard_answer_en"):
            _add_column_if_not_exists(connection, "interview_questions", column_name, "TEXT")
        _migrate_interview_role_to_roles_json(connection)
        _remove_analysis_json_fields(
            connection,
            "seniority_level",
            "visa_sponsorship",
            "work_authorization_notes",
            "industry",
            "analysis_version",
            "analysis_method",
            "analyzed_at",
        )
        _backfill_company_industries(connection)


def _drop_column_if_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name in columns:
        connection.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")


def _add_column_if_not_exists(
    connection: sqlite3.Connection, table_name: str, column_name: str, column_type: str
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _migrate_interview_role_to_roles_json(connection: sqlite3.Connection) -> None:
    # 旧库的 role 是单值文本列，改为 roles_json（JSON 数组）；先把旧值搬过去再删列，避免丢数据
    _add_column_if_not_exists(
        connection, "interview_questions", "roles_json", "TEXT NOT NULL DEFAULT '[]'"
    )
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(interview_questions)").fetchall()
    }
    if "role" in columns:
        connection.execute(
            "UPDATE interview_questions SET roles_json = json_array(role) WHERE role IS NOT NULL"
        )
        connection.execute("ALTER TABLE interview_questions DROP COLUMN role")


def _remove_analysis_json_fields(connection: sqlite3.Connection, *field_names: str) -> None:
    import json

    rows = connection.execute("SELECT job_id, analysis_json FROM job_analysis").fetchall()
    for row in rows:
        try:
            payload = json.loads(row["analysis_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        changed = False
        for field_name in field_names:
            if field_name in payload:
                del payload[field_name]
                changed = True
        if changed:
            connection.execute(
                "UPDATE job_analysis SET analysis_json = ? WHERE job_id = ?",
                (json.dumps(payload, ensure_ascii=False), row["job_id"]),
            )


def _backfill_company_industries(connection: sqlite3.Connection) -> None:
    from app.parsers.job_industry_classifier import (
        classify_company_industry,
        normalize_company_name,
    )

    rows = connection.execute(
        """
        SELECT DISTINCT company
        FROM jobs
        WHERE TRIM(company) <> ''
        """
    ).fetchall()
    for row in rows:
        company = row["company"]
        connection.execute(
            """
            INSERT INTO company_industries (normalized_company, company, industry)
            VALUES (?, ?, ?)
            ON CONFLICT(normalized_company) DO UPDATE SET
                company = excluded.company,
                industry = excluded.industry
            """,
            (
                normalize_company_name(company),
                company,
                classify_company_industry(company),
            ),
        )
