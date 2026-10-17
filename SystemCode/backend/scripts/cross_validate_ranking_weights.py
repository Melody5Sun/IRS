from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
import statistics
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.evaluation.grouped_weight_cross_validation import (
    run_grouped_cross_validation,
)
from app.evaluation.ranking_weight_optimizer import RankingExample


DEFAULT_DIR = BACKEND_ROOT / "evaluation" / "job_ranking"
HISTORICAL_BASELINE_WEIGHTS = {
    "required_direct": 0.30,
    "responsibility": 0.45,
    "required_graph": 0.25,
}
FINAL_WEIGHTS = {
    "required_direct": 0.20,
    "responsibility": 0.60,
    "required_graph": 0.20,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run grouped cross-validation of ranking weights by resume."
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=DEFAULT_DIR / "annotation_pairs_three_level_professional_v2.csv",
    )
    parser.add_argument(
        "--features",
        type=Path,
        default=DEFAULT_DIR / "pair_features_resume_segments_v5.jsonl",
    )
    parser.add_argument(
        "--profiles",
        type=Path,
        default=DEFAULT_DIR / "profiles.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DIR / "ranking_weight_cv_v5_constrained.json",
    )
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--step", type=float, default=0.05)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument(
        "--require-direct-gte-graph",
        action="store_true",
        help="Only search weights where required-direct weight is at least graph weight.",
    )
    return parser.parse_args()


def load_examples(annotations_path: Path, features_path: Path) -> list[RankingExample]:
    features = {
        row["pair_id"]: row
        for row in map(json.loads, features_path.read_text(encoding="utf-8").splitlines())
    }
    examples: list[RankingExample] = []
    with annotations_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            feature = features[row["pair_id"]]
            examples.append(
                RankingExample(
                    pair_id=row["pair_id"],
                    resume_id=feature["resume_id"],
                    split=feature["split"],
                    relevance=float(row["label"]),
                    coverages=feature["coverages"],
                    preferred_bonus=float(feature.get("preferred_bonus", 0.0)),
                    hard_constraint_pass=bool(feature["hard_constraint_pass"]),
                )
            )
    return examples


def main() -> None:
    args = parse_args()
    examples = load_examples(args.annotations, args.features)
    profiles = {
        item["resume_id"]: item
        for item in json.loads(args.profiles.read_text(encoding="utf-8"))
    }
    folds, summary = run_grouped_cross_validation(
        examples,
        fold_count=args.folds,
        seed=args.seed,
        step=args.step,
        k=args.k,
        baseline_weights=HISTORICAL_BASELINE_WEIGHTS,
        candidate_weights=FINAL_WEIGHTS,
        require_direct_gte_graph=args.require_direct_gte_graph,
    )

    direction_values: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for fold in folds:
        for resume_id in fold.test_resume_ids:
            for role in profiles[resume_id]["target_roles"]:
                direction_values[role]["baseline"].append(
                    fold.baseline_test_by_resume[resume_id]
                )
                direction_values[role]["candidate"].append(
                    fold.candidate_test_by_resume[resume_id]
                )
                direction_values[role]["selected"].append(
                    fold.selected_test_by_resume[resume_id]
                )

    report = {
        "pair_count": len(examples),
        "resume_count": len({item.resume_id for item in examples}),
        "fold_count": args.folds,
        "seed": args.seed,
        "grid_step": args.step,
        "ndcg_k": args.k,
        "require_direct_gte_graph": args.require_direct_gte_graph,
        "weight_order": ["required_direct", "responsibility", "required_graph"],
        "baseline_weights": HISTORICAL_BASELINE_WEIGHTS,
        "candidate_weights": FINAL_WEIGHTS,
        "folds": [
            {
                "fold": fold.fold,
                "train_resume_ids": list(fold.train_resume_ids),
                "test_resume_ids": list(fold.test_resume_ids),
                "selected_weights": dict(fold.selected_weights),
                "direct_weight_gte_graph_weight": (
                    fold.selected_weights["required_direct"]
                    >= fold.selected_weights["required_graph"]
                ),
                "train_ndcg": fold.train_ndcg,
                "selected_test_ndcg": fold.selected_test_ndcg,
                "baseline_test_ndcg": fold.baseline_test_ndcg,
                "candidate_test_ndcg": fold.candidate_test_ndcg,
                "selected_test_by_resume": dict(fold.selected_test_by_resume),
                "baseline_test_by_resume": dict(fold.baseline_test_by_resume),
                "candidate_test_by_resume": dict(fold.candidate_test_by_resume),
            }
            for fold in folds
        ],
        "summary": summary,
        "by_target_role": {
            role: {
                method: {
                    "resume_count": len(values),
                    "mean_ndcg": statistics.mean(values),
                }
                for method, values in methods.items()
            }
            for role, methods in sorted(direction_values.items())
        },
        "notes": [
            "All 20 pairs for a resume remain in the same held-out fold.",
            "A resume with multiple target roles contributes to each listed role summary.",
            (
                "The grid requires direct-skill weight to be at least graph weight."
                if args.require_direct_gte_graph
                else "The grid matches the existing unconstrained search."
            ),
        ],
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Saved report to {args.output}")


if __name__ == "__main__":
    main()
