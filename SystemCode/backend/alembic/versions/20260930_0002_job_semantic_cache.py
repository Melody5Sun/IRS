"""Persist JD responsibility vectors and standard-role Top-K results.

Revision ID: 20260930_0002
Revises: 20260929_0001
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260930_0002"
down_revision: Union[str, None] = "20260929_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE job_responsibilities
            ADD COLUMN embedding_content_hash CHAR(64),
            ADD COLUMN embedded_at TIMESTAMPTZ;

        CREATE TABLE job_version_roles (
            job_version_id BIGINT NOT NULL
                REFERENCES job_versions(id) ON DELETE CASCADE,
            role_id BIGINT NOT NULL
                REFERENCES roles(id) ON DELETE RESTRICT,
            rank SMALLINT NOT NULL CHECK (rank > 0),
            similarity NUMERIC(7,6) NOT NULL
                CHECK (similarity >= -1 AND similarity <= 1),
            model_name TEXT NOT NULL,
            algorithm_version TEXT NOT NULL,
            input_hash CHAR(64) NOT NULL,
            taxonomy_hash CHAR(64) NOT NULL,
            matched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (
                job_version_id, role_id, model_name, algorithm_version
            ),
            UNIQUE (
                job_version_id, model_name, algorithm_version, rank
            )
        );
        CREATE INDEX ix_job_version_roles_role
            ON job_version_roles(role_id, job_version_id);
        CREATE INDEX ix_job_version_roles_lookup
            ON job_version_roles(
                job_version_id, model_name, algorithm_version, rank
            );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE job_version_roles;
        ALTER TABLE job_responsibilities
            DROP COLUMN embedded_at,
            DROP COLUMN embedding_content_hash;
        """
    )
