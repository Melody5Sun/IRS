from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

from app.api.routes import jobs as jobs_route
from app.main import app
from app.schemas.job import JobPosting, JobRequirementDocument
from app.schemas.match import (
    CareerIntentScoreResponse,
    DirectSkillMatch,
    GraphSkillMatch,
    ResponsibilityEvidenceMatch,
    ResponsibilityScoreResponse,
    SkillScoreResponse,
    StandardRoleSimilarity,
)
from app.schemas.profile import JobSearchConstraints, UserProfile
from app.schemas.resume import ResumeDocument
from app.services.job_match_detail_service import (
    JobMatchDetailNotFoundError,
    JobMatchDetailService,
)


NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


class FakeJobRepository:
    def get_job(self, job_id: int):
        if job_id == 404:
            return None
        return JobPosting(
            id=job_id,
            source="test-source",
            company="Example Company",
            external_id="external-1",
            title="Backend Engineer Intern",
            location="Singapore",
            description="Build backend services.",
            url="https://example.com/jobs/1",
            employment_type="internship",
            collected_at=NOW,
            last_seen_at=NOW,
            content_hash="hash",
        )


class FakeSemanticRepository:
    def get_analyzed_job(self, job_id: int):
        return JobRequirementDocument(
            job_id=job_id,
            company="Example Company",
            title="Backend Engineer Intern",
            summary="Build payment backend services.",
            employment_type="internship",
            responsibilities=["Develop REST APIs", "Operate Kubernetes workloads"],
            required_skills=["Python", "Kubernetes", "SQL"],
            preferred_skills=["AWS", "Terraform"],
        )


class FakeSkillService:
    def score(self, request):
        return SkillScoreResponse(
            job_id=request.job.job_id,
            required_skills_calculable=True,
            preferred_skills_available=True,
            required_direct_coverage=50,
            required_direct_points=20,
            required_graph_coverage=50,
            required_graph_points=10,
            preferred_direct_coverage=50,
            preferred_graph_coverage=0,
            preferred_skill_coverage=35,
            preferred_bonus=3.5,
            partial_score=33.5,
            direct_required_matches=[
                DirectSkillMatch(jd_skill="Python", candidate_skill="Python")
            ],
            graph_required_matches=[
                GraphSkillMatch(
                    jd_skill="Kubernetes",
                    candidate_skill="Docker",
                    relation="related",
                    relation_score=0.75,
                    path=["Docker", "Kubernetes"],
                )
            ],
            missing_required_skills=["SQL"],
            direct_preferred_matches=[
                DirectSkillMatch(jd_skill="AWS", candidate_skill="AWS")
            ],
            missing_preferred_skills=["Terraform"],
        )


class FakeResponsibilityService:
    def score(self, request):
        return ResponsibilityScoreResponse(
            job_id=request.job.job_id,
            responsibilities_calculable=True,
            resume_evidence_available=True,
            responsibility_count=2,
            evidence_count=1,
            responsibility_coverage=50,
            responsibility_points=15,
            matches=[
                ResponsibilityEvidenceMatch(
                    responsibility="Develop REST APIs",
                    evidence_type="experience",
                    evidence_index=0,
                    evidence_title="Backend Intern",
                    evidence_text="Experience: Backend Intern. Developed REST APIs.",
                    similarity=0.86,
                    coverage=100,
                    status="matched",
                )
            ],
            unmatched_responsibilities=["Operate Kubernetes workloads"],
        )


class FakeCareerIntentService:
    def score(self, request):
        return CareerIntentScoreResponse(
            job_id=request.job.job_id,
            intent_calculable=True,
            best_target_role="Backend Developer",
            intent_similarity=0.82,
            intent_coverage=80,
            career_intent_points=8,
            target_role_matches=[
                StandardRoleSimilarity(role="Backend Developer", similarity=0.82)
            ],
            top_standard_roles=[
                StandardRoleSimilarity(role="Backend Developer", similarity=0.9)
            ],
        )


def make_service() -> JobMatchDetailService:
    return JobMatchDetailService(
        job_repository=FakeJobRepository(),
        semantic_repository=FakeSemanticRepository(),
        skill_match_service=FakeSkillService(),
        responsibility_match_service=FakeResponsibilityService(),
        career_intent_match_service=FakeCareerIntentService(),
    )


def make_profile() -> UserProfile:
    return UserProfile(
        resume=ResumeDocument(skills=["Python", "Docker", "AWS"]),
        constraints=JobSearchConstraints(target_roles=["Backend Developer"]),
    )


def test_detail_returns_job_score_recommendation_evidence_and_gaps() -> None:
    response = make_service().get_detail(1, make_profile())

    assert response.job.job_id == 1
    assert response.match.final_score == 56.5
    assert response.match.component_points.model_dump() == {
        "required_skill_direct": 20.0,
        "responsibility": 15.0,
        "required_skill_graph": 10.0,
        "career_intent": 8.0,
    }
    assert response.recommendation.highlights
    assert response.recommendation.level == "moderate"
    assert response.recommendation.level_label == "Moderate match"
    assert response.recommendation.summary == "Your profile has a useful foundation for this role."
    assert response.recommendation.highlights == [
        "Your Python skills meet required skill expectations.",
        "Your Docker experience provides a transferable foundation for the required Kubernetes skills.",
        "Your resume evidence from Backend Intern experience is relevant to this role's responsibilities.",
        "This role is strongly aligned with your target role: Backend Developer.",
        "Your AWS skills align with the role's preferred skills.",
    ]
    recommendation_text = " ".join(
        [response.recommendation.summary, *response.recommendation.highlights]
    )
    assert "56.5" not in recommendation_text
    assert "/" not in recommendation_text
    assert "%" not in recommendation_text
    assert {item.match_type for item in response.recommendation.evidence} == {
        "direct_skill",
        "knowledge_graph",
        "preferred_skill",
        "responsibility_semantic",
        "career_intent",
    }
    assert {item.gap_type for item in response.gaps} == {
        "transferable",
        "hard_gap",
        "optional_gap",
        "experience_gap",
    }
    assert "SQL" in response.improvement_plan.summary
    assert "Docker" in response.improvement_plan.summary
    assert "Operate Kubernetes workloads" in response.improvement_plan.summary
    assert "Terraform" in response.improvement_plan.summary
    assert [item.title for item in response.improvement_plan.priorities] == [
        "Build required skills",
        "Strengthen transferable evidence",
        "Add responsibility evidence",
        "Add preferred skills",
    ]
    assert response.improvement_plan.next_action.startswith("Start with SQL")


def test_detail_raises_not_found_for_unknown_job() -> None:
    with pytest.raises(JobMatchDetailNotFoundError):
        make_service().get_detail(404, make_profile())


class FakeMissingJobService:
    def get_detail(self, job_id, profile):
        raise JobMatchDetailNotFoundError(f"Job {job_id} was not found.")


def test_detail_api_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs_route, "job_match_detail_service", FakeMissingJobService())

    response = TestClient(app).post(
        "/api/jobs/404/match-detail",
        json=make_profile().model_dump(mode="json"),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job 404 was not found."
