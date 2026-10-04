from functools import lru_cache

from fastapi import APIRouter, HTTPException

from app.ingestion.job_sync_service import JobSyncService
from app.repositories.job_repository import JobRepository
from app.schemas.job import (
    CompanySource,
    CompanySourceResponse,
    JobAnalysis,
    JobAnalysisRequest,
    JobLibraryStatus,
    JobListResponse,
    JobRequirementDocument,
    JobSyncResponse,
)
from app.schemas.interview_recommendation import (
    InterviewQuestionSampleRequest,
    InterviewQuestionSampleResponse,
)
from app.schemas.job_match_detail import JobMatchDetailResponse
from app.schemas.profile import UserProfile
from app.services.interview_question_recommendation_service import (
    InterviewJobNotFoundError,
    InterviewQuestionRecommendationService,
    InterviewRoleMatchesUnavailableError,
)
from app.services.job_match_detail_service import (
    JobMatchDetailAnalysisUnavailableError,
    JobMatchDetailNotFoundError,
    JobMatchDetailService,
)
from app.services.job_requirement_service import JobRequirementService
from app.services.job_service import JobService

router = APIRouter()
job_service = JobService()
job_repository = JobRepository()
job_requirement_service = JobRequirementService(repository=job_repository)
interview_question_recommendation_service = InterviewQuestionRecommendationService()
job_match_detail_service = JobMatchDetailService()


# JobSyncService 构造时会读写数据库，延迟到第一次请求再创建，避免 import app 就改写 data/careerpilot.db
@lru_cache
def get_job_sync_service() -> JobSyncService:
    return JobSyncService(repository=job_repository)


@router.post("/analyze", response_model=JobAnalysis)
def analyze_job(request: JobAnalysisRequest) -> JobAnalysis:
    return job_service.analyze(request)


@router.post("/analyze-requirements", response_model=JobRequirementDocument)
def analyze_job_requirements(request: JobAnalysisRequest) -> JobRequirementDocument:
    return job_requirement_service.analyze_request(request)


@router.get("", response_model=JobListResponse)
def list_jobs(status: str = "active", company: str | None = None, limit: int = 100) -> JobListResponse:
    jobs = job_repository.list_jobs(status=status, company=company, limit=limit)
    return JobListResponse(jobs=jobs)


@router.get("/library-status", response_model=JobLibraryStatus)
def get_library_status() -> JobLibraryStatus:
    """JD 库最近同步时间和在招岗位数，前端每页顶栏显示。"""
    return job_repository.library_status()


@router.get("/sources", response_model=CompanySourceResponse)
def list_company_sources(enabled_only: bool = False) -> CompanySourceResponse:
    job_repository.ensure_company_sources(get_job_sync_service().sources)
    sources = job_repository.list_company_sources(enabled_only=enabled_only)
    return CompanySourceResponse(sources=[CompanySource(**source.__dict__) for source in sources])


@router.post("/sync", response_model=JobSyncResponse)
def sync_jobs() -> JobSyncResponse:
    return get_job_sync_service().sync()


@router.post("/{job_id}/analyze-requirements", response_model=JobRequirementDocument)
def analyze_stored_job_requirements(job_id: int) -> JobRequirementDocument:
    document = job_requirement_service.analyze_stored_job(job_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return document


@router.post("/{job_id}/match-detail", response_model=JobMatchDetailResponse)
def get_job_match_detail(
    job_id: int,
    profile: UserProfile,
) -> JobMatchDetailResponse:
    try:
        return job_match_detail_service.get_detail(job_id, profile)
    except JobMatchDetailNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except JobMatchDetailAnalysisUnavailableError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/{job_id}/interview-questions/sample",
    response_model=InterviewQuestionSampleResponse,
)
def sample_interview_questions(
    job_id: int,
    request: InterviewQuestionSampleRequest,
) -> InterviewQuestionSampleResponse:
    try:
        return interview_question_recommendation_service.sample(job_id, request)
    except InterviewJobNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except InterviewRoleMatchesUnavailableError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
