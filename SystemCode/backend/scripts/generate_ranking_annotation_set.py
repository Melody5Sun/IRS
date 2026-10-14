from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import random
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
from app.schemas.profile import JobSearchConstraints, UserProfile
from app.schemas.resume import ParsedResume, ResumeDocument
from app.services.career_intent_match_service import CareerIntentMatchService
from app.services.responsibility_match_service import ResponsibilityMatchService
from app.services.rules_screening_service import RulesScreeningService
from app.services.skill_match_service import SkillMatchService


DEFAULT_CONFIG = BACKEND_ROOT / "evaluation" / "job_ranking" / "profiles.json"
DEFAULT_OUTPUT = BACKEND_ROOT / "evaluation" / "job_ranking"
ANNOTATION_FIELDS = (
    "pair_id",
    "resume_id",
    "resume_pdf",
    "target_roles",
    "job_id",
    "company",
    "title",
    "location",
    "employment_type",
    "summary",
    "responsibilities",
    "required_skills",
    "preferred_skills",
    "label",
    "notes",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a blind, stratified resume-job annotation set."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pairs-per-resume", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20261013)
    return parser.parse_args()


def load_profile(item: dict[str, object]) -> UserProfile:
    resume_path = BACKEND_ROOT / str(item["resume_json"])
    parsed = ParsedResume.model_validate_json(resume_path.read_text(encoding="utf-8"))
    resume = ResumeDocument.model_validate(parsed.model_dump(exclude={"about"}))
    return UserProfile(
        resume=resume,
        constraints=JobSearchConstraints(
            target_roles=list(item["target_roles"]),
            target_industries=[],
            work_modes=[],
            target_employment_types=[],
            notes=parsed.about or "",
        ),
    )


def stratified_sample(
    rows: list[dict[str, object]], count: int, rng: random.Random
) -> list[dict[str, object]]:
    if len(rows) <= count:
        return rows
    ranked = sorted(rows, key=lambda row: (-float(row["baseline_score"]), int(row["job_id"])))
    boundaries = [round(len(ranked) * index / 4) for index in range(5)]
    quartiles = [
        ranked[boundaries[index] : boundaries[index + 1]]
        for index in range(4)
    ]
    quotas = [8, 4, 4, 2]
    selected: list[dict[str, object]] = []
    selected_ids: set[int] = set()
    for bucket, quota in zip(quartiles, quotas, strict=True):
        choices = bucket[:quota] if quota == 8 else rng.sample(bucket, min(quota, len(bucket)))
        for row in choices:
            job_id = int(row["job_id"])
            if job_id not in selected_ids:
                selected.append(row)
                selected_ids.add(job_id)
    remaining = [row for row in ranked if int(row["job_id"]) not in selected_ids]
    rng.shuffle(remaining)
    selected.extend(remaining[: max(0, count - len(selected))])
    rng.shuffle(selected)
    return selected[:count]


def main() -> None:
    args = parse_args()
    if args.pairs_per_resume < 10:
        raise SystemExit("--pairs-per-resume must be at least 10")
    profiles = json.loads(args.config.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    annotation_path = args.output_dir / "annotation_pairs.csv"
    feature_path = args.output_dir / "pair_features.jsonl"

    skill_service = SkillMatchService()
    responsibility_service = ResponsibilityMatchService()
    intent_service = CareerIntentMatchService()
    screening_service = RulesScreeningService()
    overall_scorer = OverallScorer()
    annotation_rows: list[dict[str, object]] = []
    feature_rows: list[dict[str, object]] = []

    for profile_index, config in enumerate(profiles):
        resume_id = str(config["resume_id"])
        split = "validation" if profile_index < 7 else "test"
        profile = load_profile(config)
        screened = screening_service.run(profile)
        prepared = responsibility_service.prepare_candidate(profile.resume)
        scored: list[dict[str, object]] = []
        for job in screened.jobs:
            if job.job_id is None:
                continue
            skill = skill_service.score(SkillScoreRequest(candidate=profile.resume, job=job))
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
            scored.append(
                {
                    "resume_id": resume_id,
                    "split": split,
                    "job": job,
                    "job_id": job.job_id,
                    "baseline_score": overall.final_score,
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
                    "career_intent": (
                        intent.intent_coverage if intent.intent_calculable else None
                    ),
                    "preferred_bonus": skill.preferred_bonus,
                }
            )

        sampled = stratified_sample(
            scored,
            args.pairs_per_resume,
            random.Random(f"{args.seed}:{resume_id}"),
        )
        for sequence, row in enumerate(sampled, start=1):
            job = row.pop("job")
            pair_id = f"{resume_id}-J{job.job_id}"
            annotation_rows.append(
                {
                    "pair_id": pair_id,
                    "resume_id": resume_id,
                    "resume_pdf": config["resume_pdf"],
                    "target_roles": " | ".join(profile.constraints.target_roles),
                    "job_id": job.job_id,
                    "company": job.company,
                    "title": job.title,
                    "location": job.location or "",
                    "employment_type": job.employment_type,
                    "summary": job.summary,
                    "responsibilities": " | ".join(job.responsibilities),
                    "required_skills": " | ".join(job.required_skills),
                    "preferred_skills": " | ".join(job.preferred_skills),
                    "label": "",
                    "notes": "",
                }
            )
            feature_rows.append(
                {
                    "pair_id": pair_id,
                    "resume_id": resume_id,
                    "split": split,
                    "job_id": job.job_id,
                    "sample_sequence": sequence,
                    "hard_constraint_pass": True,
                    "coverages": {
                        name: row[name]
                        for name in (
                            "required_direct",
                            "responsibility",
                            "required_graph",
                            "career_intent",
                        )
                    },
                    "preferred_bonus": row["preferred_bonus"],
                    "baseline_score": row["baseline_score"],
                }
            )
        print(
            f"{resume_id}: {len(screened.jobs)} jobs passed hard constraints; "
            f"sampled {len(sampled)} pairs ({split})."
        )

    annotation_rows.sort(key=lambda row: (str(row["resume_id"]), int(row["job_id"])))
    with annotation_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANNOTATION_FIELDS)
        writer.writeheader()
        writer.writerows(annotation_rows)
    with feature_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in feature_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(annotation_rows)} grouped annotation pairs to {annotation_path}")
    print(f"Wrote scoring features to {feature_path}")


if __name__ == "__main__":
    main()
