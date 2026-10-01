from fastapi.testclient import TestClient
from job_db import make_api_profile

URL = "/api/rules-screening"


def test_rules_screening_returns_only_passed_jobs_with_stats(screening_client: TestClient) -> None:
    response = screening_client.post(URL, json=make_api_profile().model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert (body["total_jobs"], body["passed_count"]) == (4, 2)
    # 3 号行业不符、4 号已下线
    assert body["rejected_by_rule"] == {"industry": 1, "status": 1}
    assert [job["job_id"] for job in body["jobs"]] == [1, 2]
    assert [job["industry"] for job in body["jobs"]] == ["Gaming", "Gaming"]
    assert body["jobs"][0]["title"] == "Backend Engineer"
    assert body["jobs"][0]["required_skills"] == ["python", "sql"]


def test_rules_screening_all_rejected_returns_empty_jobs(screening_client: TestClient) -> None:
    profile = make_api_profile(target_industries=["Cybersecurity"])

    response = screening_client.post(URL, json=profile.model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert (body["total_jobs"], body["passed_count"], body["jobs"]) == (4, 0, [])
    assert body["rejected_by_rule"] == {"industry": 4, "status": 1}


def test_rules_screening_rejects_body_without_resume(screening_client: TestClient) -> None:
    response = screening_client.post(URL, json={"constraints": {}})

    assert response.status_code == 422
