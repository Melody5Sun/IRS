from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from job_db import API_JOBS, make_rows

from app.api.routes import profile as profile_route
from app.api.routes import ranking as ranking_route
from app.api.routes import resumes as resumes_route
from app.api.routes import rules_screening as rules_screening_route
from app.api.routes import targets as targets_route
from app.main import app
from app.rule_engine import engine as rule_engine
from app.schemas.profile import SavedProfile, UserProfile
from app.schemas.resume import ParsedResume, ResumeDocument, ResumeHistoryEntry, ResumeUpload
from app.services.career_intent_match_service import CareerIntentMatchService
from app.services.profile_service import ProfileService
from app.services.ranking_service import RankingService
from app.services.responsibility_match_service import ResponsibilityMatchService
from app.services.rules_screening_service import RulesScreeningService
from app.services.skill_match_service import SkillMatchService


class FakeProfileRepository:
    """代替 user_profile 表：只存一份画像。"""

    def __init__(self) -> None:
        self.profile: SavedProfile | None = None

    def get(self) -> SavedProfile | None:
        return self.profile

    def save(self, profile: UserProfile) -> SavedProfile:
        self.profile = SavedProfile.model_validate({**profile.model_dump(), "updated_at": datetime.now(timezone.utc)})
        return self.profile


class FakeResumeHistoryRepository:
    """代替 resume_uploads 表：按上传顺序存解析结果，id 从 1 开始。"""

    def __init__(self) -> None:
        self.uploads: list[tuple[str | None, ParsedResume]] = []

    def add(self, parsed: ParsedResume, filename: str | None) -> int:
        self.uploads.append((filename, parsed))
        return len(self.uploads)

    def list(self) -> list[ResumeHistoryEntry]:
        return [
            ResumeHistoryEntry(
                id=index, filename=filename, name=parsed.name, uploaded_at=datetime.now(timezone.utc)
            )
            for index, (filename, parsed) in reversed(list(enumerate(self.uploads, start=1)))
        ]

    def get(self, history_id: int) -> ResumeUpload | None:
        if not 1 <= history_id <= len(self.uploads):
            return None
        filename, parsed = self.uploads[history_id - 1]
        return ResumeUpload(
            id=history_id, filename=filename, name=parsed.name, uploaded_at=datetime.now(timezone.utc), resume=parsed
        )

    def update(self, history_id: int, resume: ResumeDocument) -> bool:
        # 和真实仓库的 JSONB || 一样：覆盖简历字段，保留 about
        if not 1 <= history_id <= len(self.uploads):
            return False
        filename, parsed = self.uploads[history_id - 1]
        merged = ParsedResume.model_validate({**parsed.model_dump(), **resume.model_dump()})
        self.uploads[history_id - 1] = (filename, merged)
        return True


@pytest.fixture
def screening_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """rules-screening / ranking 读的岗位换成 API_JOBS，JD 语义不落库，不碰真实 PostgreSQL。"""
    monkeypatch.setattr(rule_engine, "load_job_rows", lambda: make_rows(*API_JOBS))
    rules_service = RulesScreeningService()
    monkeypatch.setattr(rules_screening_route, "rules_screening_service", rules_service)
    monkeypatch.setattr(
        ranking_route,
        "ranking_service",
        RankingService(
            rules_service,
            SkillMatchService(),
            ResponsibilityMatchService(persist=False),
            CareerIntentMatchService(persist=False),
        ),
    )
    return TestClient(app)


@pytest.fixture(autouse=True)
def profile_service(monkeypatch: pytest.MonkeyPatch) -> ProfileService:
    """画像 / 简历历史 / 排序 / 目标岗位路由共用的服务换成注入 Fake 仓库的新实例，每个测试从空画像开始，不碰真实 PostgreSQL。"""
    service = ProfileService(FakeProfileRepository(), FakeResumeHistoryRepository())
    monkeypatch.setattr(profile_route, "profile_service", service)
    monkeypatch.setattr(resumes_route, "profile_service", service)
    monkeypatch.setattr(ranking_route, "profile_service", service)
    monkeypatch.setattr(targets_route, "profile_service", service)
    return service
