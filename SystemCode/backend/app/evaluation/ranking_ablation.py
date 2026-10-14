from __future__ import annotations

from dataclasses import dataclass
import statistics
from typing import Mapping, Sequence

from app.evaluation.grouped_weight_cross_validation import (
    make_resume_folds,
    ndcg_by_resume,
)
from app.evaluation.ranking_weight_optimizer import COMPONENTS, RankingExample


ABLATION_CONFIGS: dict[str, dict[str, float]] = {
    "full_model": {
        "required_direct": 0.20,
        "responsibility": 0.60,
        "required_graph": 0.20,
    },
    "without_direct_skill": {
        "required_direct": 0.00,
        "responsibility": 0.75,
        "required_graph": 0.25,
    },
    "without_responsibility": {
        "required_direct": 0.50,
        "responsibility": 0.00,
        "required_graph": 0.50,
    },
    "without_knowledge_graph": {
        "required_direct": 0.25,
        "responsibility": 0.75,
        "required_graph": 0.00,
    },
    "direct_skill_only": {
        "required_direct": 1.00,
        "responsibility": 0.00,
        "required_graph": 0.00,
    },
    "responsibility_only": {
        "required_direct": 0.00,
        "responsibility": 1.00,
        "required_graph": 0.00,
    },
}


@dataclass(frozen=True)
class AblationFoldResult:
    fold: int
    test_resume_ids: tuple[str, ...]
    ndcg_by_method: Mapping[str, Mapping[str, float]]


def run_ranking_ablation(
    examples: Sequence[RankingExample],
    *,
    configs: Mapping[str, Mapping[str, float]] = ABLATION_CONFIGS,
    fold_count: int = 5,
    seed: int = 42,
    k: int = 10,
) -> tuple[list[AblationFoldResult], dict[str, object]]:
    _validate_configs(configs)
    resume_ids = sorted({example.resume_id for example in examples})
    folds = make_resume_folds(resume_ids, fold_count=fold_count, seed=seed)
    fold_results: list[AblationFoldResult] = []
    held_out: dict[str, dict[str, float]] = {
        method: {} for method in configs
    }

    for index, test_ids in enumerate(folds, start=1):
        fold_scores = {
            method: ndcg_by_resume(examples, weights, test_ids, k=k)
            for method, weights in configs.items()
        }
        for method, values in fold_scores.items():
            held_out[method].update(values)
        fold_results.append(
            AblationFoldResult(
                fold=index,
                test_resume_ids=test_ids,
                ndcg_by_method=fold_scores,
            )
        )

    full_scores = held_out["full_model"]
    summary: dict[str, object] = {}
    for method, scores in held_out.items():
        ordered = [scores[resume_id] for resume_id in resume_ids]
        full_ordered = [full_scores[resume_id] for resume_id in resume_ids]
        deltas = [
            value - full
            for value, full in zip(ordered, full_ordered, strict=True)
        ]
        summary[method] = {
            "weights": dict(configs[method]),
            "mean_ndcg": statistics.mean(ordered),
            "std_ndcg": statistics.pstdev(ordered),
            "min_ndcg": min(ordered),
            "max_ndcg": max(ordered),
            "mean_delta_vs_full": statistics.mean(deltas),
            "mean_drop_from_full": -statistics.mean(deltas),
            "better_resume_count": sum(delta > 1e-12 for delta in deltas),
            "equal_resume_count": sum(abs(delta) <= 1e-12 for delta in deltas),
            "worse_resume_count": sum(delta < -1e-12 for delta in deltas),
            "ndcg_by_resume": {
                resume_id: scores[resume_id] for resume_id in resume_ids
            },
        }
    return fold_results, summary


def _validate_configs(configs: Mapping[str, Mapping[str, float]]) -> None:
    if "full_model" not in configs:
        raise ValueError("configs must include full_model")
    for name, weights in configs.items():
        if set(weights) != set(COMPONENTS):
            raise ValueError(f"{name} must define exactly {COMPONENTS}")
        if any(value < 0 for value in weights.values()):
            raise ValueError(f"{name} contains a negative weight")
        if abs(sum(weights.values()) - 1.0) > 1e-9:
            raise ValueError(f"{name} weights must sum to 1")
