"""user_profile.resume_upload_id: profile must come from an uploaded resume.

画像必须来自一份上传的简历：user_profile 新增 resume_upload_id（NOT NULL，外键指向 resume_uploads），
保存画像时补全后的简历会回写到这一条上传记录。
已有画像没有来源记录，就把它当前的 resume 插入 resume_uploads 作为一条新记录再关联，画像数据不丢。

Revision ID: 20261002_0012
Revises: 20261002_0011
Create Date: 2026-10-02
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20261002_0012"
down_revision: Union[str, None] = "20261002_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE user_profile ADD COLUMN resume_upload_id INTEGER;

        -- 单用户最多一行画像：把它的简历存成一条上传记录，再回填 id
        WITH inserted AS (
            INSERT INTO resume_uploads (filename, resume_json)
            SELECT '(迁移前的画像)', resume FROM user_profile
            RETURNING id
        )
        UPDATE user_profile SET resume_upload_id = (SELECT id FROM inserted);

        ALTER TABLE user_profile
            ALTER COLUMN resume_upload_id SET NOT NULL,
            ADD CONSTRAINT fk_user_profile_resume_upload
                FOREIGN KEY (resume_upload_id) REFERENCES resume_uploads(id);
        """
    )


def downgrade() -> None:
    # 迁移时插入的那条上传记录保留，不影响旧版本使用
    op.execute(
        """
        ALTER TABLE user_profile
            DROP CONSTRAINT fk_user_profile_resume_upload,
            DROP COLUMN resume_upload_id;
        """
    )
