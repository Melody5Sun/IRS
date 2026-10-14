from app.matching.overall_scorer import OverallScorer
from app.schemas.match import (
    CareerIntentScoreRequest,
    ResponsibilityScoreRequest,
    SkillScoreRequest,
)
from app.schemas.job import JobRequirementDocument
from app.schemas.profile import UserProfile
from app.schemas.ranking import RankedJob, RankingResponse
from app.services.career_intent_match_service import CareerIntentMatchService
from app.services.responsibility_match_service import ResponsibilityMatchService
from app.services.rules_screening_service import RulesScreeningService
from app.services.skill_match_service import SkillMatchService

RANKING_RESULT_LIMIT = 30


def recommendation_level_rank(professional_score: float) -> int:
    """Mirror the four recommendation levels displayed by the frontend."""
    if professional_score >= 13:
        return 3
    if professional_score >= 7:
        return 2
    if professional_score >= 1:
        return 1
    return 0


def ranking_sort_key(
    professional_score: float,
    intent_fit: float | None,
    job_id: int | None,
) -> tuple[float, float, float, float]:
    return (
        -recommendation_level_rank(professional_score),
        -(intent_fit if intent_fit is not None else 0.0),
        -professional_score,
        job_id if job_id is not None else float("inf"),
    )


class RankingService:
    """Rank by professional-fit tier, then career intent within each tier."""

    def __init__(
        self,
        rules_screening_service: RulesScreeningService,
        skill_match_service: SkillMatchService,
        responsibility_match_service: ResponsibilityMatchService | None = None,
        career_intent_match_service: CareerIntentMatchService | None = None,
        overall_scorer: OverallScorer | None = None,
    ) -> None:
        self.rules_screening_service = rules_screening_service
        self.skill_match_service = skill_match_service
        self.responsibility_match_service = (
            responsibility_match_service or ResponsibilityMatchService()
        )
        self.career_intent_match_service = (
            career_intent_match_service or CareerIntentMatchService()
        )
        self.overall_scorer = overall_scorer or OverallScorer()

    def run(self, profile: UserProfile) -> RankingResponse:
        screened = self.rules_screening_service.run(profile)
        scored_jobs: list[tuple[float, float, float | None, JobRequirementDocument]] = []
        prepared_evidence = self.responsibility_match_service.prepare_candidate(
            profile.resume
        )
        for job in screened.jobs:
            skill_score = self.skill_match_service.score(
                SkillScoreRequest(candidate=profile.resume, job=job)
            )
            responsibility_score = self.responsibility_match_service.score(
                ResponsibilityScoreRequest(candidate=profile.resume, job=job),
                prepared_evidence=prepared_evidence,
            )
            career_intent_score = self.career_intent_match_service.score(
                CareerIntentScoreRequest(
                    target_roles=profile.constraints.target_roles,
                    job=job,
                )
            )
            overall_score = self.overall_scorer.combine(
                skill_score,
                responsibility_score,
                career_intent_score,
            )
            scored_jobs.append(
                (
                    overall_score.final_score,
                    overall_score.professional_score,
                    overall_score.intent_fit,
                    job,
                )
            )

        # 先保证专业匹配等级顺序，再在同一等级内按用户意向重排。
        scored_jobs.sort(
            key=lambda item: ranking_sort_key(
                item[1],
                item[2],
                item[3].job_id,
            )
        )
        results = [
            RankedJob(
                rank=index,
                job_id=job.job_id,
                company=job.company,
                title=job.title,
                location=job.location,
                employment_type=job.employment_type,
                professional_score=professional_score,
                intent_fit=intent_fit,
                final_score=final_score,
            )
            for index, (final_score, professional_score, intent_fit, job) in enumerate(
                scored_jobs[:RANKING_RESULT_LIMIT],
                start=1,
            )
            if job.job_id is not None
        ]
        return RankingResponse(
            total_jobs=screened.total_jobs,
            passed_count=screened.passed_count,
            returned_count=len(results),
            rejected_by_rule=screened.rejected_by_rule,
            results=results,
        )
