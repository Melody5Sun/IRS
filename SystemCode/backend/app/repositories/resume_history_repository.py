from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sqlalchemy import text

from app.db.postgres import get_postgres_engine
from app.db.sqlite import connect, initialize_database
from app.schemas.resume import ParsedResume, ResumeHistoryEntry


class ResumeHistoryRepository:
    """单用户部署：保留每次上传解析的简历，供用户挑选历史版本套用到当前画像。"""

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

    def add(self, parsed: ParsedResume, filename: str | None) -> int:
        if self._use_postgres:
            return self._add_postgres(parsed, filename)
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO resume_uploads (filename, resume_json, uploaded_at) VALUES (?, ?, ?)",
                (filename, parsed.model_dump_json(), datetime.now(timezone.utc).isoformat()),
            )
            return cursor.lastrowid

    def list(self) -> list[ResumeHistoryEntry]:
        if self._use_postgres:
            with get_postgres_engine().connect() as connection:
                rows = connection.execute(
                    text(
                        """
                        SELECT id, filename, resume_json, uploaded_at
                        FROM resume_uploads
                        ORDER BY id DESC
                        """
                    )
                ).mappings().all()
            return [
                ResumeHistoryEntry(
                    id=row["id"],
                    filename=row["filename"],
                    name=ParsedResume.model_validate_json(row["resume_json"]).name,
                    uploaded_at=row["uploaded_at"],
                )
                for row in rows
            ]
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, filename, resume_json, uploaded_at FROM resume_uploads ORDER BY id DESC"
            ).fetchall()
        return [
            ResumeHistoryEntry(
                id=row["id"],
                filename=row["filename"],
                name=ParsedResume.model_validate_json(row["resume_json"]).name,
                uploaded_at=row["uploaded_at"],
            )
            for row in rows
        ]

    def get(self, history_id: int) -> ParsedResume | None:
        if self._use_postgres:
            with get_postgres_engine().connect() as connection:
                payload = connection.execute(
                    text(
                        """
                        SELECT resume_json
                        FROM resume_uploads
                        WHERE id = :history_id
                        """
                    ),
                    {"history_id": history_id},
                ).scalar_one_or_none()
            return ParsedResume.model_validate_json(payload) if payload else None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT resume_json FROM resume_uploads WHERE id = ?", (history_id,)
            ).fetchone()
        return ParsedResume.model_validate_json(row["resume_json"]) if row else None

    @staticmethod
    def _add_postgres(parsed: ParsedResume, filename: str | None) -> int:
        uploaded_at = datetime.now(timezone.utc)
        with get_postgres_engine().begin() as connection:
            return int(
                connection.execute(
                    text(
                        """
                        INSERT INTO resume_uploads (
                            filename, resume_json, uploaded_at
                        ) VALUES (:filename, :resume_json, :uploaded_at)
                        RETURNING id
                        """
                    ),
                    {
                        "filename": filename,
                        "resume_json": parsed.model_dump_json(),
                        "uploaded_at": uploaded_at.isoformat(),
                    },
                ).scalar_one()
            )
