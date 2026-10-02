from sqlalchemy import text

from app.db.postgres import get_postgres_engine
from app.schemas.profile import UserProfile
from app.schemas.resume import ParsedResume, ResumeHistoryEntry


class ResumeHistoryRepository:
    """resume_uploads 表：保留每次上传解析的简历，供用户挑选历史版本套用到当前画像。"""

    def add(self, parsed: ParsedResume, filename: str | None) -> int:
        with get_postgres_engine().begin() as connection:
            return connection.execute(
                text(
                    """
                    INSERT INTO resume_uploads (filename, resume_json)
                    VALUES (:filename, CAST(:resume_json AS JSONB))
                    RETURNING id
                    """
                ),
                {"filename": filename, "resume_json": parsed.model_dump_json()},
            ).scalar_one()

    def list(self) -> list[ResumeHistoryEntry]:
        # 名字直接在 SQL 里从 JSONB 取，不用把整份简历读回来
        with get_postgres_engine().connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT id, filename, resume_json ->> 'name' AS name, uploaded_at
                    FROM resume_uploads
                    ORDER BY id DESC
                    """
                )
            ).mappings().all()
        return [ResumeHistoryEntry.model_validate(dict(row)) for row in rows]

    def get(self, history_id: int) -> ParsedResume | None:
        with get_postgres_engine().connect() as connection:
            payload = connection.execute(
                text("SELECT resume_json FROM resume_uploads WHERE id = :id"),
                {"id": history_id},
            ).scalar_one_or_none()
        return ParsedResume.model_validate(payload) if payload is not None else None


class ProfileRepository:
    """user_profile 表：单用户部署只有一行（id 固定为 1），resume / constraints 两列合起来就是完整画像。"""

    def get(self) -> UserProfile | None:
        with get_postgres_engine().connect() as connection:
            row = connection.execute(
                text("SELECT resume, constraints FROM user_profile WHERE id = 1")
            ).mappings().one_or_none()
        return UserProfile.model_validate(dict(row)) if row else None

    def save(self, profile: UserProfile) -> None:
        with get_postgres_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO user_profile (id, resume, constraints)
                    VALUES (1, CAST(:resume AS JSONB), CAST(:constraints AS JSONB))
                    ON CONFLICT (id) DO UPDATE SET
                        resume = EXCLUDED.resume,
                        constraints = EXCLUDED.constraints,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {
                    "resume": profile.resume.model_dump_json(),
                    "constraints": profile.constraints.model_dump_json(),
                },
            )
