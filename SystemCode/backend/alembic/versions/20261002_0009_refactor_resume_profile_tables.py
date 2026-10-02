"""Refactor resume_uploads and user_profile in place: TEXT JSON -> JSONB, TEXT time -> TIMESTAMPTZ.

Revision ID: 20261002_0009
Revises: 20261002_0008
Create Date: 2026-10-02
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20261002_0009"
down_revision: Union[str, None] = "20261002_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        -- 每次上传解析出的简历（ParsedResume，含 about），供用户挑选历史版本套用
        ALTER TABLE resume_uploads
            ALTER COLUMN resume_json TYPE JSONB USING resume_json::jsonb,
            ALTER COLUMN uploaded_at TYPE TIMESTAMPTZ USING uploaded_at::timestamptz,
            ALTER COLUMN uploaded_at SET DEFAULT CURRENT_TIMESTAMP;

        -- 单用户画像：profile_json 拆成 resume（ResumeDocument 全部字段）和 constraints（求职约束）两列
        ALTER TABLE user_profile
            ADD COLUMN resume JSONB,
            ADD COLUMN constraints JSONB;
        UPDATE user_profile SET
            resume = profile_json::jsonb -> 'resume',
            constraints = profile_json::jsonb -> 'constraints';
        ALTER TABLE user_profile
            DROP COLUMN profile_json,
            ALTER COLUMN resume SET NOT NULL,
            ALTER COLUMN constraints SET NOT NULL,
            ALTER COLUMN id SET DEFAULT 1,
            ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at::timestamptz,
            ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE user_profile ADD COLUMN profile_json TEXT;
        UPDATE user_profile SET profile_json =
            jsonb_build_object('resume', resume, 'constraints', constraints)::text;
        ALTER TABLE user_profile
            DROP COLUMN resume,
            DROP COLUMN constraints,
            ALTER COLUMN profile_json SET NOT NULL,
            ALTER COLUMN id DROP DEFAULT,
            ALTER COLUMN updated_at DROP DEFAULT,
            ALTER COLUMN updated_at TYPE TEXT USING updated_at::text;

        ALTER TABLE resume_uploads
            ALTER COLUMN resume_json TYPE TEXT USING resume_json::text,
            ALTER COLUMN uploaded_at DROP DEFAULT,
            ALTER COLUMN uploaded_at TYPE TEXT USING uploaded_at::text;
        """
    )
