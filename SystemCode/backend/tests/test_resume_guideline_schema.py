import pytest
from pydantic import ValidationError

from app.schemas.resume_guideline import ResumeGuideline


def _entry(**overrides: object) -> ResumeGuideline:
    fields: dict[str, object] = {
        "key": "quantify-01",
        "source": "it-careerpilot-team",
        "title": "Quantify impact",
        "guideline": "Add a measurable result to each bullet.",
        "rationale": "Numbers show scale.",
        "examples": [
            {"before": "Improved API performance.", "after": "Cut API latency by [X%]."},
            {"before": "Made the app faster.", "after": "Reduced app load time by [X%]."},
        ],
        "sections": ["experience"],
        "issue_types": ["missing_quantification"],
    }
    fields.update(overrides)
    return ResumeGuideline(**fields)


def test_guideline_builds_one_guideline_chunk_and_one_chunk_per_example() -> None:
    entry = _entry(role_categories=["Software Development"])

    assert entry.chunk_texts() == [
        (None, "Quantify impact. Add a measurable result to each bullet."),
        (0, "Improved API performance."),
        (1, "Made the app faster."),
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {"role_categories": ["Backend Developer"]},  # 具体岗位不是一级大类
        {"source": "some-random-blog"},
        {"sections": ["summary"]},
        {"issue_types": ["typo"]},
        {"sections": []},
        {"examples": []},
        {"examples": [{"before": "a", "after": "b"}] * 4},
    ],
)
def test_guideline_rejects_invalid_fields(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _entry(**overrides)
