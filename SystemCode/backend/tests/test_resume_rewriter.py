import json

import pytest
from fastapi.testclient import TestClient

from app.api.routes import resumes as resumes_route
from app.main import app
from app.matching.responsibility_scorer import ResponsibilityScorer
from app.repositories.resume_guideline_repository import GuidelineMatch
from app.resume.resume_rewriter import ISSUE_QUERIES, ResumeRewriteError, ResumeRewriter
from app.schemas.job import JobRequirementDocument
from app.schemas.profile import UserProfile
from app.schemas.resume import Experience, ParsedResume, Project, ResumeDocument, SkillGroup
from app.schemas.resume_guideline import ResumeGuideline
from app.schemas.resume_rewrite import SavedResumeRewrite
from app.services.responsibility_match_service import ResponsibilityMatchService

DESCRIPTION = "Responsible for building REST APIs with Python and FastAPI.\nWrote weekly reports for the team."
PROJECT_SUMMARY = "A personal photo blog about travel."
REASON = {"issue_type": "weak_action_verb", "explanation": {"en": "Start with a verb.", "zh": "用动词开头。"}}


class FakeChatClient:
    """按顺序返回预设输出，记录调用次数。"""

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls = 0
        self.prompts: list[str] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        self.prompts.append(user_prompt)
        return self.responses.pop(0)


class FakeEmbeddingProvider:
    # 照片博客项目和 JD 职责正交（相似度 0，判为无关），其余文本都与职责同向；记录编码过的文本
    def __init__(self) -> None:
        self.texts: list[str] = []

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.texts += texts
        return [[0.0, 1.0] if "photo blog" in text else [1.0, 0.0] for text in texts]


class FakeGuidelineRepository:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.guideline = ResumeGuideline(
            key="action-verb-01", source="tech-interview-handbook", title="Lead with a strong verb",
            guideline="Start each bullet with an action verb.", rationale="Recruiters skim the first word.",
            examples=[{"before": "Responsible for APIs", "after": "Built APIs"}],
            sections=["experience", "project"], issue_types=["weak_action_verb"],
        )

    def search(self, query_embedding, **kwargs) -> list[GuidelineMatch]:
        self.calls.append(kwargs)
        return [GuidelineMatch(self.guideline, 0.8, "example", "Responsible for APIs")]


def _resume() -> ResumeDocument:
    return ResumeDocument(
        name="Test Candidate",
        experiences=[Experience(company="Acme", title="Backend Intern", start_date="2025-05", description=DESCRIPTION)],
        projects=[Project(title="Photo Blog", summary=PROJECT_SUMMARY)],
        skills=["Python", "FastAPI"],
        skill_groups=[SkillGroup(category="Backend", description="Python, FastAPI")],
    )


def _job() -> JobRequirementDocument:
    return JobRequirementDocument(
        job_id=7, company="Shopee", title="Backend Engineer",
        responsibilities=["Build REST APIs in Python"], required_skills=["python", "fastapi"],
    )


def _rewriter(client: FakeChatClient, repository: FakeGuidelineRepository) -> ResumeRewriter:
    provider = FakeEmbeddingProvider()
    return ResumeRewriter(
        client=client,
        guideline_repository=repository,
        embedding_provider=provider,
        responsibility_service=ResponsibilityMatchService(scorer=ResponsibilityScorer(provider), persist=False),
    )


def test_rewrite_applies_changes_filters_keys_and_returns_deletions() -> None:
    change_set = {
        "changes": [{
            "section": "experience", "index": 0, "field": "description", "original": DESCRIPTION,
            "value": "Built REST APIs with Python and FastAPI serving [number of users] users.\n"
                     "Wrote weekly reports for the team.",
            "reasons": [{**REASON, "guideline_keys": ["action-verb-01", "made-up-99"]}],
            "needs_user_input": [{
                "placeholder": "[number of users]",
                "question": {"en": "How many users?", "zh": "服务了多少用户？"},
                "reason": {"en": "Scale shows impact.", "zh": "规模体现影响。"},
            }],
        }],
        "deletions": [
            {"section": "project", "index": 0, "line": None, "original": PROJECT_SUMMARY,
             "reasons": [{**REASON, "issue_type": "irrelevant_content", "guideline_keys": ["action-verb-01"]}]},
            # 经历与 JD 高度相关，删除建议应被拒绝
            {"section": "experience", "index": 0, "line": 1, "original": "Wrote weekly reports for the team.",
             "reasons": [{**REASON, "issue_type": "irrelevant_content"}]},
        ],
    }
    client = FakeChatClient("not json", json.dumps(change_set))
    repository = FakeGuidelineRepository()

    result = _rewriter(client, repository).rewrite(_resume(), _job(), ["Software Development"])

    assert client.calls == 2  # 第一次非法 JSON，重试一次
    assert all(call["role_categories"] == ["Software Development"] for call in repository.calls)
    assert result.job_id == 7
    assert result.rejected_changes == []
    change = result.blocks[0].changes[0]
    assert change.reasons[0].guideline_keys == ["action-verb-01"]  # 编造的 key 被丢掉
    assert change.needs_user_input[0].placeholder == "[number of users]"
    assert result.rewritten_resume.experiences[0].description.startswith("Built REST APIs")
    assert [g.key for g in result.guidelines] == ["action-verb-01"]
    # 删除建议不应用到改写稿
    assert [(d.section, d.index) for d in result.deletion_suggestions] == [("project", 0)]
    assert result.rewritten_resume.projects[0].summary == PROJECT_SUMMARY
    assert len(result.rejected_deletions) == 1


