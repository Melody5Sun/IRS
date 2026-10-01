from fastapi.testclient import TestClient

from app.api.routes import matches as matches_route
from app.main import app
from app.matching.responsibility_scorer import ResponsibilityScorer
from app.services.responsibility_match_service import ResponsibilityMatchService


client = TestClient(app)


class ApiEmbeddingProvider:
    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors = {
            "Develop and maintain backend APIs": [1.0, 0.0],
            "Experience: Backend Intern. Built and maintained backend APIs.": [1.0, 0.0],
        }
        return [vectors[text] for text in texts]


def test_responsibility_match_api_returns_explainable_score(monkeypatch) -> None:
    service = ResponsibilityMatchService(
        ResponsibilityScorer(ApiEmbeddingProvider())
    )
    monkeypatch.setattr(matches_route, "responsibility_match_service", service)

    response = client.post(
        "/api/matches/responsibilities",
        json={
            "candidate": {
                "name": "Jane Tan",
                "experiences": [
                    {
                        "company": "Acme",
                        "title": "Backend Intern",
                        "description": "Built and maintained backend APIs.",
                    }
                ],
                "projects": [],
                "research": [],
                "skills": ["Python"],
                "educations": [],
                "certificates": [],
                "languages": [],
            },
            "job": {
                "job_id": 38,
                "company": "Example",
                "title": "Backend Engineer",
                "responsibilities": ["Develop and maintain backend APIs"],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == 38
    assert body["responsibility_coverage"] == 100.0
    assert body["responsibility_points"] == 30.0
    assert body["matches"] == [
        {
            "responsibility": "Develop and maintain backend APIs",
            "evidence_type": "experience",
            "evidence_index": 0,
            "evidence_title": "Backend Intern",
            "evidence_text": "Experience: Backend Intern. Built and maintained backend APIs.",
            "similarity": 1.0,
            "coverage": 100.0,
            "status": "matched",
        }
    ]
    assert body["unmatched_responsibilities"] == []
