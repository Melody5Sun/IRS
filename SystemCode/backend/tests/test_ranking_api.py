from fastapi.testclient import TestClient
import pytest

from app.rule_engine import engine as rule_engine
from job_db import make_api_profile, make_rows

RANKING_URL = "/api/ranking"


def test_ranking_scores_only_screened_jobs_in_descending_order(screening_client: TestClient) -> None:
    response = screening_client.post(RANKING_URL, json=make_api_profile().model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert (body["total_jobs"], body["passed_count"], body["returned_count"]) == (4, 2, 2)
    assert body["rejected_by_rule"] == {"industry": 1, "status": 1}
    # 被规则剔除的 3、4 号不会进入技能评分；候选人有 Python/SQL，1 号全命中，分数更高
    assert [item["job_id"] for item in body["results"]] == [1, 2]
    scores = [item["final_score"] for item in body["results"]]
    assert scores[0] > scores[1]
    assert body["results"][0] == {
        "rank": 1,
        "job_id": 1,
        "company": "Alpha",
        "title": "Backend Engineer",
        "location": None,
        "employment_type": "not_stated",
        "final_score": scores[0],
    }


def test_ranking_all_rejected_returns_empty_results(screening_client: TestClient) -> None:
    profile = make_api_profile(target_industries=["Cybersecurity"])

    response = screening_client.post(RANKING_URL, json=profile.model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert (
        body["total_jobs"],
        body["passed_count"],
        body["returned_count"],
        body["results"],
    ) == (4, 0, 0, [])


def test_ranking_rejects_body_without_resume(screening_client: TestClient) -> None:
    assert screening_client.post(RANKING_URL, json={"constraints": {}}).status_code == 422


def test_ranking_returns_only_top_30_with_stable_tie_order(
    monkeypatch: pytest.MonkeyPatch,
    screening_client: TestClient,
) -> None:
    jobs = tuple(
        {
            "id": job_id,
            "title": f"Backend Engineer {job_id}",
            "company": f"Company {job_id}",
            "industry": "Gaming",
            "employment_type": "internship",
            "required_skills": ["python"],
        }
        for job_id in range(1, 36)
    )
    monkeypatch.setattr(rule_engine, "load_job_rows", lambda: make_rows(*jobs))

    response = screening_client.post(
        RANKING_URL,
        json=make_api_profile().model_dump(mode="json"),
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["passed_count"], body["returned_count"]) == (35, 30)
    assert [item["job_id"] for item in body["results"]] == list(range(1, 31))
    assert [item["rank"] for item in body["results"]] == list(range(1, 31))
