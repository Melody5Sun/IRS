from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.matching.overall_scorer import OverallScorer
from app.schemas.match import (
    CareerIntentScoreRequest,
    ResponsibilityScoreRequest,
    SkillScoreRequest,
)
from app.services.career_intent_match_service import CareerIntentMatchService
from app.services.responsibility_match_service import ResponsibilityMatchService
from app.services.rules_screening_service import RulesScreeningService
from app.services.skill_match_service import SkillMatchService
from scripts.generate_ranking_annotation_set import load_profile


DEFAULT_DIR = BACKEND_ROOT / "evaluation" / "job_ranking"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute scoring features for an existing annotation set."
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=DEFAULT_DIR / "annotation_pairs_ai_labeled_professional_v2.csv",
    )
    parser.add_argument("--profiles", type=Path, default=DEFAULT_DIR / "profiles.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DIR / "pair_features_resume_segments_v4.jsonl",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gb18030")
    return list(csv.DictReader(text.splitlines()))


def main() -> None:
    args = parse_args()
    annotation_rows = read_csv(args.annotations)
    annotations_by_resume: dict[str, list[dict[str, str]]] = {}
    for row in annotation_rows:
        annotations_by_resume.setdefault(row["resume_id"], []).append(row)

    profile_configs = json.loads(args.profiles.read_text(encoding="utf-8"))
    skill_service = SkillMatchService()
    responsibility_service = ResponsibilityMatchService()
    intent_service = CareerIntentMatchService()
    screening_service = RulesScreeningService()
    overall_scorer = OverallScorer()
    feature_rows: list[dict[str, object]] = []

    for profile_index, config in enumerate(profile_configs):
        resume_id = str(config["resume_id"])
        requested_rows = annotations_by_resume.get(resume_id, [])
        if not requested_rows:
            continue
        profile = load_profile(config)
        jobs = {
            job.job_id: job
            for job in screening_service.run(profile).jobs
            if job.job_id is not None
        }
        prepared = responsibility_service.prepare_candidate(profile.resume)
        for annotation in requested_rows:
            job_id = int(annotation["job_id"])
            job = jobs.get(job_id)
            if job is None:
                raise ValueError(f"{annotation['pair_id']}: job no longer passes hard constraints")
            skill = skill_service.score(
                SkillScoreRequest(candidate=profile.resume, job=job)
            )
            responsibility = responsibility_service.score(
                ResponsibilityScoreRequest(candidate=profile.resume, job=job),
                prepared_evidence=prepared,
            )
            intent = intent_service.score(
                CareerIntentScoreRequest(
                    target_roles=profile.constraints.target_roles,
                    job=job,
                )
            )
            overall = overall_scorer.combine(skill, responsibility, intent)
            feature_rows.append(
                {
                    "pair_id": annotation["pair_id"],
                    "resume_id": resume_id,
                    "split": "validation" if profile_index < 7 else "test",
                    "job_id": job_id,
                    "hard_constraint_pass": True,
                    "coverages": {
                        "required_direct": (
                            skill.required_direct_coverage
                            if skill.required_skills_calculable
                            else None
                        ),
                        "responsibility": (
                            responsibility.responsibility_coverage
                            if responsibility.responsibilities_calculable
                            else None
                        ),
                        "required_graph": (
                            skill.required_graph_coverage
                            if skill.required_skills_calculable
                            else None
                        ),
                    },
                    "preferred_bonus": skill.preferred_bonus,
                    "baseline_score": overall.professional_score,
                }
            )

    if len(feature_rows) != len(annotation_rows):
        raise ValueError(
            f"Expected {len(annotation_rows)} features, generated {len(feature_rows)}"
        )
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in feature_rows),
        encoding="utf-8",
    )
    print(f"Wrote {len(feature_rows)} recomputed features to {args.output}")


if __name__ == "__main__":
    main()
