from fastapi import APIRouter

from app.schemas.match import (
    CareerIntentScoreRequest,
    CareerIntentScoreResponse,
    ResponsibilityScoreRequest,
    ResponsibilityScoreResponse,
    SkillScoreRequest,
    SkillScoreResponse,
)
from app.services.career_intent_match_service import CareerIntentMatchService
from app.services.responsibility_match_service import ResponsibilityMatchService
from app.services.skill_match_service import SkillMatchService


router = APIRouter()
skill_match_service = SkillMatchService()
responsibility_match_service = ResponsibilityMatchService(persist=False)
career_intent_match_service = CareerIntentMatchService(persist=False)


@router.post("/skills", response_model=SkillScoreResponse)
def score_skills(request: SkillScoreRequest) -> SkillScoreResponse:
    return skill_match_service.score(request)


@router.post("/responsibilities", response_model=ResponsibilityScoreResponse)
def score_responsibilities(
    request: ResponsibilityScoreRequest,
) -> ResponsibilityScoreResponse:
    return responsibility_match_service.score(request)


@router.post("/career-intent", response_model=CareerIntentScoreResponse)
def score_career_intent(request: CareerIntentScoreRequest) -> CareerIntentScoreResponse:
    return career_intent_match_service.score(request)
