from pathlib import Path

from fastapi.testclient import TestClient

from app.api.v1.routes import matches as matches_route
from app.core.config import settings
from app.knowledge.role_taxonomy import RoleTaxonomy
from app.main import app
from app.matching.career_intent_scorer import CareerIntentScorer
from app.schemas.job import JobRequirementDocument
from app.services.career_intent_match_service import CareerIntentMatchService
from app.repositories.job_semantic_repository import StoredRoleMatch


client = TestClient(app)


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        vectors = []
        for text in texts:
            if "Backend Developer" in text or "backend APIs" in text:
                vectors.append([1.0, 0.0])
            elif "Frontend Developer" in text:
                vectors.append([0.0, 1.0])
            else:
                vectors.append([0.5, 0.5])
        return vectors


def build_scorer(tmp_path: Path, provider: FakeEmbeddingProvider) -> CareerIntentScorer:
    return CareerIntentScorer(
        embedding_provider=provider,
        taxonomy_path=settings.role_taxonomy_path,
        model_name="test-model",
        similarity_floor=0.40,
        similarity_full=0.85,
    )


def test_role_taxonomy_covers_all_target_roles() -> None:
    taxonomy = RoleTaxonomy.load(settings.role_taxonomy_path)
    assert len(taxonomy.profiles) == 66
    assert len(taxonomy.by_role) == 66


def test_career_intent_uses_best_selected_role_with_in_memory_vectors(tmp_path: Path) -> None:
    provider = FakeEmbeddingProvider()
    scorer = build_scorer(tmp_path, provider)
    result = scorer.score(
        ["Frontend Developer", "Backend Developer"],
        JobRequirementDocument(
            job_id=7,
            company="Example",
            title="Software Engineer Intern",
            responsibilities=["Develop backend APIs"],
            required_skills=["Python", "SQL"],
        ),
    )

    assert result.intent_calculable is True
    assert result.best_target_role == "Backend Developer"
    assert result.intent_similarity == 1.0
    assert result.intent_coverage == 100.0
    assert result.career_intent_points == 10.0
    assert result.top_standard_roles[0].role == "Backend Developer"
    assert len(provider.calls[0]) == 66


def test_career_intent_api(monkeypatch, tmp_path: Path) -> None:
    service = CareerIntentMatchService(build_scorer(tmp_path, FakeEmbeddingProvider()))
    monkeypatch.setattr(matches_route, "career_intent_match_service", service)

    response = client.post(
        "/api/v1/matches/career-intent",
        json={
            "target_roles": ["Backend Developer"],
            "job": {
                "job_id": 8,
                "company": "Example",
                "title": "Backend Engineering Intern",
                "responsibilities": ["Develop backend APIs"],
                "required_skills": ["Python"],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["best_target_role"] == "Backend Developer"
    assert response.json()["career_intent_points"] == 10.0


def test_career_intent_api_rejects_unknown_target_role() -> None:
    response = client.post(
        "/api/v1/matches/career-intent",
        json={
            "target_roles": ["Backend Engineer"],
            "job": {"company": "Example", "title": "Backend Engineer"},
        },
    )
    assert response.status_code == 422


class FakeSemanticRepository:
    def __init__(self) -> None:
        self.matches: list[StoredRoleMatch] | None = None

    def load_role_matches(self, job_id, **metadata):
        return self.matches

    def save_role_matches(self, job_id, matches, **metadata) -> None:
        self.matches = matches


def test_career_intent_service_reuses_persisted_top_k(tmp_path: Path) -> None:
    provider = FakeEmbeddingProvider()
    repository = FakeSemanticRepository()
    service = CareerIntentMatchService(
        build_scorer(tmp_path, provider),
        repository=repository,
    )
    job = JobRequirementDocument(
        job_id=7,
        company="Example",
        title="Backend Engineering Intern",
        responsibilities=["Develop backend APIs"],
        required_skills=["Python"],
    )

    first = service.ensure_role_matches(job)
    call_count = len(provider.calls)
    second = service.ensure_role_matches(job)

    assert len(first) == 3
    assert second == first
    assert len(provider.calls) == call_count
