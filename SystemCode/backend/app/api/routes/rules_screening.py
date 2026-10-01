from fastapi import APIRouter

from app.schemas.profile import UserProfile
from app.schemas.rules_screening import RulesScreeningResponse
from app.services.rules_screening_service import RulesScreeningService

router = APIRouter()
rules_screening_service = RulesScreeningService()


@router.post("", response_model=RulesScreeningResponse)
def screen_jobs_by_rules(profile: UserProfile) -> RulesScreeningResponse:
    # 规则引擎：按学生画像里的硬约束筛选全部岗位，返回通过筛选的岗位文档和各规则的剔除统计
    return rules_screening_service.run(profile)
