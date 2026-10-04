from datetime import datetime, timezone

from app.ingestion.job_sync_service import JobSyncService
from app.ingestion.source_registry import DEFAULT_SOURCES, JobSource
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobPosting


def make_job(external_id: str = "job-1") -> JobPosting:
    now = datetime.now(timezone.utc)
    return JobPosting(
        source="test_source",
        company="TestCo",
        external_id=external_id,
        title="Software Engineer Intern",
        location="Singapore",
        description="Build backend services with Python and SQL.",
        url=f"https://example.com/jobs/{external_id}",
        employment_type="Intern",
        collected_at=now,
        last_seen_at=now,
        content_hash=f"hash-{external_id}",
        raw_json={"id": external_id},
    )


def test_job_repository_upserts_and_lists_active_jobs(tmp_path) -> None:
    repository = JobRepository(tmp_path / "careerpilot.db")

    changed_count = repository.upsert_many([make_job()])
    jobs = repository.list_jobs()

    assert changed_count == 1
    assert len(jobs) == 1
    assert jobs[0].title == "Software Engineer Intern"


def test_job_sync_service_skips_disabled_sources(tmp_path) -> None:
    repository = JobRepository(tmp_path / "careerpilot.db")
    service = JobSyncService(
        repository=repository,
        sources=[
            JobSource(
                name="disabled_google",
                company="Google",
                provider="manual",
                identifier="https://example.com",
                enabled=False,
            )
        ],
    )

    response = service.sync()

    assert response.fetched_count == 0
    assert response.sources[0].status == "skipped"


def test_default_sources_enable_stable_public_apis() -> None:
    enabled_sources = {source.name: source for source in DEFAULT_SOURCES if source.enabled}

    assert enabled_sources["shopback_lever"].provider == "lever"
    assert enabled_sources["straitsx_greenhouse"].provider == "greenhouse"
    assert enabled_sources["drw_greenhouse"].provider == "greenhouse"
    assert enabled_sources["grasshopper_greenhouse"].provider == "greenhouse"
    assert enabled_sources["csit_lever"].provider == "lever"
    assert enabled_sources["tencent_careers"].provider == "tencent"
    assert enabled_sources["stripe_greenhouse"].provider == "greenhouse"
    assert enabled_sources["datadog_greenhouse"].provider == "greenhouse"
    assert enabled_sources["jane_street_greenhouse"].provider == "greenhouse"
    assert enabled_sources["jump_trading_greenhouse"].provider == "greenhouse"
    assert enabled_sources["worldquant_greenhouse"].provider == "greenhouse"
    assert enabled_sources["tower_research_greenhouse"].provider == "greenhouse"
    assert enabled_sources["point72_greenhouse"].provider == "greenhouse"
    assert enabled_sources["applovin_greenhouse"].provider == "greenhouse"
    assert enabled_sources["squarepoint_greenhouse"].provider == "greenhouse"
    assert enabled_sources["virtu_greenhouse"].provider == "greenhouse"
    assert enabled_sources["visier_greenhouse"].provider == "greenhouse"
    assert enabled_sources["amperesand_greenhouse"].provider == "greenhouse"
    assert enabled_sources["caladan_greenhouse"].provider == "greenhouse"
    assert enabled_sources["bosch_smartrecruiters"].provider == "smartrecruiters"
    assert enabled_sources["globalfoundries_workday"].provider == "workday"
    assert enabled_sources["ncs_smartrecruiters"].provider == "smartrecruiters"
    assert "tiktok_bytedance_campus" not in enabled_sources
    assert "alibaba_lazada_recruit" not in enabled_sources
    assert "huawei_careers" not in enabled_sources


def test_library_status_route_reports_latest_sync_and_active_count(tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.api.routes import jobs as jobs_route
    from app.main import app

    repository = JobRepository(tmp_path / "careerpilot.db")
    monkeypatch.setattr(jobs_route, "job_repository", repository)
    client = TestClient(app)
    assert client.get("/api/jobs/library-status").json() == {"synced_at": None, "active_job_count": 0}

    latest = datetime(2026, 10, 4, 7, 40, tzinfo=timezone.utc)
    old, recent, inactive = make_job("a"), make_job("b"), make_job("c")
    old.last_seen_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    recent.last_seen_at = latest
    inactive.status = "inactive"
    inactive.last_seen_at = datetime(2026, 9, 1, tzinfo=timezone.utc)
    repository.upsert_many([old, recent, inactive])

    status = client.get("/api/jobs/library-status").json()
    assert status["active_job_count"] == 2
    assert datetime.fromisoformat(status["synced_at"].replace("Z", "+00:00")) == latest