def test_rewrite_raises_after_two_invalid_outputs() -> None:
    with pytest.raises(ResumeRewriteError):
        _rewriter(FakeChatClient("bad", "still bad"), FakeGuidelineRepository()).rewrite(_resume(), _job(), [])


class IssueKeyedGuidelineRepository:
    """每个问题类型返回一条只带该标签的条目（key = g-<问题类型>），记录每次检索带的问题类型。"""

    def __init__(self) -> None:
        self.issue_types: list[list[str]] = []

    def search(self, query_embedding, *, issue_types, **kwargs) -> list[GuidelineMatch]:
        self.issue_types.append(issue_types)
        issue = issue_types[0]
        guideline = ResumeGuideline(
            key=f"g-{issue}", source="tech-interview-handbook", title=issue, guideline="g", rationale="r",
            examples=[{"before": "b", "after": "a"}],
            sections=["experience", "project", "research", "skills"], issue_types=[issue],
        )
        return [GuidelineMatch(guideline, 0.5, "guideline", "g")]


def test_retrieval_is_per_issue_type_and_citations_must_match_the_reason() -> None:
    change_set = {"changes": [{
        "section": "experience", "index": 0, "field": "description", "original": DESCRIPTION,
        "value": "Built REST APIs with Python and FastAPI.\nWrote weekly reports for the team.",
        # 弱动词理由引用了缺结果分组下的条目，应被丢掉
        "reasons": [{**REASON, "guideline_keys": ["g-weak_action_verb", "g-missing_outcome"]}],
    }]}
    client = FakeChatClient(json.dumps(change_set))
    repository = IssueKeyedGuidelineRepository()

    rewriter = _rewriter(client, repository)
    result = rewriter.rewrite(_resume(), _job(), [])

    assert all(len(issue_types) == 1 for issue_types in repository.issue_types)
    # 写法类问题除了用原文，还用问题描述再检索一次
    assert ISSUE_QUERIES["weak_action_verb"] in rewriter.embedding_provider.texts
    blocks = json.loads(client.prompts[0])["BLOCKS"]
    experience = next(b for b in blocks if b["section"] == "experience")
    # 每个检测到的问题都有自己的一组条目
    assert {"weak_action_verb", "missing_quantification", "missing_outcome"} <= set(experience["guidelines"])
    assert experience["guidelines"]["weak_action_verb"][0]["key"] == "g-weak_action_verb"
    assert result.blocks[0].changes[0].reasons[0].guideline_keys == ["g-weak_action_verb"]


class FakeRewriteRepository:
    """代替 resume_rewrites 表。"""

    def __init__(self) -> None:
        self.rows: dict[tuple[int, int], tuple[ResumeDocument, str]] = {}

    def save(self, resume_upload_id: int, job_id: int, resume: ResumeDocument, source_hash: str) -> SavedResumeRewrite:
        self.rows[(resume_upload_id, job_id)] = (resume, source_hash)
        return SavedResumeRewrite(resume=resume, stale=False, updated_at="2026-10-02T00:00:00Z")

    def get(self, resume_upload_id: int, job_id: int, current_hash: str) -> SavedResumeRewrite | None:
        if (resume_upload_id, job_id) not in self.rows:
            return None
        resume, source_hash = self.rows[(resume_upload_id, job_id)]
        return SavedResumeRewrite(resume=resume, stale=source_hash != current_hash, updated_at="2026-10-02T00:00:00Z")


class FakeJobRepository:
    def get_job(self, job_id: int) -> object | None:
        return object() if job_id == 7 else None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(resumes_route, "rewrite_repository", FakeRewriteRepository())
    monkeypatch.setattr(resumes_route, "job_repository", FakeJobRepository())
    return TestClient(app)


def _save_profile(profile_service, upload_id: int, resume: ResumeDocument) -> None:
    while len(profile_service.resume_history.uploads) < upload_id:
        profile_service.resume_history.add(ParsedResume.model_validate(resume.model_dump()), "cv.pdf")
    assert profile_service.save(UserProfile(resume=resume, resume_upload_id=upload_id))


def test_rewrite_requires_saved_profile(client: TestClient) -> None:
    assert client.post("/api/resumes/rewrite", json={"job_id": 7}).status_code == 409
    assert client.get("/api/resumes/rewrites/7").status_code == 409


def test_saved_rewrite_round_trip_stale_and_per_resume(client: TestClient, profile_service) -> None:
    resume = _resume()
    _save_profile(profile_service, 1, resume)
    rewritten = resume.model_copy(update={"name": "Rewritten"})

    assert client.get("/api/resumes/rewrites/7").status_code == 404
    assert client.put("/api/resumes/rewrites/999", json=rewritten.model_dump()).status_code == 404
    assert client.put("/api/resumes/rewrites/7", json=rewritten.model_dump()).status_code == 200
    saved = client.get("/api/resumes/rewrites/7").json()
    assert saved["resume"]["name"] == "Rewritten" and saved["stale"] is False

    # 同一条上传记录的简历被修改后，改写稿保留但标记为过时
    _save_profile(profile_service, 1, resume.model_copy(update={"phone": "+65 0000 0000"}))
    saved = client.get("/api/resumes/rewrites/7").json()
    assert saved["resume"]["name"] == "Rewritten" and saved["stale"] is True

    # 画像换成另一份简历后，读不到旧简历的改写稿
    _save_profile(profile_service, 2, resume)
    assert client.get("/api/resumes/rewrites/7").status_code == 404
