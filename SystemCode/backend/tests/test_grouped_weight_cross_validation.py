import pytest

from app.evaluation.grouped_weight_cross_validation import (
    make_resume_folds,
    run_grouped_cross_validation,
    select_weights_for_resumes,
)
from app.evaluation.ranking_weight_optimizer import RankingExample


def _examples() -> list[RankingExample]:
    examples: list[RankingExample] = []
    for resume_index in range(1, 7):
        resume_id = f"R{resume_index:02d}"
        examples.extend(
            [
                RankingExample(
                    pair_id=f"{resume_id}-A",
                    resume_id=resume_id,
                    split="ignored",
                    relevance=3,
                    coverages={
                        "required_direct": 100,
                        "responsibility": 80,
                        "required_graph": 20,
                    },
                ),
                RankingExample(
                    pair_id=f"{resume_id}-B",
                    resume_id=resume_id,
                    split="ignored",
                    relevance=0,
                    coverages={
                        "required_direct": 0,
                        "responsibility": 20,
                        "required_graph": 80,
                    },
                ),
            ]
        )
    return examples


def test_resume_folds_are_deterministic_and_disjoint() -> None:
    ids = [f"R{index:02d}" for index in range(1, 11)]
    first = make_resume_folds(ids, fold_count=5, seed=7)
    second = make_resume_folds(ids, fold_count=5, seed=7)

    assert first == second
    assert all(len(fold) == 2 for fold in first)
    assert sorted(item for fold in first for item in fold) == ids


def test_grouped_cross_validation_holds_out_each_resume_once() -> None:
    folds, summary = run_grouped_cross_validation(
        _examples(),
        fold_count=3,
        seed=3,
        step=0.5,
        k=2,
    )

    held_out = [resume_id for fold in folds for resume_id in fold.test_resume_ids]
    assert sorted(held_out) == [f"R{index:02d}" for index in range(1, 7)]
    assert all(
        not (set(fold.train_resume_ids) & set(fold.test_resume_ids))
        for fold in folds
    )
    assert summary["baseline"]["mean_ndcg"] == pytest.approx(1.0)
    assert summary["selected"]["mean_ndcg"] == pytest.approx(1.0)


def test_weight_search_can_require_direct_weight_not_below_graph() -> None:
    weights, _, evaluated = select_weights_for_resumes(
        _examples(),
        [f"R{index:02d}" for index in range(1, 7)],
        step=0.5,
        k=2,
        require_direct_gte_graph=True,
    )

    assert weights["required_direct"] >= weights["required_graph"]
    assert evaluated < 6
