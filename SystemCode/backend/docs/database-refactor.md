# PostgreSQL database refactor

The PostgreSQL schema is normalized for job descriptions, interview questions,
skills, roles, resumes, and matching results. `DATABASE_URL` is required for the
API runtime; SQLite is not an application fallback.

## Safety rules

- Keep the source SQLite archive outside the repository.
- Take a SQLite online backup before every migration attempt.
- Migrate only into an empty PostgreSQL schema.
- Run the migration in one transaction.
- Do not configure `DATABASE_URL` for the API until verification reports
  `"passed": true`.
- Keep `migration_legacy_rows`; it stores every source row and its SHA-256 hash.

Verify an online SQLite backup by content rather than by file hash because
SQLite may reorganize pages while copying:

```bash
python -m scripts.verify_sqlite_backup \
  --source path/to/source.db \
  --backup path/to/verified-archive.db
```

## Local PostgreSQL

The repository includes `docker-compose.yml` using PostgreSQL 16 with pgvector.
PostgreSQL 16 with the compiled `pgvector` extension can also be installed
natively; use port `5432` for the default native installation.

```bash
docker compose up -d postgres
```

The development connection URL is:

```text
postgresql+psycopg://careerpilot:careerpilot@localhost:5433/careerpilot
```

## Create and migrate

Run commands from `SystemCode/backend` in the `careerpilot-backend` environment.

```bash
python -m alembic upgrade head
python -m scripts.migrate_sqlite_to_postgres \
  --source path/to/verified-archive.db \
  --target-url postgresql+psycopg://careerpilot:careerpilot@localhost:5433/careerpilot
```

The migration refuses to write when the target already contains jobs, questions,
or archived source rows.

## Verify

```bash
python -m scripts.verify_postgres_migration \
  --source path/to/verified-archive.db \
  --target-url postgresql+psycopg://careerpilot:careerpilot@localhost:5433/careerpilot
```

Verification checks:

- SQLite integrity
- entity and child-row counts
- every archived source row and SHA-256
- missing or extra archived rows
- orphaned job versions, analyses, and question sources

Only after all checks pass should the URL be added to `.env`:

```text
DATABASE_URL=postgresql+psycopg://careerpilot:careerpilot@localhost:5433/careerpilot
```

## Recovery

Keep the verified SQLite archive and PostgreSQL dump outside the repository.
Recovery uses `pg_restore` from the PostgreSQL dump or a new migration into an
empty database; removing `DATABASE_URL` is not a runtime fallback.
