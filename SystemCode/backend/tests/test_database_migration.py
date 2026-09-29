import json
import sqlite3

from scripts.migrate_sqlite_to_postgres import canonical_json, normalized_name
from scripts.verify_sqlite_backup import compare


def _create_legacy_database(path, question_text: str = "What is Python?") -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE jobs (id INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE company_sources (name TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE industries (name TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE company_industries (normalized_company TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE job_analysis (job_id INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE user_profile (id INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE resume_uploads (id INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE interview_questions (id INTEGER PRIMARY KEY, value TEXT);
        """
    )
    connection.execute("INSERT INTO jobs VALUES (1, 'job')")
    connection.execute("INSERT INTO company_sources VALUES ('source', 'source')")
    connection.execute("INSERT INTO industries VALUES ('industry', 'industry')")
    connection.execute("INSERT INTO company_industries VALUES ('company', 'company')")
    connection.execute("INSERT INTO job_analysis VALUES (1, 'analysis')")
    connection.execute("INSERT INTO user_profile VALUES (1, 'profile')")
    connection.execute("INSERT INTO resume_uploads VALUES (1, 'resume')")
    connection.execute("INSERT INTO interview_questions VALUES (1, ?)", (question_text,))
    connection.commit()
    connection.close()


def test_canonical_json_is_stable() -> None:
    left = canonical_json({"skills": ["Python", "SQL"], "id": 1})
    right = canonical_json(json.loads('{"id": 1, "skills": ["Python", "SQL"]}'))
    assert left == right


def test_normalized_name_is_case_and_punctuation_insensitive() -> None:
    assert normalized_name("  NCS Group (Singapore) ") == "ncs group singapore"


def test_sqlite_backup_comparison_detects_no_changes(tmp_path) -> None:
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    _create_legacy_database(source)
    source_connection = sqlite3.connect(source)
    backup_connection = sqlite3.connect(backup)
    source_connection.backup(backup_connection)
    source_connection.close()
    backup_connection.close()

    report = compare(source, backup)

    assert report["passed"] is True
    assert report["source_rows"] == 8


def test_sqlite_backup_comparison_detects_changed_row(tmp_path) -> None:
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    _create_legacy_database(source)
    _create_legacy_database(backup, question_text="Changed")

    report = compare(source, backup)

    assert report["passed"] is False
    assert report["changed"] == [("interview_questions", "1")]
