from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_skill_match_api_scores_formatted_resume_against_structured_jd() -> None:
    response = client.post(
        "/api/matches/skills",
        json={
            "candidate": {
                "name": "Jane Tan",
                "skills": ["Python", "FastAPI", "Docker"],
                "experiences": [],
                "projects": [],
                "research": [],
                "educations": [],
                "certificates": [],
                "languages": [],
            },
            "job": {
                "job_id": 1,
                "company": "Acme",
                "title": "Backend Engineer",
                "required_skills": ["python", "sql", "kubernetes"],
                "preferred_skills": ["fastapi", "aws"],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["required_direct_coverage"] == 33.33
    assert body["required_direct_points"] == 13.33
    assert body["required_graph_coverage"] == 43.33
    assert body["required_graph_points"] == 8.67
    assert body["preferred_skill_coverage"] == 50.0
    assert body["preferred_bonus"] == 2.5
    assert body["partial_score"] == 24.5
    assert body["direct_required_matches"] == [
        {"jd_skill": "python", "candidate_skill": "Python"}
    ]
    assert body["graph_required_matches"] == [
        {
            "jd_skill": "kubernetes",
            "candidate_skill": "Docker",
            "relation": "required_skill_builds_on_candidate_skill",
            "relation_score": 0.3,
            "path": ["Docker", "Kubernetes"],
        }
    ]
    assert body["missing_required_skills"] == ["sql"]
