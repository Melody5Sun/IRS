from functools import lru_cache

from fastapi import APIRouter, HTTPException

from app.ingestion.job_sync_service import JobSyncService
from app.repositories.job_repository import JobRepository
from app.schemas.job import (
    CompanySource,
    CompanySourceResponse,
    JobAnalysis,
    JobAnalysisRequest,
    JobListResponse,
    JobRequirementDocument,
    JobSyncResponse,
)
from app.services.job_requirement_service import JobRequirementService
from app.services.job_service import JobService

router = APIRouter()
job_service = JobService()
job_repository = JobRepository()
job_requirement_service = JobRequirementService(repository=job_repository)


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
