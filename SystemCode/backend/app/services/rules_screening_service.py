from app.rule_engine import screen_jobs
from app.schemas.profile import UserProfile
from app.schemas.rules_screening import RulesScreeningResponse


class RulesScreeningService:
    def run(self, profile: UserProfile) -> RulesScreeningResponse:
        screened = screen_jobs(profile)
        return RulesScreeningResponse(
            total_jobs=screened.total_jobs,
            passed_count=len(screened.documents),
            rejected_by_rule=screened.rejected_by_rule,
            jobs=screened.documents,
        )
