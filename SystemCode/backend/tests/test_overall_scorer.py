from app.matching.overall_scorer import OverallScorer
from app.schemas.match import (
    CareerIntentScoreResponse,
    ResponsibilityScoreResponse,
    SkillScoreResponse,
)


def skill_score(
    direct: float,
    graph: float,
    *,
    calculable: bool = True,
    preferred_bonus: float = 0,
) -> SkillScoreResponse:
    return SkillScoreResponse(
        required_skills_calculable=calculable,
        preferred_skills_available=preferred_bonus > 0,
        required_direct_coverage=direct,
        required_direct_points=0.20 * direct,
        required_graph_coverage=graph,
        required_graph_points=0.20 * graph,
        preferred_direct_coverage=0,
        preferred_graph_coverage=0,
        preferred_skill_coverage=0,
        preferred_bonus=preferred_bonus,
        partial_score=0.20 * direct + 0.20 * graph + preferred_bonus,
    )


def responsibility_score(coverage: float, *, calculable: bool = True) -> ResponsibilityScoreResponse:
    return ResponsibilityScoreResponse(
        responsibilities_calculable=calculable,
        resume_evidence_available=True,
        responsibility_count=1 if calculable else 0,
        evidence_count=1,
        responsibility_coverage=coverage,
        responsibility_points=0.60 * coverage,
    )


def intent_score(coverage: float, *, calculable: bool = True) -> CareerIntentScoreResponse:
    return CareerIntentScoreResponse(
        intent_calculable=calculable,
        intent_similarity=0.7 if calculable else 0,
        intent_coverage=coverage,
        career_intent_points=0.10 * coverage,
    )


def test_calculates_professional_fit_without_mixing_in_intent() -> None:
    result = OverallScorer().combine(
        skill_score(50, 50, preferred_bonus=4),
        responsibility_score(50),
        intent_score(50),
    )

    assert result.active_core_weight == 100
    assert result.core_score == 50
    assert result.preferred_bonus == 4
    assert result.professional_score == 54
    assert result.intent_fit == 50
    assert result.final_score == 54
    assert result.effective_weights == {
        "required_direct": 0.2,
        "required_graph": 0.2,
        "responsibility": 0.6,
    }


def test_renormalizes_when_responsibility_and_intent_are_unavailable() -> None:
    result = OverallScorer().combine(
        skill_score(75, 75),
        responsibility_score(0, calculable=False),
        intent_score(0, calculable=False),
    )

    assert result.active_core_weight == 40
    assert result.core_score == 75
    assert result.effective_weights == {
        "required_direct": 0.5,
        "required_graph": 0.5,
    }
    assert result.professional_score == 75
    assert result.intent_fit is None
    assert result.final_score == 75


def test_caps_core_plus_preferred_bonus_at_100() -> None:
    result = OverallScorer().combine(
        skill_score(100, 100, preferred_bonus=5),
        responsibility_score(100),
        intent_score(100),
    )
    assert result.core_score == 100
    assert result.professional_score == 100
    assert result.final_score == 100
