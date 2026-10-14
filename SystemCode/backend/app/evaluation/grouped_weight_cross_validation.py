from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import random
import statistics
from typing import Mapping, Sequence

from app.evaluation.ranking_weight_optimizer import (
    BASELINE_WEIGHTS,
    COMPONENTS,
    RankingExample,
    ndcg_at_k,
    score_example,
    weight_grid,
)


@dataclass(frozen=True)
class FoldResult:
    fold: int
    train_resume_ids: tuple[str, ...]
    test_resume_ids: tuple[str, ...]
    selected_weights: Mapping[str, float]
    train_ndcg: float
    selected_test_ndcg: float
    baseline_test_ndcg: float
    candidate_test_ndcg: float
    selected_test_by_resume: Mapping[str, float]
    baseline_test_by_resume: Mapping[str, float]
    candidate_test_by_resume: Mapping[str, float]


def make_resume_folds(
    resume_ids: Sequence[str],
    *,
    fold_count: int = 5,
    seed: int = 42,
) -> list[tuple[str, ...]]:
    unique_ids = sorted(set(resume_ids))
    if len(unique_ids) != len(resume_ids):
        raise ValueError("resume_ids must be unique")
    if fold_count < 2 or fold_count > len(unique_ids):
        raise ValueError("fold_count must be between 2 and the number of resumes")

    random.Random(seed).shuffle(unique_ids)
    folds = [[] for _ in range(fold_count)]
    for index, resume_id in enumerate(unique_ids):
        folds[index % fold_count].append(resume_id)
    return [tuple(fold) for fold in folds]


def ndcg_by_resume(
    examples: Sequence[RankingExample],
    weights: Mapping[str, float],
    resume_ids: Sequence[str],
    *,
    k: int = 10,
) -> dict[str, float]:
    grouped: dict[str, list[RankingExample]] = defaultdict(list)
    requested = set(resume_ids)
    for example in examples:
        if example.resume_id in requested:
            grouped[example.resume_id].append(example)
    missing = requested - set(grouped)
    if missing:
        raise ValueError(f"missing examples for resumes: {sorted(missing)}")

    return {
        resume_id: ndcg_at_k(
            [item.relevance for item in grouped[resume_id]],
            [score_example(item, weights) for item in grouped[resume_id]],
            k=k,
        )
        for resume_id in resume_ids
    }


def select_weights_for_resumes(
    examples: Sequence[RankingExample],
    train_resume_ids: Sequence[str],
    *,
    step: float = 0.05,
    k: int = 10,
    baseline_weights: Mapping[str, float] = BASELINE_WEIGHTS,
    require_direct_gte_graph: bool = False,
) -> tuple[dict[str, float], float, int]:
    best_weights: dict[str, float] | None = None
    best_ndcg = float("-inf")
    best_distance = float("inf")
    evaluated = 0
    for weights in weight_grid(step, COMPONENTS):
        if (
            require_direct_gte_graph
            and weights["required_direct"] < weights["required_graph"]
        ):
            continue
        values = ndcg_by_resume(examples, weights, train_resume_ids, k=k)
        mean_ndcg = statistics.mean(values.values())
        distance = sum(
            abs(weights[name] - baseline_weights[name]) for name in COMPONENTS
        )
        evaluated += 1
        if mean_ndcg > best_ndcg + 1e-12 or (
            math.isclose(mean_ndcg, best_ndcg, abs_tol=1e-12)
            and distance < best_distance
        ):
            best_weights = weights
            best_ndcg = mean_ndcg
            best_distance = distance
    if best_weights is None:
        raise ValueError("weight grid is empty")
    return best_weights, best_ndcg, evaluated


def run_grouped_cross_validation(
    examples: Sequence[RankingExample],
    *,
    fold_count: int = 5,
    seed: int = 42,
    step: float = 0.05,
    k: int = 10,
    baseline_weights: Mapping[str, float] = BASELINE_WEIGHTS,
    candidate_weights: Mapping[str, float] | None = None,
    require_direct_gte_graph: bool = False,
) -> tuple[list[FoldResult], dict[str, object]]:
    candidate = candidate_weights or {
        "required_direct": 0.15,
        "responsibility": 0.65,
        "required_graph": 0.20,
    }
    resume_ids = sorted({example.resume_id for example in examples})
    folds = make_resume_folds(resume_ids, fold_count=fold_count, seed=seed)
    results: list[FoldResult] = []

    for index, test_ids in enumerate(folds, start=1):
        test_set = set(test_ids)
        train_ids = tuple(item for item in resume_ids if item not in test_set)
        selected, train_ndcg, _ = select_weights_for_resumes(
            examples,
            train_ids,
            step=step,
            k=k,
            baseline_weights=baseline_weights,
            require_direct_gte_graph=require_direct_gte_graph,
        )
        selected_test = ndcg_by_resume(examples, selected, test_ids, k=k)
        baseline_test = ndcg_by_resume(examples, baseline_weights, test_ids, k=k)
        candidate_test = ndcg_by_resume(examples, candidate, test_ids, k=k)
        results.append(
            FoldResult(
                fold=index,
                train_resume_ids=train_ids,
                test_resume_ids=test_ids,
                selected_weights=selected,
                train_ndcg=train_ndcg,
                selected_test_ndcg=statistics.mean(selected_test.values()),
                baseline_test_ndcg=statistics.mean(baseline_test.values()),
                candidate_test_ndcg=statistics.mean(candidate_test.values()),
                selected_test_by_resume=selected_test,
                baseline_test_by_resume=baseline_test,
                candidate_test_by_resume=candidate_test,
            )
        )

    def held_out_values(field: str) -> list[float]:
        return [
            value
            for result in results
            for value in getattr(result, field).values()
        ]

    selected_values = held_out_values("selected_test_by_resume")
    baseline_values = held_out_values("baseline_test_by_resume")
    candidate_values = held_out_values("candidate_test_by_resume")
    selected_counts = Counter(
        tuple(result.selected_weights[name] for name in COMPONENTS)
        for result in results
    )
    summary = {
        "selected": _metric_summary(selected_values),
        "baseline": _metric_summary(baseline_values),
        "candidate": _metric_summary(candidate_values),
        "selected_weight_counts": {
            "/".join(f"{value:.2f}" for value in weights): count
            for weights, count in selected_counts.most_common()
        },
        "candidate_vs_baseline": _paired_summary(candidate_values, baseline_values),
        "selected_vs_baseline": _paired_summary(selected_values, baseline_values),
    }
    return results, summary


def _metric_summary(values: Sequence[float]) -> dict[str, float]:
    return {
        "mean_ndcg": statistics.mean(values),
        "std_ndcg": statistics.pstdev(values),
        "min_ndcg": min(values),
        "max_ndcg": max(values),
    }


def _paired_summary(left: Sequence[float], right: Sequence[float]) -> dict[str, object]:
    deltas = [a - b for a, b in zip(left, right, strict=True)]
    return {
        "mean_delta": statistics.mean(deltas),
        "improved_resume_count": sum(delta > 1e-12 for delta in deltas),
        "unchanged_resume_count": sum(abs(delta) <= 1e-12 for delta in deltas),
        "worse_resume_count": sum(delta < -1e-12 for delta in deltas),
    }
