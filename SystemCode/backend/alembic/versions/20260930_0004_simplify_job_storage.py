"""Simplify company industry and current-job storage.

Revision ID: 20260930_0004
Revises: 20260930_0003
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260930_0004"
down_revision: Union[str, None] = "20260930_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM job_versions GROUP BY job_id HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot remove job_versions: at least one job has multiple versions';
            END IF;
        END $$;

        ALTER TABLE companies
            ADD COLUMN industry_id BIGINT REFERENCES industries(id) ON DELETE RESTRICT;
        UPDATE companies c
        SET industry_id = ci.industry_id
        FROM company_industries ci
        WHERE ci.company_id = c.id;
        CREATE INDEX ix_companies_industry ON companies(industry_id);
        DROP TABLE company_industries;

        ALTER TABLE job_postings
            ADD COLUMN description TEXT NOT NULL DEFAULT '',
            ADD COLUMN content_hash TEXT,
            ADD COLUMN raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            ADD COLUMN collected_at TIMESTAMPTZ;
        UPDATE job_postings jp
        SET description = jv.description,
            content_hash = jv.content_hash,
            raw_payload = jv.raw_payload,
            collected_at = jv.collected_at
        FROM job_versions jv
        WHERE jv.job_id = jp.id;
        ALTER TABLE job_postings
            ALTER COLUMN content_hash SET NOT NULL,
            ALTER COLUMN collected_at SET NOT NULL;
        CREATE INDEX ix_job_postings_description_fts
            ON job_postings USING GIN (to_tsvector('english', description));

        ALTER TABLE job_responsibilities
            DROP CONSTRAINT job_responsibilities_job_version_id_fkey;
        ALTER TABLE job_skill_requirements
            DROP CONSTRAINT job_skill_requirements_job_version_id_fkey;
        ALTER TABLE job_major_requirements
            DROP CONSTRAINT job_major_requirements_job_version_id_fkey;
        ALTER TABLE job_keywords
            DROP CONSTRAINT job_keywords_job_version_id_fkey;
        ALTER TABLE job_source_evidence
            DROP CONSTRAINT job_source_evidence_job_version_id_fkey;
        ALTER TABLE job_analyses
            DROP CONSTRAINT job_analyses_job_version_id_fkey;
        ALTER TABLE job_version_roles
            DROP CONSTRAINT job_version_roles_job_version_id_fkey;

        UPDATE job_responsibilities child
        SET job_version_id = version.job_id
        FROM job_versions version
        WHERE child.job_version_id = version.id;
        UPDATE job_skill_requirements child
        SET job_version_id = version.job_id
        FROM job_versions version
        WHERE child.job_version_id = version.id;
        UPDATE job_analyses child
        SET job_version_id = version.job_id
        FROM job_versions version
        WHERE child.job_version_id = version.id;
        UPDATE job_version_roles child
        SET job_version_id = version.job_id
        FROM job_versions version
        WHERE child.job_version_id = version.id;

        DROP TABLE job_major_requirements;
        DROP TABLE job_keywords;
        DROP TABLE job_source_evidence;

        ALTER TABLE job_analyses RENAME COLUMN job_version_id TO job_id;
        ALTER TABLE job_responsibilities RENAME COLUMN job_version_id TO job_id;
        ALTER TABLE job_skill_requirements RENAME COLUMN job_version_id TO job_id;
        ALTER TABLE job_version_roles RENAME COLUMN job_version_id TO job_id;
        ALTER TABLE job_version_roles RENAME TO job_roles;

        ALTER TABLE job_analyses
            ADD CONSTRAINT job_analyses_job_id_fkey
            FOREIGN KEY (job_id) REFERENCES job_postings(id) ON DELETE CASCADE;
        ALTER TABLE job_responsibilities
            ADD CONSTRAINT job_responsibilities_job_id_fkey
            FOREIGN KEY (job_id) REFERENCES job_analyses(job_id) ON DELETE CASCADE;
        ALTER TABLE job_skill_requirements
            ADD CONSTRAINT job_skill_requirements_job_id_fkey
            FOREIGN KEY (job_id) REFERENCES job_analyses(job_id) ON DELETE CASCADE;
        ALTER TABLE job_roles
            ADD CONSTRAINT job_roles_job_id_fkey
            FOREIGN KEY (job_id) REFERENCES job_analyses(job_id) ON DELETE CASCADE;

        ALTER INDEX ix_job_version_roles_role RENAME TO ix_job_roles_role;
        ALTER INDEX ix_job_version_roles_lookup RENAME TO ix_job_roles_lookup;

        DROP TABLE job_versions;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE company_industries (
            company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
            industry_id BIGINT NOT NULL REFERENCES industries(id) ON DELETE RESTRICT,
            PRIMARY KEY (company_id, industry_id)
        );
        INSERT INTO company_industries (company_id, industry_id)
        SELECT id, industry_id FROM companies WHERE industry_id IS NOT NULL;
        CREATE INDEX ix_company_industries_industry
            ON company_industries(industry_id, company_id);

        CREATE TABLE job_versions (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            job_id BIGINT NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
            content_hash TEXT NOT NULL,
            description TEXT NOT NULL,
            raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            collected_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (job_id, content_hash)
        );
        INSERT INTO job_versions (
            id, job_id, content_hash, description, raw_payload, collected_at, created_at
        )
        SELECT id, id, content_hash, description, raw_payload, collected_at, created_at
        FROM job_postings;
        SELECT setval(
            pg_get_serial_sequence('job_versions', 'id'),
            COALESCE((SELECT MAX(id) FROM job_versions), 1),
            EXISTS (SELECT 1 FROM job_versions)
        );
        CREATE INDEX ix_job_versions_job_collected
            ON job_versions(job_id, collected_at DESC);
        CREATE INDEX ix_job_versions_description_fts
            ON job_versions USING GIN (to_tsvector('english', description));

        ALTER TABLE job_responsibilities DROP CONSTRAINT job_responsibilities_job_id_fkey;
        ALTER TABLE job_skill_requirements DROP CONSTRAINT job_skill_requirements_job_id_fkey;
        ALTER TABLE job_roles DROP CONSTRAINT job_roles_job_id_fkey;
        ALTER TABLE job_analyses DROP CONSTRAINT job_analyses_job_id_fkey;

        ALTER TABLE job_analyses RENAME COLUMN job_id TO job_version_id;
        ALTER TABLE job_responsibilities RENAME COLUMN job_id TO job_version_id;
        ALTER TABLE job_skill_requirements RENAME COLUMN job_id TO job_version_id;
        ALTER TABLE job_roles RENAME COLUMN job_id TO job_version_id;
        ALTER TABLE job_roles RENAME TO job_version_roles;

        ALTER TABLE job_analyses
            ADD CONSTRAINT job_analyses_job_version_id_fkey
            FOREIGN KEY (job_version_id) REFERENCES job_versions(id) ON DELETE CASCADE;
        ALTER TABLE job_responsibilities
            ADD CONSTRAINT job_responsibilities_job_version_id_fkey
            FOREIGN KEY (job_version_id)
            REFERENCES job_analyses(job_version_id) ON DELETE CASCADE;
        ALTER TABLE job_skill_requirements
            ADD CONSTRAINT job_skill_requirements_job_version_id_fkey
            FOREIGN KEY (job_version_id)
            REFERENCES job_analyses(job_version_id) ON DELETE CASCADE;
        ALTER TABLE job_version_roles
            ADD CONSTRAINT job_version_roles_job_version_id_fkey
            FOREIGN KEY (job_version_id) REFERENCES job_versions(id) ON DELETE CASCADE;

        ALTER INDEX ix_job_roles_role RENAME TO ix_job_version_roles_role;
        ALTER INDEX ix_job_roles_lookup RENAME TO ix_job_version_roles_lookup;

        CREATE TABLE job_major_requirements (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            job_version_id BIGINT NOT NULL
                REFERENCES job_analyses(job_version_id) ON DELETE CASCADE,
            sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
            major_text TEXT NOT NULL,
            UNIQUE (job_version_id, sequence_no)
        );
        INSERT INTO job_major_requirements (job_version_id, sequence_no, major_text)
        SELECT ja.job_version_id, item.ordinality - 1, item.value
        FROM job_analyses ja
        CROSS JOIN LATERAL jsonb_array_elements_text(
            COALESCE(ja.raw_analysis->'major_required', '[]'::jsonb)
        ) WITH ORDINALITY AS item(value, ordinality);

        CREATE TABLE job_keywords (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            job_version_id BIGINT NOT NULL
                REFERENCES job_analyses(job_version_id) ON DELETE CASCADE,
            sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
            keyword_text TEXT NOT NULL,
            UNIQUE (job_version_id, sequence_no)
        );
        INSERT INTO job_keywords (job_version_id, sequence_no, keyword_text)
        SELECT ja.job_version_id, item.ordinality - 1, item.value
        FROM job_analyses ja
        CROSS JOIN LATERAL jsonb_array_elements_text(
            COALESCE(ja.raw_analysis->'keywords', '[]'::jsonb)
        ) WITH ORDINALITY AS item(value, ordinality);

        CREATE TABLE job_source_evidence (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            job_version_id BIGINT NOT NULL
                REFERENCES job_analyses(job_version_id) ON DELETE CASCADE,
            sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
            evidence_text TEXT NOT NULL,
            UNIQUE (job_version_id, sequence_no)
        );
        INSERT INTO job_source_evidence (job_version_id, sequence_no, evidence_text)
        SELECT ja.job_version_id, item.ordinality - 1, item.value
        FROM job_analyses ja
        CROSS JOIN LATERAL jsonb_array_elements_text(
            COALESCE(ja.raw_analysis->'source_evidence', '[]'::jsonb)
        ) WITH ORDINALITY AS item(value, ordinality);

        DROP INDEX ix_job_postings_description_fts;
        ALTER TABLE job_postings
            DROP COLUMN collected_at,
            DROP COLUMN raw_payload,
            DROP COLUMN content_hash,
            DROP COLUMN description;
        DROP INDEX ix_companies_industry;
        ALTER TABLE companies DROP COLUMN industry_id;
        """
    )
