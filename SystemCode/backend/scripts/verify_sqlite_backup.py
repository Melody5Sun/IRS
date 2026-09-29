from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3

try:
    from scripts.verify_postgres_migration import archive_hashes
except ModuleNotFoundError:  # Support `python scripts/verify_sqlite_backup.py`.
    from verify_postgres_migration import archive_hashes  # type: ignore[no-redef]


def open_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def schema_signature(connection: sqlite3.Connection) -> list[tuple[str, str | None]]:
    return [
        (row["name"], row["sql"])
        for row in connection.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type IN ('table', 'index') AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
    ]


def compare(source_path: Path, backup_path: Path) -> dict:
    source = open_read_only(source_path)
    backup = open_read_only(backup_path)
    try:
        source_hashes = archive_hashes(source)
        backup_hashes = archive_hashes(backup)
        missing = sorted(set(backup_hashes) - set(source_hashes))
        extra = sorted(set(source_hashes) - set(backup_hashes))
        changed = sorted(
            key
            for key in set(source_hashes) & set(backup_hashes)
            if source_hashes[key] != backup_hashes[key]
        )
        schema_equal = schema_signature(source) == schema_signature(backup)
        return {
            "passed": not (missing or extra or changed) and schema_equal,
            "source_rows": len(source_hashes),
            "backup_rows": len(backup_hashes),
            "missing": missing,
            "extra": extra,
            "changed": changed,
            "schema_equal": schema_equal,
        }
    finally:
        source.close()
        backup.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare a SQLite database with its backup.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.source, args.backup)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
