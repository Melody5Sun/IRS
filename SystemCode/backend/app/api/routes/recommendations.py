from fastapi import APIRouter

from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.recommendation_service import RecommendationService

router = APIRouter()
recommendation_service = RecommendationService()


@router.post("", response_model=RecommendationResponse)
def recommend_jobs(request: RecommendationRequest) -> RecommendationResponse:
    return recommendation_service.recommend(request)
