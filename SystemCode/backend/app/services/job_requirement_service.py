from app.parsers.job_requirement_parser import JobRequirementParser
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobAnalysisRequest, JobRequirementDocument
from app.services.gemini_service import GeminiService
from app.services.job_semantic_index_service import JobSemanticIndexService


class JobRequirementService:
    def __init__(
        self,
        parser: JobRequirementParser | None = None,
        repository: JobRepository | None = None,
        gemini_service: GeminiService | None = None,
        semantic_index_service: JobSemanticIndexService | None = None,
    ) -> None:
        self.parser = parser or JobRequirementParser()
        self.repository = repository or JobRepository()
        self.gemini_service = gemini_service or GeminiService()
        self.semantic_index_service = semantic_index_service
        if self.semantic_index_service is None and self.repository._use_postgres:
            self.semantic_index_service = JobSemanticIndexService()

    def analyze_request(self, request: JobAnalysisRequest) -> JobRequirementDocument:
        return self.parser.parse_request(request)

    def analyze_stored_job(self, job_id: int) -> JobRequirementDocument | None:
        job = self.repository.get_job(job_id)
        if job is None:
            return None
        document = self._analyze_job(job)
        if self._has_matching_skills(document):
            self.repository.save_job_analysis(document)
            self._index_semantics(document)
        elif job.id is not None:
            self.repository.mark_job_inactive(
                job.id,
                "No required or preferred skills were extracted from the JD.",
            )
        return document

    def analyze_active_jobs(self, limit: int = 1000) -> int:
        jobs = self.repository.list_jobs(status="active", limit=limit)
        analyzed_count = 0
        for job in jobs:
            document = self._analyze_job(job)
            if self._has_matching_skills(document):
                self.repository.save_job_analysis(document)
                self._index_semantics(document)
                analyzed_count += 1
            elif job.id is not None:
                self.repository.mark_job_inactive(
                    job.id,
                    "No required or preferred skills were extracted from the JD.",
                )
        return analyzed_count

    def _analyze_job(self, job) -> JobRequirementDocument:
        if self.gemini_service.is_configured():
            try:
                return self.gemini_service.extract_job_requirements(job)
            except Exception:
                pass
        return self.parser.parse_posting(job)

    def _has_matching_skills(self, document: JobRequirementDocument) -> bool:
        return bool(document.required_skills or document.preferred_skills)

    def _index_semantics(self, document: JobRequirementDocument) -> None:
        if self.semantic_index_service is not None:
            self.semantic_index_service.index(document)
