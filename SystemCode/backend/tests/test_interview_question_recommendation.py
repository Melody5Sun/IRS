from fastapi.testclient import TestClient
import pytest

from app.api.routes import jobs as jobs_route
from app.main import app
from app.repositories.interview_recommendation_repository import (
    InterviewCandidateQuestion,
    InterviewJobContext,
    InterviewRoleMatch,
)
from app.schemas.interview_question import GENERAL_PROGRAMMING_ROLE
from app.schemas.interview_recommendation import InterviewQuestionSampleRequest
from app.services.interview_question_recommendation_service import (
    InterviewJobNotFoundError,
    InterviewQuestionRecommendationService,
    InterviewRoleMatchesUnavailableError,
)


ROLE_MATCHES = [
    InterviewRoleMatch(role="Backend Developer", similarity=0.6, rank=1),
    InterviewRoleMatch(role="Database Administrator", similarity=0.3, rank=2),
    InterviewRoleMatch(role="Full Stack Developer", similarity=0.1, rank=3),
]


def make_question(
    question_id: int,
    role: str,
    difficulty: str,
) -> InterviewCandidateQuestion:
    return InterviewCandidateQuestion(
        id=question_id,
        question_text=f"中文题目 {question_id}",
        standard_answer=f"中文答案 {question_id}",
        question_text_en=f"English question {question_id}",
        standard_answer_en=f"English answer {question_id}",
        difficulty_level=difficulty,
        roles=(role,),
        source="test-source",
        company=None,
    )


def make_candidates() -> list[InterviewCandidateQuestion]:
    questions = [
        make_question(1, GENERAL_PROGRAMMING_ROLE, "easy"),
        make_question(2, GENERAL_PROGRAMMING_ROLE, "medium"),
        make_question(3, GENERAL_PROGRAMMING_ROLE, "hard"),
    ]
    question_id = 10
    for role in [item.role for item in ROLE_MATCHES]:
        for difficulty in ("easy", "medium", "hard"):
            for _ in range(5):
                questions.append(make_question(question_id, role, difficulty))
                question_id += 1
    return questions


class FakeRepository:
    def __init__(self, *, job_exists: bool = True, role_matches=None, candidates=None):
        self.job_exists = job_exists
        self.role_matches = ROLE_MATCHES if role_matches is None else role_matches
        self.candidates = make_candidates() if candidates is None else candidates

    def get_job_context(self, job_id: int):
        if not self.job_exists:
            return None
        return InterviewJobContext(job_id=job_id, title="Backend Engineer Intern")

    def list_role_matches(self, job_id: int, limit: int = 3):
        return self.role_matches[:limit]

    def list_candidates(self, roles, exclude_question_ids=None):
        excluded = set(exclude_question_ids or [])
        return [item for item in self.candidates if item.id not in excluded]


def test_default_sample_uses_basic_questions_role_scores_and_difficulty_mix() -> None:
    service = InterviewQuestionRecommendationService(FakeRepository())

    response = service.sample(8, InterviewQuestionSampleRequest(seed=42))

    assert response.returned_count == 10
    assert response.basic_question_count == 3
    assert response.difficulty_distribution.model_dump() == {
        "easy": 4,
        "medium": 4,
        "hard": 2,
    }
    assert [item.requested_quota for item in response.role_allocation] == [4, 2, 1]
    assert [item.actual_count for item in response.role_allocation] == [4, 2, 1]
    assert len({item.id for item in response.questions}) == 10
    assert all(item.standard_answer and item.standard_answer_en for item in response.questions)


def test_same_seed_reproduces_questions_and_exclusions_are_honored() -> None:
    service = InterviewQuestionRecommendationService(FakeRepository())
    request = InterviewQuestionSampleRequest(seed=90210, exclude_question_ids=[1])

    first = service.sample(8, request)
    second = service.sample(8, request)

    assert [item.id for item in first.questions] == [item.id for item in second.questions]
    assert 1 not in {item.id for item in first.questions}


def test_missing_job_and_role_matches_raise_domain_errors() -> None:
    with pytest.raises(InterviewJobNotFoundError):
        InterviewQuestionRecommendationService(
            FakeRepository(job_exists=False)
        ).sample(999, InterviewQuestionSampleRequest())

    with pytest.raises(InterviewRoleMatchesUnavailableError):
        InterviewQuestionRecommendationService(
            FakeRepository(role_matches=[])
        ).sample(8, InterviewQuestionSampleRequest())


class FakeRouteService:
    def sample(self, job_id, request):
        raise InterviewJobNotFoundError(f"Job {job_id} was not found.")


def test_api_returns_404_for_unknown_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        jobs_route,
        "interview_question_recommendation_service",
        FakeRouteService(),
    )
    response = TestClient(app).post(
        "/api/jobs/999/interview-questions/sample",
        json={"count": 10, "seed": 1},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job 999 was not found."
