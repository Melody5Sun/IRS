import pytest

from app.resume.rewrite_applier import apply_changes
from app.schemas.resume import Experience, Project, ResumeDocument
from app.schemas.resume_rewrite import ResumeChange

DESCRIPTION = "Responsible for building REST APIs with Python and FastAPI for 3 internal tools."


def _resume() -> ResumeDocument:
    return ResumeDocument(
        name="Test Candidate",
        experiences=[
            Experience(company="Acme", title="Backend Intern", start_date="2025-05", description=DESCRIPTION),
        ],
        projects=[Project(title="Chat App", summary="A chat app.", technologies=["React", "Docker"])],
        skills=["Python", "FastAPI", "Docker"],
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
    reorder = _change(
        section="skills", field="skills",
        original=["Python", "FastAPI", "Docker"], value=["Docker", "Python", "FastAPI"],
    )

    result = apply_changes(original, [_change(), reorder], jd_company="Shopee")

    assert result.rejected_changes == []
    experience = result.rewritten_resume.experiences[0]
    assert experience.description.startswith("Built REST APIs")
    assert (experience.company, experience.title, experience.start_date) == ("Acme", "Backend Intern", "2025-05")
    assert result.rewritten_resume.skills == ["Docker", "Python", "FastAPI"]
    assert original.experiences[0].description == DESCRIPTION  # 原简历不被修改
    assert [(b.section, b.heading, len(b.changes)) for b in result.blocks] == [
        ("experience", "Backend Intern · Acme", 1),
        ("project", "Chat App", 0),
        ("skills", "Skills", 1),
    ]


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
