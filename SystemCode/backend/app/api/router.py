from fastapi import APIRouter

from app.api.routes import (
    health,
    interview_transcriptions,
    jobs,
    matches,
    profile,
    ranking,
    recommendations,
    resumes,
    rules_screening,
    targets,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(
    interview_transcriptions.router,
    prefix="/jobs",
    tags=["interviews"],
)
api_router.include_router(matches.router, prefix="/matches", tags=["matches"])
api_router.include_router(rules_screening.router, prefix="/rules-screening", tags=["rules-screening"])
api_router.include_router(ranking.router, prefix="/ranking", tags=["ranking"])
api_router.include_router(targets.router, prefix="/targets", tags=["targets"])
api_router.include_router(
    recommendations.router,
    prefix="/recommendations",
    tags=["recommendations"],
)
