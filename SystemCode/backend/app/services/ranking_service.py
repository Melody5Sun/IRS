from app.matching.overall_scorer import OverallScorer
from app.schemas.match import (
    CareerIntentScoreRequest,
    ResponsibilityScoreRequest,
    SkillScoreRequest,
)
from app.schemas.profile import UserProfile
from app.schemas.ranking import RankedJob, RankingResponse
from app.services.career_intent_match_service import CareerIntentMatchService
from app.services.responsibility_match_service import ResponsibilityMatchService
from app.services.rules_screening_service import RulesScreeningService
from app.services.skill_match_service import SkillMatchService


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
        results = []
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
            results.append(
                RankedJob(
                    job_id=job.job_id,
                    company=job.company,
                    title=job.title,
                    skill_score=skill_score,
                    responsibility_score=responsibility_score,
                    career_intent_score=career_intent_score,
                    overall_score=self.overall_scorer.combine(
                        skill_score,
                        responsibility_score,
                        career_intent_score,
                    ),
                )
            )
        # 稳定排序：分数相同的岗位保持 job_id 升序
        results.sort(key=lambda item: item.overall_score.final_score, reverse=True)
        return RankingResponse(
            total_jobs=screened.total_jobs,
            passed_count=screened.passed_count,
            rejected_by_rule=screened.rejected_by_rule,
            results=results,
        )
