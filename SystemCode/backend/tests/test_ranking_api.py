from fastapi.testclient import TestClient
from job_db import make_api_profile

RANKING_URL = "/api/ranking"
SCREENING_URL = "/api/rules-screening"
SKILLS_URL = "/api/matches/skills"


def test_ranking_scores_only_screened_jobs_in_descending_order(screening_client: TestClient) -> None:
    response = screening_client.post(RANKING_URL, json=make_api_profile().model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert (body["total_jobs"], body["passed_count"]) == (4, 2)
    assert body["rejected_by_rule"] == {"industry": 1, "status": 1}
    # 被规则剔除的 3、4 号不会进入技能评分；候选人有 Python/SQL，1 号全命中，分数更高
    assert [item["job_id"] for item in body["results"]] == [1, 2]
    scores = [item["overall_score"]["final_score"] for item in body["results"]]
    assert scores[0] > scores[1]
    assert body["results"][0]["overall_score"]["active_core_weight"] == 60.0
    assert (body["results"][0]["company"], body["results"][0]["title"]) == ("Alpha", "Backend Engineer")


def test_ranking_all_rejected_returns_empty_results(screening_client: TestClient) -> None:
    profile = make_api_profile(target_industries=["Cybersecurity"])

    response = screening_client.post(RANKING_URL, json=profile.model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert (body["total_jobs"], body["passed_count"], body["results"]) == (4, 0, [])


def test_ranking_rejects_body_without_resume(screening_client: TestClient) -> None:
    assert screening_client.post(RANKING_URL, json={"constraints": {}}).status_code == 422


def test_ranking_skill_score_equals_direct_skills_api_result(screening_client: TestClient) -> None:
    # 契约一致性：把 rules-screening 筛出的文档原样交给 POST /matches/skills，结果必须和 ranking 里的 skill_score 完全相同
    payload = make_api_profile().model_dump(mode="json")
    ranked = {
        item["job_id"]: item["skill_score"]
        for item in screening_client.post(RANKING_URL, json=payload).json()["results"]
    }
    screened_jobs = screening_client.post(SCREENING_URL, json=payload).json()["jobs"]
    assert set(ranked) == {job["job_id"] for job in screened_jobs}

    for job in screened_jobs:
        direct = screening_client.post(SKILLS_URL, json={"candidate": payload["resume"], "job": job})
        assert direct.status_code == 200
        assert ranked[job["job_id"]] == direct.json()
