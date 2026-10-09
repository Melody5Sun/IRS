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
from app.schemas.resume_rewrite import PlaceholderAnswer, RewriteSession, SavedResumeRewrite
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
    # 带占位的改动是待补充草稿：块标为 needs_input，改写后的简历保留原文，等 fill 补全后由前端回填
    assert result.blocks[0].status == "needs_input"
    assert result.blocks[0].pending_inputs == change.needs_user_input
    assert result.rewritten_resume.experiences[0].description == DESCRIPTION
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
        # (上传记录, 岗位) → [终稿, 改写对比, 哈希]
        self.rows: dict[tuple[int, int], list] = {}

    def save(self, resume_upload_id: int, job_id: int, resume: ResumeDocument, source_hash: str) -> SavedResumeRewrite:
        row = self.rows.setdefault((resume_upload_id, job_id), [None, None, source_hash])
        row[0], row[2] = resume, source_hash
        return SavedResumeRewrite(resume=resume, stale=False, updated_at="2026-10-02T00:00:00Z")

    def save_session(self, resume_upload_id: int, job_id: int, session: RewriteSession, source_hash: str) -> None:
        # 和真实 SQL 一样：已有记录只更新 session
        self.rows.setdefault((resume_upload_id, job_id), [None, None, source_hash])[1] = session

    def get(self, resume_upload_id: int, job_id: int, current_hash: str) -> SavedResumeRewrite | None:
        if (resume_upload_id, job_id) not in self.rows:
            return None
        resume, session, source_hash = self.rows[(resume_upload_id, job_id)]
        return SavedResumeRewrite(
            resume=resume, session=session, stale=source_hash != current_hash, updated_at="2026-10-02T00:00:00Z"
        )


class FakeJobRepository:
    """岗位 7、8 存在。"""

    def get_job(self, job_id: int) -> object | None:
        return object() if job_id in (7, 8) else None


class FakeTargetCheck:
    """改写接口只问岗位是不是目标。"""

    def __init__(self, *job_ids: int) -> None:
        self.job_ids = set(job_ids)

    def exists(self, job_id: int) -> bool:
        return job_id in self.job_ids


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(resumes_route, "rewrite_repository", FakeRewriteRepository())
    monkeypatch.setattr(resumes_route, "job_repository", FakeJobRepository())
    # 岗位 7 是目标，岗位 8 存在但不是目标
    monkeypatch.setattr(resumes_route, "target_repository", FakeTargetCheck(7))
    return TestClient(app)


def _save_profile(profile_service, upload_id: int, resume: ResumeDocument) -> None:
    while len(profile_service.resume_history.uploads) < upload_id:
        profile_service.resume_history.add(ParsedResume.model_validate(resume.model_dump()), "cv.pdf")
    assert profile_service.save(UserProfile(resume=resume, resume_upload_id=upload_id))


def test_rewrite_requires_saved_profile(client: TestClient) -> None:
    assert client.post("/api/resumes/rewrite", json={"job_id": 7}).status_code == 409
    assert client.get("/api/resumes/rewrites/7").status_code == 409


def test_rewrite_requires_target_job(client: TestClient, profile_service) -> None:
    resume = _resume()
    _save_profile(profile_service, 1, resume)
    # 岗位存在但没设为目标：改写和保存都拦下，不会调用 LLM
    assert client.post("/api/resumes/rewrite", json={"job_id": 8}).status_code == 409
    response = client.put("/api/resumes/rewrites/8", json=resume.model_dump())
    assert response.status_code == 409 and response.json()["detail"] == "请先把该岗位设为目标岗位"


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


def test_rewrite_session_survives_and_final_save_keeps_it(client: TestClient, profile_service) -> None:
    resume = _resume()
    _save_profile(profile_service, 1, resume)
    result = {"job_id": 7, "blocks": [], "rewritten_resume": resume.model_dump()}
    session = {"result": result, "reviews": {"experience:0": "accepted"}, "drafts": {"experience:0:0": "Edited"},
               "confirmed_deletions": {"0": True}}

    # 不是目标岗位的不能存
    assert client.put("/api/resumes/rewrites/8/session", json=session).status_code == 409
    assert client.put("/api/resumes/rewrites/7/session", json=session).status_code == 204
    saved = client.get("/api/resumes/rewrites/7").json()
    # 只有对比、还没终稿
    assert saved["resume"] is None
    assert saved["session"]["reviews"] == {"experience:0": "accepted"}
    assert saved["session"]["confirmed_deletions"] == {"0": True}

    # 保存终稿后对比还在，可继续修改
    assert client.put("/api/resumes/rewrites/7", json=resume.model_dump()).status_code == 200
    saved = client.get("/api/resumes/rewrites/7").json()
    assert saved["resume"]["name"] == resume.name and saved["session"]["drafts"] == {"experience:0:0": "Edited"}


DRAFT = "Built REST APIs with Python and FastAPI serving [number of users] users, cutting latency by [latency drop].\nWrote weekly reports for the team. [report audience]"
ANSWERS = [{"placeholder": "[number of users]", "answer": "2000"}, {"placeholder": "[latency drop]", "answer": None}]


