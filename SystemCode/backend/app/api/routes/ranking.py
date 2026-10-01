from fastapi import APIRouter

from app.schemas.profile import UserProfile
from app.schemas.ranking import RankingResponse
from app.services.career_intent_match_service import CareerIntentMatchService
from app.services.ranking_service import RankingService
from app.services.responsibility_match_service import ResponsibilityMatchService
from app.services.rules_screening_service import RulesScreeningService
from app.services.skill_match_service import SkillMatchService

router = APIRouter()
ranking_service = RankingService(
    RulesScreeningService(),
    SkillMatchService(),
    ResponsibilityMatchService(),
    CareerIntentMatchService(),
)


@router.post("", response_model=RankingResponse)
def rank_jobs(profile: UserProfile) -> RankingResponse:
    # 入口：规则初筛 -> 四项核心评分 + 加分技能 -> 按最终分降序
    return ranking_service.run(profile)
