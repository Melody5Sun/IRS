from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sqlalchemy import text

from app.db.postgres import get_postgres_engine
from app.db.sqlite import connect, initialize_database
from app.repositories.postgres_helpers import ensure_role, ensure_single_user
from app.schemas.profile import JobSearchConstraints, UserProfile
from app.schemas.resume import ParsedResume, ResumeDocument

# 用户提交画像时允许留空的字段（补充说明选填、证书永久有效、交换项目没有专业、个人项目没有角色）
OPTIONAL_FIELDS = {"notes", "expiry_date", "major", "role"}
# 可以一条都不填的列表（学生可能没有）；但只要填了条目，条目里的字段仍要完整
OPTIONAL_LISTS = {"experiences", "projects", "research", "certificates"}

Loc = list[str | int]


def _is_blank(value: object) -> bool:
    # not_stated 是 LLM 解析不出来时的占位，用户手动提交时视同没填
    return value is None or value == "not_stated" or (isinstance(value, str) and not value.strip())


def merge_patch(base: dict[str, object], patch: dict[str, object]) -> dict[str, object]:
    """类似 JSON Merge Patch：patch 里的 key 覆盖 base，双方都是 dict 才递归合并，否则整体替换（含列表）。"""
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_patch(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


def find_empty_fields(data: dict[str, object], loc: Loc | None = None) -> list[Loc]:
    """返回不允许为空却为空的字段位置，比如 ["resume", "experiences", 0, "country"]。"""
    loc = loc or []
    empty: list[Loc] = []
    for key, value in data.items():
        if key in OPTIONAL_FIELDS:
            continue
        field_loc = [*loc, key]
        if isinstance(value, dict):
            empty += find_empty_fields(value, field_loc)
        elif isinstance(value, list):
            if not value and key not in OPTIONAL_LISTS:
                empty.append(field_loc)
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    empty += find_empty_fields(item, [*field_loc, index])
                elif _is_blank(item):
                    empty.append([*field_loc, index])
        elif _is_blank(value):
            empty.append(field_loc)
    return empty


class ProfileService:
    """本地部署只有一个用户，只保存一份画像，持久化在 user_profile 表的单行（id 固定为 1）。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path
        # 延迟到第一次真正访问数据库时才建表/迁移，避免 import app 时就改写 data/careerpilot.db
        self._initialized = False
        self._profile: UserProfile | None = None
        self._loaded = False

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

    @property
    def profile(self) -> UserProfile | None:
        if not self._loaded:
            if self._use_postgres:
                with get_postgres_engine().connect() as connection:
                    payload = connection.execute(
                        text("SELECT profile_payload FROM user_profiles WHERE user_id = 1")
                    ).scalar_one_or_none()
                self._profile = UserProfile.model_validate(payload) if payload else None
            else:
                with self._connect() as connection:
                    row = connection.execute(
                        "SELECT profile_json FROM user_profile WHERE id = 1"
                    ).fetchone()
                self._profile = UserProfile.model_validate_json(row["profile_json"]) if row else None
            self._loaded = True
        return self._profile

    @profile.setter
    def profile(self, value: UserProfile | None) -> None:
        if self._use_postgres:
            self._save_postgres_profile(value)
            self._profile = value
            self._loaded = True
            return
        with self._connect() as connection:
            if value is None:
                connection.execute("DELETE FROM user_profile WHERE id = 1")
            else:
                connection.execute(
                    """
                    INSERT INTO user_profile (id, profile_json, updated_at)
                    VALUES (1, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        profile_json = excluded.profile_json,
                        updated_at = excluded.updated_at
                    """,
                    (value.model_dump_json(), datetime.now(timezone.utc).isoformat()),
                )
        self._profile = value
        self._loaded = True

    @staticmethod
    def _save_postgres_profile(value: UserProfile | None) -> None:
        with get_postgres_engine().begin() as connection:
            user_id = ensure_single_user(connection)
            if value is None:
                connection.execute(
                    text("DELETE FROM user_profiles WHERE user_id = :user_id"),
                    {"user_id": user_id},
                )
                connection.execute(
                    text("DELETE FROM user_target_roles WHERE user_id = :user_id"),
                    {"user_id": user_id},
                )
                connection.execute(
                    text("DELETE FROM user_target_industries WHERE user_id = :user_id"),
                    {"user_id": user_id},
                )
                return
            connection.execute(
                text(
                    """
                    INSERT INTO user_profiles (user_id, profile_payload, notes)
                    VALUES (:user_id, CAST(:payload AS JSONB), :notes)
                    ON CONFLICT (user_id) DO UPDATE SET
                        profile_payload = EXCLUDED.profile_payload,
                        notes = EXCLUDED.notes,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {
                    "user_id": user_id,
                    "payload": value.model_dump_json(),
                    "notes": value.constraints.notes,
                },
            )
            connection.execute(
                text("DELETE FROM user_target_roles WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            for priority, role_name in enumerate(value.constraints.target_roles, start=1):
                connection.execute(
                    text(
                        """
                        INSERT INTO user_target_roles (user_id, role_id, priority)
                        VALUES (:user_id, :role_id, :priority)
                        """
                    ),
                    {
                        "user_id": user_id,
                        "role_id": ensure_role(connection, role_name),
                        "priority": priority,
                    },
                )
            connection.execute(
                text("DELETE FROM user_target_industries WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            for industry_name in value.constraints.target_industries:
                industry_id = connection.execute(
                    text("SELECT id FROM industries WHERE name = :name"),
                    {"name": industry_name},
                ).scalar_one()
                connection.execute(
                    text(
                        """
                        INSERT INTO user_target_industries (user_id, industry_id)
                        VALUES (:user_id, :industry_id)
                        """
                    ),
                    {"user_id": user_id, "industry_id": industry_id},
                )

    def save_resume(self, parsed: ParsedResume) -> None:
        # 重新上传简历时只替换画像，已经填写的求职约束保留
        constraints = self.profile.constraints if self.profile else JobSearchConstraints()
        # 简历里的自我介绍合并进补充说明；用户已经写过 notes 就不覆盖
        if parsed.about and not constraints.notes.strip():
            constraints = constraints.model_copy(update={"notes": parsed.about})
        resume = ResumeDocument.model_validate(parsed.model_dump(exclude={"about"}))
        self.profile = UserProfile(resume=resume, constraints=constraints)


# resumes 和 profile 两个路由共用同一份画像
profile_service = ProfileService()
