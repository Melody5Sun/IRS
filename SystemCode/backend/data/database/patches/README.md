# Targeted database patches

This directory contains reviewable, data-only PostgreSQL patches. It is used
when a small set of production-like records must be shared without replacing
the complete team database snapshot.

## 20261013_repair_14_jds.sql

Repairs the following SmartRecruiters job records:

`92, 94, 97, 98, 99, 107, 270, 274, 275, 278, 280, 282, 283, 344`

The patch synchronizes only the affected rows in:

- `companies`
- `skills`
- `job_postings`
- `job_analyses`
- `job_responsibilities`, including stored embeddings
- `job_skill_requirements`
- `job_roles`

It does not modify the database schema or unrelated jobs, users, resumes, or
interview questions. The script runs in one transaction and validates the
expected row counts before committing. It can be run repeatedly.

From the repository root, after applying the current Alembic migrations:

```powershell
psql "$env:DATABASE_URL" -f SystemCode/backend/data/database/patches/20261013_repair_14_jds.sql
```

If `DATABASE_URL` uses SQLAlchemy's `postgresql+psycopg://` prefix, replace it
with `postgresql://` when invoking `psql`.
