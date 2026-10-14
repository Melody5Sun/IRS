from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence


COMPONENTS = (
    "required_direct",
    "responsibility",
    "required_graph",
)
BASELINE_WEIGHTS = {
    "required_direct": 0.20,
    "responsibility": 0.60,
    "required_graph": 0.20,
}


@dataclass(frozen=True)
class RankingExample:
    pair_id: str
    resume_id: str
    split: str
    relevance: float
    coverages: Mapping[str, float | None]
    preferred_bonus: float = 0.0
    hard_constraint_pass: bool = True


@dataclass(frozen=True)
class SearchResult:
    weights: dict[str, float]
    validation_ndcg: float
    evaluated_candidates: int


def score_example(example: RankingExample, weights: Mapping[str, float]) -> float:
    if not example.hard_constraint_pass:
        return float("-inf")
    active = [name for name in weights if example.coverages.get(name) is not None]
    active_weight = sum(weights[name] for name in active)
    if active_weight <= 0:
        return example.preferred_bonus
    core = sum(
        float(example.coverages[name]) * weights[name] / active_weight
        for name in active
    )
    return min(100.0, core + example.preferred_bonus)


def ndcg_at_k(relevances: Sequence[float], scores: Sequence[float], k: int = 10) -> float:
    if len(relevances) != len(scores):
        raise ValueError("relevances and scores must have equal length")
    if k <= 0:
        raise ValueError("k must be positive")
    if not relevances:
        return 0.0
    order = sorted(range(len(scores)), key=lambda index: (-scores[index], index))[:k]
    ideal = sorted(relevances, reverse=True)[:k]

    def dcg(values: Iterable[float]) -> float:
        return sum(
            (2.0**relevance - 1.0) / math.log2(rank + 2.0)
            for rank, relevance in enumerate(values)
        )

    ideal_dcg = dcg(ideal)
    if ideal_dcg == 0:
        return 0.0
    return dcg(relevances[index] for index in order) / ideal_dcg


def mean_ndcg_at_k(
    examples: Sequence[RankingExample],
    weights: Mapping[str, float],
    *,
    split: str,
    k: int = 10,
) -> float:
    grouped: dict[str, list[RankingExample]] = defaultdict(list)
    for example in examples:
        if example.split == split:
            grouped[example.resume_id].append(example)
    if not grouped:
        raise ValueError(f"no examples found for split {split!r}")
    values = []
    for group in grouped.values():
        values.append(
            ndcg_at_k(
                [item.relevance for item in group],
                [score_example(item, weights) for item in group],
                k=k,
            )
        )
    return sum(values) / len(values)


def weight_grid(
    step: float = 0.05,
    components: Sequence[str] = COMPONENTS,
) -> Iterable[dict[str, float]]:
    units = round(1.0 / step)
    if not math.isclose(units * step, 1.0, abs_tol=1e-9):
        raise ValueError("step must divide 1.0 exactly")
    if not components:
        raise ValueError("components must not be empty")

    def compositions(remaining: int, count: int) -> Iterable[tuple[int, ...]]:
        if count == 1:
            yield (remaining,)
            return
        for value in range(remaining + 1):
            for rest in compositions(remaining - value, count - 1):
                yield (value, *rest)

    for values in compositions(units, len(components)):
        yield {
            name: value / units
            for name, value in zip(components, values, strict=True)
        }


def search_weights(
    examples: Sequence[RankingExample],
    *,
    step: float = 0.05,
    k: int = 10,
    components: Sequence[str] = COMPONENTS,
    baseline_weights: Mapping[str, float] = BASELINE_WEIGHTS,
) -> SearchResult:
    best_weights: dict[str, float] | None = None
    best_ndcg = float("-inf")
    best_distance = float("inf")
    evaluated = 0
    for weights in weight_grid(step, components):
        value = mean_ndcg_at_k(examples, weights, split="validation", k=k)
        baseline_total = sum(baseline_weights[name] for name in components)
        distance = sum(
            abs(weights[name] - baseline_weights[name] / baseline_total)
            for name in components
        )
        evaluated += 1
        if value > best_ndcg + 1e-12 or (
            math.isclose(value, best_ndcg, abs_tol=1e-12) and distance < best_distance
        ):
            best_weights = weights
            best_ndcg = value
            best_distance = distance
    if best_weights is None:
        raise ValueError("weight grid is empty")
    return SearchResult(best_weights, best_ndcg, evaluated)


def cohen_kappa(left: Sequence[int], right: Sequence[int]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("annotator labels must be non-empty and have equal length")
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / len(left)
    left_counts = Counter(left)
    right_counts = Counter(right)
    labels = set(left_counts) | set(right_counts)
    expected = sum(
        left_counts[label] / len(left) * right_counts[label] / len(right)
        for label in labels
    )
    if math.isclose(expected, 1.0):
        return 1.0 if math.isclose(observed, 1.0) else 0.0
    return (observed - expected) / (1.0 - expected)
