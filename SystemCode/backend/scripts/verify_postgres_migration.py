from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from sqlalchemy import create_engine, text

try:
    from scripts.migrate_sqlite_to_postgres import (
        LEGACY_TABLE_KEYS,
        canonical_json,
        parse_json,
        sqlite_rows,
    )
except ModuleNotFoundError:  # Support `python scripts/verify_postgres_migration.py`.
    from migrate_sqlite_to_postgres import (  # type: ignore[no-redef]
        LEGACY_TABLE_KEYS,
        canonical_json,
        parse_json,
        sqlite_rows,
    )


def source_metrics(source: sqlite3.Connection) -> dict[str, int]:
    analyses = sqlite_rows(source, "job_analysis")
    questions = sqlite_rows(source, "interview_questions")
    resumes = sqlite_rows(source, "resume_uploads")
    return {
        "job_postings": source.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
        "job_analyses": len(analyses),
        "job_responsibilities": sum(
            len(parse_json(row["responsibilities_json"], [])) for row in analyses
        ),
        "job_skill_requirements": sum(
            len(parse_json(row["required_skills_json"], []))
            + len(parse_json(row["preferred_skills_json"], []))
            for row in analyses
        ),
        "interview_questions": len(questions),
        "question_sources": len(questions),
        "resume_uploads": len(resumes),
    }


def archive_hashes(source: sqlite3.Connection) -> dict[tuple[str, str], str]:
    hashes: dict[tuple[str, str], str] = {}
    for table_name, key_name in LEGACY_TABLE_KEYS.items():
        for row in sqlite_rows(source, table_name):
            payload = canonical_json(row)
            hashes[(table_name, str(row[key_name]))] = hashlib.sha256(
                payload.encode("utf-8")
            ).hexdigest()
    return hashes


def verify(source_path: Path, target_url: str) -> dict[str, Any]:
    source = sqlite3.connect(source_path.resolve().as_uri() + "?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("Source SQLite database failed integrity_check.")

    expected_metrics = source_metrics(source)
    expected_hashes = archive_hashes(source)
    engine = create_engine(target_url, future=True)
    with engine.connect() as target:
        actual_metrics = {
            table_name: int(target.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one())
            for table_name in (
                "job_postings",
                "job_analyses",
                "job_responsibilities",
                "job_skill_requirements",
                "interview_questions",
                "question_sources",
            )
        }
        actual_metrics["resume_uploads"] = int(
            target.execute(text("SELECT COUNT(*) FROM resume_uploads")).scalar_one()
        )
        actual_hashes = {
            (row.source_table, row.source_primary_key): row.row_sha256
            for row in target.execute(
                text(
                    """
                    SELECT source_table, source_primary_key, row_sha256
                    FROM migration_legacy_rows
                    """
                )
            )
        }
        orphan_checks = {
            "analyses_without_job": """
                SELECT COUNT(*) FROM job_analyses a
                LEFT JOIN job_postings j ON j.id = a.job_id WHERE j.id IS NULL
            """,
            "questions_without_source": """
                SELECT COUNT(*) FROM interview_questions q
                LEFT JOIN question_sources s ON s.question_id = q.id WHERE s.id IS NULL
            """,
        }
        orphan_counts = {
            name: int(target.execute(text(sql)).scalar_one())
            for name, sql in orphan_checks.items()
        }

    source.close()
    metric_mismatches = {
        name: {"expected": expected, "actual": actual_metrics.get(name)}
        for name, expected in expected_metrics.items()
        if actual_metrics.get(name) != expected
    }
    missing_archive_rows = sorted(set(expected_hashes) - set(actual_hashes))
    extra_archive_rows = sorted(set(actual_hashes) - set(expected_hashes))
    hash_mismatches = sorted(
        key
        for key in set(expected_hashes) & set(actual_hashes)
        if expected_hashes[key] != actual_hashes[key]
    )
    passed = not (
        metric_mismatches
        or missing_archive_rows
        or extra_archive_rows
        or hash_mismatches
        or any(orphan_counts.values())
    )
    return {
        "passed": passed,
        "metrics": actual_metrics,
        "metric_mismatches": metric_mismatches,
        "archive_rows": len(actual_hashes),
        "missing_archive_rows": missing_archive_rows,
        "extra_archive_rows": extra_archive_rows,
        "hash_mismatches": hash_mismatches,
        "orphan_counts": orphan_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the CareerPilot PostgreSQL migration.")
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to the archived SQLite source used for verification.",
    )
    parser.add_argument("--target-url", required=True)
    args = parser.parse_args()
    report = verify(args.source, args.target_url)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
