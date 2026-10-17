from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.evaluation.ranking_ablation import run_ranking_ablation
from scripts.cross_validate_ranking_weights import DEFAULT_DIR, load_examples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run grouped ablation evaluation for ranking components."
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
        "--output",
        type=Path,
        default=DEFAULT_DIR / "ranking_ablation_v5.json",
    )
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--k", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    examples = load_examples(args.annotations, args.features)
    folds, summary = run_ranking_ablation(
        examples,
        fold_count=args.folds,
        seed=args.seed,
        k=args.k,
    )
    report = {
        "pair_count": len(examples),
        "resume_count": len({item.resume_id for item in examples}),
        "fold_count": args.folds,
        "seed": args.seed,
        "ndcg_k": args.k,
        "evaluation": "Each resume is evaluated once in its held-out fold.",
        "controlled_factors": [
            "Preferred-skill bonus remains enabled for every configuration.",
            "Missing-component renormalization is identical to production scoring.",
            "Career intent is excluded from professional-fit relevance and evaluation.",
        ],
        "folds": [
            {
                "fold": fold.fold,
                "test_resume_ids": list(fold.test_resume_ids),
                "ndcg_by_method": {
                    method: dict(values)
                    for method, values in fold.ndcg_by_method.items()
                },
            }
            for fold in folds
        ],
        "summary": summary,
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    concise = {
        method: {
            "weights": result["weights"],
            "mean_ndcg": result["mean_ndcg"],
            "std_ndcg": result["std_ndcg"],
            "mean_drop_from_full": result["mean_drop_from_full"],
            "worse_resume_count": result["worse_resume_count"],
        }
        for method, result in summary.items()
    }
    print(json.dumps(concise, ensure_ascii=False, indent=2))
    print(f"Saved report to {args.output}")


if __name__ == "__main__":
    main()
