from fastapi.testclient import TestClient
import pytest

from app.rule_engine import engine as rule_engine
from app.schemas.profile import UserProfile
from app.services.profile_service import ProfileService
from app.services.ranking_service import ranking_sort_key, recommendation_level_rank
from job_db import make_api_profile, make_rows

RANKING_URL = "/api/ranking"


def test_recommendation_levels_match_frontend_thresholds() -> None:
    assert recommendation_level_rank(16) == 2
    assert recommendation_level_rank(15.99) == 1
    assert recommendation_level_rank(4) == 1
    assert recommendation_level_rank(3.99) == 0


def test_intent_reranks_only_within_the_same_recommendation_level() -> None:
    jobs = [
        (16.0, 0.0, 1),
        (15.0, 100.0, 2),
        (8.0, 40.0, 3),
        (4.0, 80.0, 4),
    ]

    ranked = sorted(jobs, key=lambda item: ranking_sort_key(*item))

    assert [job_id for _, _, job_id in ranked] == [1, 2, 4, 3]


def _rank(client: TestClient, service: ProfileService, profile: UserProfile):
    # ranking 不收请求体，读库里保存的画像：测试直接写进 Fake 画像仓库
    service.profile_repository.save(profile)
    return client.post(RANKING_URL)


def test_ranking_scores_only_screened_jobs_in_descending_order(
    screening_client: TestClient, profile_service: ProfileService
) -> None:
    response = _rank(screening_client, profile_service, make_api_profile())

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
        "professional_score": body["results"][0]["professional_score"],
        "intent_fit": body["results"][0]["intent_fit"],
        "final_score": scores[0],
    }


def test_ranking_all_rejected_returns_empty_results(
    screening_client: TestClient, profile_service: ProfileService
) -> None:
    profile = make_api_profile(target_industries=["Cybersecurity"])

    response = _rank(screening_client, profile_service, profile)

    assert response.status_code == 200
    body = response.json()
    assert (
        body["total_jobs"],
        body["passed_count"],
        body["returned_count"],
        body["results"],
    ) == (4, 0, 0, [])


def test_ranking_excludes_jobs_without_responsibilities(
    monkeypatch: pytest.MonkeyPatch,
    screening_client: TestClient,
    profile_service: ProfileService,
) -> None:
    jobs = (
        {
            "id": 1,
            "title": "Backend Engineer",
            "company": "Complete",
            "industry": "Gaming",
            "employment_type": "internship",
            "responsibilities": ["Build backend services"],
            "required_skills": ["python"],
        },
        {
            "id": 2,
            "title": "Title Only Engineer",
            "company": "Incomplete",
            "industry": "Gaming",
            "employment_type": "internship",
            "responsibilities": [],
            "required_skills": ["python"],
        },
    )
    monkeypatch.setattr(rule_engine, "load_job_rows", lambda: make_rows(*jobs))

    response = _rank(screening_client, profile_service, make_api_profile())

    assert response.status_code == 200
    body = response.json()
    assert (body["total_jobs"], body["passed_count"], body["returned_count"]) == (2, 1, 1)
    assert body["rejected_by_rule"] == {"insufficient_job_data": 1}
    assert [item["job_id"] for item in body["results"]] == [1]


def test_ranking_without_saved_profile_returns_409(screening_client: TestClient) -> None:
    # 还没有保存画像就不能进行下一步
    assert screening_client.post(RANKING_URL).status_code == 409


def test_ranking_reranks_after_profile_update(
    screening_client: TestClient, profile_service: ProfileService
) -> None:
    before = _rank(screening_client, profile_service, make_api_profile()).json()
    # 画像更新（目标行业改了）后再调用，结果按新画像重新计算
    after = _rank(screening_client, profile_service, make_api_profile(target_industries=["Cybersecurity"])).json()

    assert before["passed_count"] == 2
    assert after["passed_count"] == 0


def test_ranking_returns_only_top_30_with_stable_tie_order(
    monkeypatch: pytest.MonkeyPatch,
    screening_client: TestClient,
    profile_service: ProfileService,
) -> None:
    jobs = tuple(
        {
            "id": job_id,
            "title": f"Backend Engineer {job_id}",
            "company": f"Company {job_id}",
            "industry": "Gaming",
            "employment_type": "internship",
            "responsibilities": ["Build backend services"],
            "required_skills": ["python"],
        }
        for job_id in range(1, 36)
    )
    monkeypatch.setattr(rule_engine, "load_job_rows", lambda: make_rows(*jobs))

    response = _rank(screening_client, profile_service, make_api_profile())

    assert response.status_code == 200
    body = response.json()
    assert (body["passed_count"], body["returned_count"]) == (35, 30)
    assert [item["job_id"] for item in body["results"]] == list(range(1, 31))
    assert [item["rank"] for item in body["results"]] == list(range(1, 31))
