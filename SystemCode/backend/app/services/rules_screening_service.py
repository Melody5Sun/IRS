from pathlib import Path

from app.rule_engine import screen_jobs, screen_jobs_postgres
from app.schemas.profile import UserProfile
from app.schemas.rules_screening import RulesScreeningResponse


class RulesScreeningService:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path

    def run(self, profile: UserProfile) -> RulesScreeningResponse:
        if self.db_path is None:
            screened = screen_jobs_postgres(profile)
        else:
            screened = screen_jobs(profile, self.db_path)
        return RulesScreeningResponse(
            total_jobs=screened.total_jobs,
            passed_count=len(screened.documents),
            rejected_by_rule=screened.rejected_by_rule,
            jobs=screened.documents,
        )
