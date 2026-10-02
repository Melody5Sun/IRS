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


class RankingService:
    """Apply hard constraints, calculate all match components, and rank by final score."""

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
        scored_jobs: list[tuple[float, JobRequirementDocument]] = []
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
            scored_jobs.append((overall_score.final_score, job))

        # 稳定排序：分数相同的岗位按 job_id 升序，前端翻页时顺序不会漂移。
        scored_jobs.sort(
            key=lambda item: (
                -item[0],
                item[1].job_id if item[1].job_id is not None else float("inf"),
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
                final_score=final_score,
            )
            for index, (final_score, job) in enumerate(
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
