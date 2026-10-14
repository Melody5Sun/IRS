import pytest

from app.evaluation.ranking_weight_optimizer import (
    RankingExample,
    cohen_kappa,
    mean_ndcg_at_k,
    ndcg_at_k,
    score_example,
    search_weights,
    weight_grid,
)


def example(
    pair_id: str,
    relevance: float,
    direct: float,
    responsibility: float,
    *,
    resume_id: str = "R01",
    split: str = "validation",
) -> RankingExample:
    return RankingExample(
        pair_id=pair_id,
        resume_id=resume_id,
        split=split,
        relevance=relevance,
        coverages={
            "required_direct": direct,
            "responsibility": responsibility,
            "required_graph": 0.0,
            "career_intent": 0.0,
        },
    )


def test_ndcg_is_one_for_an_ideal_ranking() -> None:
    assert ndcg_at_k([3, 2, 0], [0.9, 0.8, 0.1], k=3) == pytest.approx(1.0)


def test_missing_components_are_renormalized_over_active_weights() -> None:
    item = RankingExample(
        pair_id="P1",
        resume_id="R1",
        split="validation",
        relevance=2,
        coverages={
            "required_direct": 80.0,
            "responsibility": None,
            "required_graph": 20.0,
            "career_intent": None,
        },
    )
    score = score_example(
        item,
        {
            "required_direct": 0.4,
            "responsibility": 0.3,
            "required_graph": 0.2,
            "career_intent": 0.1,
        },
    )
    assert score == pytest.approx((80 * 0.4 + 20 * 0.2) / 0.6)


def test_weight_grid_is_nonnegative_and_sums_to_one() -> None:
    candidates = list(weight_grid(0.5))
    assert len(candidates) == 6
    assert all(sum(candidate.values()) == pytest.approx(1.0) for candidate in candidates)
    assert all(value >= 0 for candidate in candidates for value in candidate.values())


def test_weight_grid_supports_professional_fit_components() -> None:
    components = ("required_direct", "responsibility", "required_graph")
    candidates = list(weight_grid(0.5, components))
    assert len(candidates) == 6
    assert all(tuple(candidate) == components for candidate in candidates)
    assert all(sum(candidate.values()) == pytest.approx(1.0) for candidate in candidates)


def test_search_selects_the_component_that_matches_human_relevance() -> None:
    examples = [
        example("A", 3, 100, 0),
        example("B", 1, 80, 100),
        example("C", 0, 0, 100),
        example("D", 3, 100, 0, resume_id="R02"),
        example("F", 1, 80, 100, resume_id="R02"),
        example("E", 0, 0, 100, resume_id="R02"),
    ]
    result = search_weights(examples, step=0.5, k=3)
    assert result.weights["required_direct"] > result.weights["responsibility"]
    assert mean_ndcg_at_k(examples, result.weights, split="validation", k=3) == pytest.approx(1.0)


def test_cohen_kappa_reports_perfect_agreement() -> None:
    assert cohen_kappa([0, 1, 2, 3], [0, 1, 2, 3]) == pytest.approx(1.0)
