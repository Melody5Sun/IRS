from fastapi import APIRouter, HTTPException

from app.schemas.ranking import RankingResponse
from app.services.career_intent_match_service import CareerIntentMatchService
from app.services.profile_service import profile_service
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
def rank_jobs() -> RankingResponse:
    # 入口：规则初筛 -> 四项核心评分 + 加分技能 -> 返回轻量 Top 30。
    # 用库里保存的画像实时计算，画像更新后再调用就是重排后的结果
    profile = profile_service.get()
    if profile is None:
        raise HTTPException(status_code=409, detail="请先上传简历并补全保存画像")
    return ranking_service.run(profile)
