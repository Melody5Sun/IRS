# IT CareerPilot Backend

FastAPI backend for the IT CareerPilot IRS project.

## What is included

- Health check endpoint
- Resume PDF parsing endpoint (`POST /api/v1/resumes/parse-pdf`, LLM-based)
- User profile and job-search constraints (`GET/PUT /api/v1/profile`, persisted for one local user)
- Job analysis endpoint with requirement extraction
- Job sync/list endpoints backed by PostgreSQL
- Recommendation endpoint with hard-constraint checks and explainable scoring
- MIND Tech Skills Ontology snapshot loaded at application startup
- Focused pytest tests for the initial API contract

## Project layout

```text
backend/
  app/
    api/v1/          # HTTP routes
    core/            # settings and shared config
    db/              # PostgreSQL runtime plus explicit SQLite test helpers
    ingestion/       # external job source clients and synchronization
    knowledge/       # MIND knowledge graph loader
    matching/        # scoring and constraint logic
    parsers/         # resume and job parsing helpers
    repositories/    # persistence access
    schemas/         # Pydantic request/response models
    services/        # application use cases
    main.py          # FastAPI app factory
  tests/             # API and service tests
  data/              # versioned ontology and embedding data
```

## Local setup

```bash
conda activate careerpilot-backend
cd SystemCode/backend
python -m pip install -r requirements.txt
```

## Run the API

```bash
uvicorn app.main:app --reload
```

Open the interactive API docs at:

```text
http://127.0.0.1:8000/docs
```

Use `POST /api/v1/jobs/sync` to fetch supported public job sources into the
configured runtime database. Use `GET /api/v1/jobs` to list active jobs and
`POST /api/v1/jobs/{job_id}/analyze-requirements` to create a structured JD.

Use `POST /api/v1/matches/skills` to calculate the implemented skill-score
components from a formatted resume and a structured JD. See
[`docs/skill-matching-score.md`](docs/skill-matching-score.md) for the formula.

Use `POST /api/v1/rules-screening` with a `UserProfile` body to run the
hard-constraint rule engine over all analysed jobs; it returns the jobs that
passed as `JobRequirementDocument`s plus per-rule rejection counts. Use
`POST /api/v1/ranking` with the same body to run the rule engine and then score
every passed job with `POST /api/v1/matches/skills`, sorted by `partial_score`.
See [`app/rule_engine/README.md`](app/rule_engine/README.md) for the rules.
The production runtime does not create or read a database file inside the repository.

## PostgreSQL migration

The formal runtime database is PostgreSQL 16 with pgvector. The repository
contains an Alembic baseline, a transactional SQLite migration tool, and a
separate verification tool. `DATABASE_URL` is required by the default API
repositories. Explicit temporary database paths are supported only by tests.
See [`docs/database-refactor.md`](docs/database-refactor.md) for the guarded
migration and archive procedure.

## Team database setup

Alembic creates the PostgreSQL schema, but it does not include the shared job
and interview-question data. To reproduce the complete team database, obtain
`careerpilot-postgresql-after-migration-20260929.dump` from the team's shared
storage. The expected SHA-256 is:

```text
54CEECBC4778AB23EF59CD79FCF3106FB1F57E12169E8141CDDF47E25FBAAEEF
```

### Recommended: Docker

Run these commands from the repository root:

```powershell
docker compose up -d postgres
docker compose ps
docker cp "<path-to-dump>\careerpilot-postgresql-after-migration-20260929.dump" `
  careerpilot-postgres:/tmp/careerpilot.dump
docker exec careerpilot-postgres pg_restore `
  -U careerpilot `
  -d careerpilot `
  --no-owner `
  /tmp/careerpilot.dump
```

The restore command is intended for the fresh, empty database created by
`docker compose up`. Do not restore the snapshot over a database that already
contains project data.

Configure the repository-root `.env` file without committing it:

```text
DATABASE_URL=postgresql+psycopg://careerpilot:careerpilot@127.0.0.1:5433/careerpilot
```

Verify the restored data:

```powershell
docker exec careerpilot-postgres psql -U careerpilot -d careerpilot `
  -c "SELECT COUNT(*) AS jobs FROM job_postings;"
docker exec careerpilot-postgres psql -U careerpilot -d careerpilot `
  -c "SELECT COUNT(*) AS questions FROM interview_questions;"
```

The current shared snapshot should return `134` jobs and `215` interview
questions. Then install the Python dependencies, start the API, and open the
Swagger page:

```powershell
cd SystemCode/backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

```text
http://127.0.0.1:8000/docs
```

### Native PostgreSQL

For a native installation, use PostgreSQL 16 with the `pgvector` extension,
create an empty `careerpilot` database, and restore the same dump with
`pg_restore --no-owner`. Native PostgreSQL normally uses port `5432`, so update
`DATABASE_URL` accordingly. Each teammate should use a local password and must
not commit their `.env` file.

## MIND knowledge graph

The backend includes a pinned MIND Tech Skills Ontology snapshot under
`data/mind_ontology`. The application validates and loads 3,333 skill nodes and
974 concept nodes during startup. Access the graph from application code with:

```python
from app.knowledge import get_mind_knowledge_graph

graph = get_mind_knowledge_graph()
react = graph.get_skill("react.js")
prerequisites = graph.related_skills("Next.js", "impliesKnowingSkills")
```

The graph is loaded and queryable but is not yet connected to recommendation
scoring.

## Run tests

```bash
pytest
```
