from datetime import datetime

from sqlalchemy import text

from app.db.postgres import get_postgres_engine
from app.schemas.target_job import ApplicationStage, TargetJobRecord

SELECT_TARGETS = """
    SELECT t.job_id, jp.title, c.name AS company, jp.location_text AS location, jp.source_url AS url,
           t.match_score, t.stage, t.stage_note, t.interview_done_at, t.created_at, t.updated_at
    FROM target_jobs t
    JOIN job_postings jp ON jp.id = t.job_id
    JOIN companies c ON c.id = jp.company_id
"""


class TargetJobRepository:
    """target_jobs 表：用户设为目标的岗位及申请进度，单用户部署，岗位 id 即主键。"""

    def list(self) -> list[TargetJobRecord]:
        # 岗位已没有截止日期，按加入目标的时间倒序
        with get_postgres_engine().connect() as connection:
            rows = connection.execute(text(SELECT_TARGETS + " ORDER BY t.created_at DESC")).mappings().all()
        return [TargetJobRecord.model_validate(dict(row)) for row in rows]

    def get(self, job_id: int) -> TargetJobRecord | None:
        with get_postgres_engine().connect() as connection:
            row = connection.execute(
                text(SELECT_TARGETS + " WHERE t.job_id = :job_id"), {"job_id": job_id}
            ).mappings().one_or_none()
        return TargetJobRecord.model_validate(dict(row)) if row else None

    def add(self, job_id: int, match_score: float | None) -> None:
        # 重复添加不报错，也不覆盖已有进度
        with get_postgres_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO target_jobs (job_id, match_score) VALUES (:job_id, :match_score)
                    ON CONFLICT (job_id) DO NOTHING
                    """
                ),
                {"job_id": job_id, "match_score": match_score},
            )

    def update(
        self, job_id: int, stage: ApplicationStage, stage_note: str, interview_done_at: datetime | None
    ) -> None:
        with get_postgres_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE target_jobs
                    SET stage = :stage, stage_note = :stage_note, interview_done_at = :interview_done_at,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = :job_id
                    """
                ),
                {"job_id": job_id, "stage": stage, "stage_note": stage_note, "interview_done_at": interview_done_at},
            )

    def delete(self, job_id: int) -> bool:
        """移出目标：同一事务里删掉该岗位所有简历版本的改写稿。返回该岗位原本是否是目标。"""
        with get_postgres_engine().begin() as connection:
            result = connection.execute(text("DELETE FROM target_jobs WHERE job_id = :job_id"), {"job_id": job_id})
            if result.rowcount == 0:
                return False
            connection.execute(text("DELETE FROM resume_rewrites WHERE job_id = :job_id"), {"job_id": job_id})
        return True

    def exists(self, job_id: int) -> bool:
        with get_postgres_engine().connect() as connection:
            return connection.execute(
                text("SELECT EXISTS (SELECT 1 FROM target_jobs WHERE job_id = :job_id)"), {"job_id": job_id}
            ).scalar_one()
