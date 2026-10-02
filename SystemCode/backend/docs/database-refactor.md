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
- orphaned job analyses and question sources

Only after all checks pass should the URL be added to `.env`:

```text
DATABASE_URL=postgresql+psycopg://careerpilot:careerpilot@localhost:5433/careerpilot
```

## JD semantic data

Apply the latest Alembic migration and populate reusable JD semantics after a
legacy restore or import:

```bash
python -m alembic upgrade head
python -m scripts.backfill_job_semantics
```

`job_responsibilities.embedding` stores the 384-dimensional vector for each
responsibility together with its model name and content hash.
`job_roles` stores only the Top-3 standard-role results for each current JD,
including rank, similarity, model, algorithm, input hash, and taxonomy
hash. The temporary JD classification vector and standard-role vectors are not
persisted. Resume evidence vectors remain request-scoped, while interview
questions continue to use their normalized role labels.

Migration `20260930_0004` stores each company's single industry directly in
`companies.industry_id` and stores the current JD content directly in
`job_postings`. Analyses, responsibilities, skill requirements, and role
matches now reference `job_postings.id` as `job_id`. Historical JD versions are
not retained. `job_major_requirements`, `job_keywords`, and
`job_source_evidence` were removed because the same values remain available in
`job_analyses.raw_analysis`.

The following empty or superseded tables were removed in migration
`20260930_0003`: `ingestion_runs`, the old confidence-only `job_roles`,
`question_embeddings`, `match_runs`, and `job_match_results`. Migration
`20260930_0004` later reuses the `job_roles` name for the active Top-3 semantic
mapping described above. The other tables can be recreated by downgrading if a
future feature genuinely needs them.

Migration `20260930_0005` removes the empty `skill_aliases` and
`skill_relations` tables. Runtime alias and graph traversal use the versioned
MIND ontology under `data/mind_ontology`; the PostgreSQL `skills` table remains
the relational dictionary referenced by JD and resume skill associations.

Migration `20260930_0006` removes `question_skills` and `question_keywords`.
Interview questions are recommended through the JD Top-3 role mappings in
`job_roles` and the many-to-many role labels in `question_roles`; skill and
keyword tags are therefore not part of the persisted recommendation path.

Migration `20260930_0007` restores the original single-user persistence owned
by the profile/resume team: `user_profile(id, profile_json, updated_at)` and
`resume_uploads(id, filename, resume_json, uploaded_at)`. The speculative
normalized user, target, resume-evidence, and resume-skill tables were empty and
were removed.

Migration `20261002_0009` refactors those two tables in place (same names):
`resume_uploads.resume_json` becomes `JSONB` and `uploaded_at` becomes
`TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP`; `user_profile.profile_json` is split into
`resume JSONB` (every `ResumeDocument` field) and `constraints JSONB` (job-search
constraints), and `updated_at` becomes `TIMESTAMPTZ`. Existing rows are converted
with `USING`, and the downgrade merges the two columns back. The API still returns
the complete `{resume, constraints}` profile. SQLite is no longer used for these
tables or the rule engine; tests inject fake repositories / job rows instead.

## Recovery

Keep the verified SQLite archive and PostgreSQL dump outside the repository.
Recovery uses `pg_restore` from the PostgreSQL dump or a new migration into an
empty database; removing `DATABASE_URL` is not a runtime fallback.
