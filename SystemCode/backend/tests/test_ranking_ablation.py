import pytest

from app.evaluation.ranking_ablation import run_ranking_ablation
from app.evaluation.ranking_weight_optimizer import RankingExample


def _examples() -> list[RankingExample]:
    examples: list[RankingExample] = []
    for resume_index in range(1, 7):
        resume_id = f"R{resume_index:02d}"
        for job_index, relevance in enumerate((3, 2, 1, 0), start=1):
            examples.append(
                RankingExample(
                    pair_id=f"{resume_id}-J{job_index}",
                    resume_id=resume_id,
                    split="ignored",
                    relevance=relevance,
                    coverages={
                        "required_direct": (3 - relevance) * 20,
                        "responsibility": relevance * 30,
                        "required_graph": 10,
                    },
                )
            )
    return examples


def test_ablation_evaluates_each_resume_once() -> None:
    folds, summary = run_ranking_ablation(
        _examples(), fold_count=3, seed=3, k=4
    )

    held_out = [resume_id for fold in folds for resume_id in fold.test_resume_ids]
    assert sorted(held_out) == [f"R{index:02d}" for index in range(1, 7)]
    assert summary["full_model"]["mean_ndcg"] == pytest.approx(1.0)
    assert summary["without_responsibility"]["mean_ndcg"] < 1.0
    assert len(summary["full_model"]["ndcg_by_resume"]) == 6


def test_ablation_rejects_weights_that_are_not_normalized() -> None:
    configs = {
        "full_model": {
            "required_direct": 0.2,
            "responsibility": 0.6,
            "required_graph": 0.1,
        }
    }

    with pytest.raises(ValueError, match="sum to 1"):
        run_ranking_ablation(_examples(), configs=configs, fold_count=3)
