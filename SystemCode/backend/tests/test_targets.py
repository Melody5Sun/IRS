from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from test_resume_rewriter import FakeJobRepository, FakeRewriteRepository, _resume, _save_profile

from app.api.routes import targets as targets_route
from app.main import app
from app.schemas.target_job import ApplicationStage, TargetJobRecord


class FakeTargetJobRepository:
    """代替 target_jobs 表；删除时连带删改写稿的事务在 SQL 里，这里测不到。"""

    def __init__(self) -> None:
        self.rows: dict[int, TargetJobRecord] = {}

    def list(self) -> list[TargetJobRecord]:
        return sorted(self.rows.values(), key=lambda row: row.created_at, reverse=True)

    def get(self, job_id: int) -> TargetJobRecord | None:
        return self.rows.get(job_id)

    def add(self, job_id: int, match_score: float | None) -> None:
        now = datetime.now(timezone.utc)
        self.rows.setdefault(job_id, TargetJobRecord(
            job_id=job_id, title=f"Job {job_id}", company="Acme", url=f"https://example.com/{job_id}",
            match_score=match_score, stage="not_applied", stage_note="", created_at=now, updated_at=now,
        ))

    def update(self, job_id: int, stage: ApplicationStage, stage_note: str, interview_done_at: datetime | None) -> None:
        self.rows[job_id] = self.rows[job_id].model_copy(
            update={"stage": stage, "stage_note": stage_note, "interview_done_at": interview_done_at}
        )

    def delete(self, job_id: int) -> bool:
        return self.rows.pop(job_id, None) is not None


@pytest.fixture
def rewrites(monkeypatch: pytest.MonkeyPatch) -> FakeRewriteRepository:
    repository = FakeRewriteRepository()
    monkeypatch.setattr(targets_route, "rewrite_repository", repository)
    monkeypatch.setattr(targets_route, "target_repository", FakeTargetJobRepository())
    monkeypatch.setattr(targets_route, "job_repository", FakeJobRepository())
    return repository


def test_target_lifecycle(rewrites: FakeRewriteRepository, profile_service) -> None:
    client = TestClient(app)
    assert client.post("/api/targets", json={"job_id": 999}).status_code == 404

    created = client.post("/api/targets", json={"job_id": 7, "match_score": 82.5})
    assert created.status_code == 201
    assert created.json()["stage"] == "not_applied" and created.json()["rewrite_status"] == "none"
    # 重复添加不报错，也不覆盖原来的匹配度快照
    assert client.post("/api/targets", json={"job_id": 7, "match_score": 10}).json()["match_score"] == 82.5

    # 未提交申请时不能写进度备注
    assert client.patch("/api/targets/7", json={"stage_note": "三面已过"}).status_code == 409
    assert client.patch("/api/targets/999", json={"stage": "submitted"}).status_code == 404
    assert client.patch("/api/targets/7", json={"stage": "unknown"}).status_code == 422

    updated = client.patch("/api/targets/7", json={"stage": "interview_1", "stage_note": " 等 HR 回复 ", "interview_done": True})
    body = updated.json()
    assert body["stage"] == "interview_1" and body["stage_note"] == "等 HR 回复" and body["interview_done_at"]
    # 只传一个字段时，其他字段不变
    assert client.patch("/api/targets/7", json={"stage": "offer"}).json()["stage_note"] == "等 HR 回复"
    # 撤回到未申请：备注一并清空
    reverted = client.patch("/api/targets/7", json={"stage": "not_applied", "interview_done": False}).json()
    assert reverted["stage_note"] == "" and reverted["interview_done_at"] is None

    assert client.delete("/api/targets/7").status_code == 204
    assert client.delete("/api/targets/7").status_code == 404
    assert client.get("/api/targets").json() == []


def test_target_rewrite_status_follows_current_profile(rewrites: FakeRewriteRepository, profile_service) -> None:
    client = TestClient(app)
    client.post("/api/targets", json={"job_id": 7})
    resume = _resume()
    _save_profile(profile_service, 1, resume)
    assert client.get("/api/targets").json()[0]["rewrite_status"] == "none"

    rewrites.save(1, 7, resume.model_copy(update={"name": "Rewritten"}), "hash-at-save")
    # 保存时的哈希和当前画像不一致 → 过时
    assert client.get("/api/targets").json()[0]["rewrite_status"] == "stale"

    from app.services.profile_service import resume_hash

    rewrites.save(1, 7, resume, resume_hash(resume))
    target = client.get("/api/targets").json()[0]
    assert target["rewrite_status"] == "saved" and target["rewrite_updated_at"]

    # 画像换成另一份简历后，读不到旧简历的改写稿
    _save_profile(profile_service, 2, resume)
    assert client.get("/api/targets").json()[0]["rewrite_status"] == "none"
