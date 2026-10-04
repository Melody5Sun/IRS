"""target_jobs: jobs the user set as targets, with application progress.

目标岗位：用户在岗位推荐里点「设为目标岗位」后存一行，跟踪申请阶段和模拟面试是否完成。
单用户部署，岗位 id 直接当主键。简历改写这一步不在这里存，从 resume_rewrites 推出；
「提交申请」这一步 = stage 不是 not_applied，不另设字段。

Revision ID: 20261004_0014
Revises: 20261002_0013
Create Date: 2026-10-04
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20261004_0014"
down_revision: Union[str, None] = "20261002_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE target_jobs (
            job_id BIGINT PRIMARY KEY REFERENCES job_postings(id) ON DELETE CASCADE,
            -- 加入目标时排序接口给出的匹配度快照
            match_score REAL,
            stage TEXT NOT NULL DEFAULT 'not_applied' CHECK (stage IN (
                'not_applied', 'submitted', 'written_test', 'interview_1', 'interview_2',
                'interview_3', 'hr_interview', 'manager_interview', 'offer', 'rejected'
            )),
            -- 用户自填的进度说明，前端优先显示
            stage_note TEXT NOT NULL DEFAULT '',
            interview_done_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- 改写接口从此只对目标岗位开放：已有改写稿的岗位直接设为目标，改写稿仍可继续编辑
        INSERT INTO target_jobs (job_id) SELECT DISTINCT job_id FROM resume_rewrites;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE target_jobs;")