def _fill(rewriter: ResumeRewriter, answers: list[dict] = ANSWERS):
    return rewriter.fill_block(
        DRAFT, [PlaceholderAnswer(**a) for a in answers], _job(), technologies=[]
    )


def test_fill_block_writes_answers_and_neutralises_skipped() -> None:
    value = "Built REST APIs with Python and FastAPI serving 2,000 users.\nWrote weekly reports for the team. [report audience]"
    client = FakeChatClient(json.dumps({"value": value, "needs_user_input": []}))

    fill = _fill(_rewriter(client, FakeGuidelineRepository()))

    assert fill.value == value and fill.needs_user_input == []
    sent = json.loads(client.prompts[0])
    # 跳过的问询以 null 传给 LLM，没涉及的占位原样保留
    assert sent["ANSWERS"][1] == {"placeholder": "[latency drop]", "answer": None}


def test_fill_block_retries_on_invented_number_then_gives_up() -> None:
    invented = json.dumps({"value": "Built REST APIs serving 2000 users, cutting latency by 40%.\nWrote weekly reports for the team. [report audience]"})
    good = json.dumps({"value": "Built REST APIs serving 2000 users.\nWrote weekly reports for the team. [report audience]"})

    client = FakeChatClient(invented, good)
    assert _fill(_rewriter(client, FakeGuidelineRepository())).value.startswith("Built REST APIs serving 2000")
    assert client.calls == 2 and "40" in client.prompts[1]

    with pytest.raises(ResumeRewriteError):
        _fill(_rewriter(FakeChatClient(invented, invented), FakeGuidelineRepository()))


def test_fill_block_follow_up_must_keep_its_placeholder() -> None:
    follow_up = {
        "placeholder": "[number of users]",
        "question": {"en": "Roughly how many users per day?", "zh": "大概每天多少用户？"},
        "reason": {"en": "'A lot' cannot be stated as a fact.", "zh": "“很多”无法写成事实。"},
    }
    vague = [{"placeholder": "[number of users]", "answer": "a lot"}]
    kept = "Built REST APIs with Python and FastAPI serving [number of users] users, cutting latency by [latency drop].\nWrote weekly reports for the team. [report audience]"
    # 第一次追问了却把占位删了，不合格；第二次保留占位
    dropped = kept.replace("[number of users]", "many")
    client = FakeChatClient(
        json.dumps({"value": dropped, "needs_user_input": [follow_up]}),
        json.dumps({"value": kept, "needs_user_input": [follow_up]}),
    )

    fill = _fill(_rewriter(client, FakeGuidelineRepository()), vague)

    assert client.calls == 2
    assert [item.placeholder for item in fill.needs_user_input] == ["[number of users]"]


class FakeSemanticRepository:
    def get_analyzed_job(self, job_id: int) -> JobRequirementDocument | None:
        return _job()


def test_fill_route(client: TestClient, profile_service, monkeypatch: pytest.MonkeyPatch) -> None:
    _save_profile(profile_service, 1, _resume())
    value = "Built REST APIs with Python and FastAPI serving 2,000 users.\nWrote weekly reports for the team. [report audience]"
    llm = FakeChatClient(json.dumps({"value": value}))
    monkeypatch.setattr(resumes_route, "resume_rewriter", _rewriter(llm, FakeGuidelineRepository()))
    monkeypatch.setattr(resumes_route, "semantic_repository", FakeSemanticRepository())
    request = {"job_id": 7, "section": "experience", "index": 0, "text": DRAFT, "answers": ANSWERS}

    assert client.post("/api/resumes/rewrite/fill", json={**request, "job_id": 8}).status_code == 409
    assert client.post("/api/resumes/rewrite/fill", json={**request, "index": 3}).status_code == 404
    # 草稿里没有的占位不是待回答的问询
    bad = {**request, "answers": [{"placeholder": "[made up]", "answer": "x"}]}
    assert client.post("/api/resumes/rewrite/fill", json=bad).status_code == 422
    assert llm.calls == 0

    response = client.post("/api/resumes/rewrite/fill", json=request)
    assert response.status_code == 200
    assert response.json() == {
        "value": value, "needs_user_input": [], "section": "experience", "index": 0, "field": "description",
    }


def test_save_rejects_unresolved_placeholders(client: TestClient, profile_service) -> None:
    resume = _resume()
    _save_profile(profile_service, 1, resume)
    draft = resume.model_copy(deep=True)
    draft.experiences[0].description = DRAFT

    response = client.put("/api/resumes/rewrites/7", json=draft.model_dump())
    assert response.status_code == 409 and "[number of users]" in response.json()["detail"]
    # 技术栈列表这类方括号以外的内容、原简历本来就有的方括号都不算占位
    draft.experiences[0].description = DESCRIPTION
    assert client.put("/api/resumes/rewrites/7", json=draft.model_dump()).status_code == 200
