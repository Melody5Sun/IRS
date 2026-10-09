"""resume_rewrites.session: persist the rewrite comparison and review progress.

改写对比（每块原文/改写稿/理由、删除建议）连同用户的审阅进度存进 session 列：生成后立即写入，
下次进页面还能看到对比并继续修改，不用再花一次大模型调用。
resume 改为可空：resume 为空 = 只生成了草稿、还没保存终稿。

Revision ID: 20261009_0015
Revises: 20261004_0014
Create Date: 2026-10-09
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20261009_0015"
down_revision: Union[str, None] = "20261004_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE resume_rewrites ADD COLUMN session JSONB;
        ALTER TABLE resume_rewrites ALTER COLUMN resume DROP NOT NULL;
        """
    )


def downgrade() -> None:
    # 只有草稿、没有终稿的行无法放回 NOT NULL 的 resume 列
    op.execute(
        """
        DELETE FROM resume_rewrites WHERE resume IS NULL;
        ALTER TABLE resume_rewrites ALTER COLUMN resume SET NOT NULL;
        ALTER TABLE resume_rewrites DROP COLUMN session;
        """
    )
