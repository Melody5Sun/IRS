import pytest

from app.resume.rewrite_applier import apply_changes
from app.schemas.resume import Experience, Project, ResumeDocument
from app.schemas.resume_rewrite import ResumeChange

DESCRIPTION = "Responsible for building REST APIs with Python and FastAPI for 3 internal tools."
# 技能栏原文只写了 Python 和 FastAPI；Docker 只在扁平 skills 列表里（来自项目技术栈）
SKILL_GROUPS = [{"category": "Backend", "description": "Proficient in Python and FastAPI."}]


class FakeChatClient:
    """删技能检查的 LLM 打桩：固定返回一段输出。"""

    def __init__(self, response: str) -> None:
        self.response = response

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        return self.response


def _resume() -> ResumeDocument:
    return ResumeDocument(
        name="Test Candidate",
        experiences=[
            Experience(company="Acme", title="Backend Intern", start_date="2025-05", description=DESCRIPTION),
        ],
        projects=[Project(title="Chat App", summary="A chat app.", technologies=["React", "Docker"])],
        skills=["Python", "FastAPI", "Docker"],
        skill_groups=SKILL_GROUPS,
    )


def _change(**overrides: object) -> ResumeChange:
    fields: dict[str, object] = {
        "section": "experience",
        "index": 0,
        "field": "description",
        "original": DESCRIPTION,
        "value": "Built REST APIs with Python and FastAPI powering 3 internal tools.",
        "reasons": [{"issue_type": "weak_action_verb", "explanation": "Lead with an action verb."}],
    }
    fields.update(overrides)
    return ResumeChange(**fields)


def test_valid_changes_are_applied_and_identity_fields_kept() -> None:
    original = _resume()
    new_groups = [
        {"category": "Backend Development", "description": "Proficient in Python and FastAPI."},
        {"category": "DevOps", "description": "Docker"},
    ]
    skills = _change(section="skills", field="skill_groups", original=SKILL_GROUPS, value=new_groups)

    result = apply_changes(
        original, [_change(), skills], jd_company="Shopee", client=FakeChatClient('{"removed_skills": []}')
    )

    assert result.rejected_changes == []
    experience = result.rewritten_resume.experiences[0]
    assert experience.description.startswith("Built REST APIs")
    assert (experience.company, experience.title, experience.start_date) == ("Acme", "Backend Intern", "2025-05")
    # 技能栏按 skill_groups 格式输出，可补入 skills 列表里有、原技能栏没写的 Docker；扁平 skills 不变
    assert [group.model_dump() for group in result.rewritten_resume.skill_groups] == new_groups
    assert result.rewritten_resume.skills == ["Python", "FastAPI", "Docker"]
    assert original.experiences[0].description == DESCRIPTION  # 原简历不被修改
    assert [(b.section, b.heading, len(b.changes)) for b in result.blocks] == [
        ("experience", "Backend Intern · Acme", 1),
        ("project", "Chat App", 0),
        ("skills", "Skills", 1),
    ]
    assert result.blocks[-1].removed_skills == []


def _skills_change(description: str, original: object = SKILL_GROUPS) -> dict[str, object]:
    return {
        "section": "skills", "field": "skill_groups", "original": original,
        "value": [{"category": "Backend", "description": description}],
    }


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"section": "project", "field": "description"}, "invalid_target"),
        ({"index": 5}, "invalid_target"),
        ({"original": "Something the resume never said."}, "original_mismatch"),
        ({"value": "Built REST APIs with Python and FastAPI, cutting latency by 40%."}, "new_number"),
        ({"value": "Built REST APIs with Python, FastAPI and Kubernetes for 3 internal tools."}, "new_skill"),
        ({"value": "Built REST APIs with Python and FastAPI for 3 internal tools at Shopee."}, "jd_company_mention"),
        ({"value": "Built REST APIs with Python and FastAPI for 3 internal tools" + " and more" * 20}, "too_long"),
        (
            {"section": "project", "field": "technologies", "original": ["React", "Docker"], "value": ["React", "Vue"]},
            "not_a_reorder",
        ),
        (_skills_change("Python, FastAPI", original=[]), "original_mismatch"),
        (_skills_change("Proficient in Python, FastAPI, Docker and Kubernetes."), "new_skill"),
        (_skills_change("Proficient in Python 3 and FastAPI."), "new_number"),
        ({"section": "skills", "field": "skill_groups", "original": SKILL_GROUPS}, "invalid_target"),
    ],
)
def test_invalid_changes_are_rejected_with_reason(overrides: dict[str, object], reason: str) -> None:
    result = apply_changes(_resume(), [_change(**overrides)], jd_company="Shopee")

    assert [r.reason for r in result.rejected_changes] == [reason]
    assert result.rewritten_resume == _resume()


def test_second_change_to_same_field_is_rejected() -> None:
    result = apply_changes(_resume(), [_change(), _change()], jd_company="Shopee")

    assert [r.reason for r in result.rejected_changes] == ["invalid_target"]
    assert len(result.blocks[0].changes) == 1


def _skills_rewrite(response: str) -> list[str]:
    # 原技能栏写的是缩写 K8s，skills 列表里是全称 Kubernetes；改写后删掉了 K8s 和 Python
    original = ResumeDocument.model_validate({
        **_resume().model_dump(),
        "skills": ["Python", "FastAPI", "Kubernetes"],
        "skill_groups": [{"category": "Backend", "description": "Python, FastAPI, K8s"}],
    })
    change = _change(
        section="skills", field="skill_groups",
        original=[{"category": "Backend", "description": "Python, FastAPI, K8s"}],
        value=[{"category": "Backend", "description": "FastAPI"}],
    )
    result = apply_changes(original, [change], jd_company="Shopee", client=FakeChatClient(response))
    assert result.rejected_changes == []  # 删技能不拒绝，只提醒
    return result.blocks[-1].removed_skills


def test_removed_skills_use_llm_alias_match() -> None:
    # LLM 识别出缩写 K8s 被删；编出来的 Rust 原简历没有，被过滤
    assert _skills_rewrite('{"removed_skills": ["Python", "K8s", "Rust"]}') == ["Python", "K8s"]


def test_removed_skills_fall_back_to_string_match_on_bad_llm_output() -> None:
    # 字符串匹配查不出 K8s（skills 列表写的是 Kubernetes），这是退回方案的已知上限
    assert _skills_rewrite("not json") == ["Python"]
