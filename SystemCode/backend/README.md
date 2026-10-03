# IT CareerPilot Backend

FastAPI backend for the IT CareerPilot IRS project.

## What is included

- Health check endpoint
- Resume PDF parsing endpoint (`POST /api/resumes/parse-pdf`, LLM-based)
- User profile and job-search constraints (`GET/PUT /api/profile`, persisted for one local user)
- Job analysis endpoint with requirement extraction
- Job sync/list endpoints backed by PostgreSQL
- Recommendation endpoint with hard-constraint checks and explainable scoring
- MIND Tech Skills Ontology snapshot loaded at application startup
- Focused pytest tests for the initial API contract

## Project layout

```text
backend/
  app/
    api/             # HTTP routes
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

Use `POST /api/jobs/sync` to fetch supported public job sources into the
configured runtime database. Use `GET /api/jobs` to list active jobs and
`POST /api/jobs/{job_id}/analyze-requirements` to create a structured JD.

Use `POST /api/matches/skills` to calculate the implemented skill-score
components from a formatted resume and a structured JD. See
[`docs/skill-matching-score.md`](docs/skill-matching-score.md) for the formula.

Use `POST /api/jobs/{job_id}/interview-questions/sample` to sample a
repeatable interview set from the stored JD Top-3 role matches. The default
response contains 10 questions, including 3 basic programming questions, with
a 4 easy / 4 medium / 2 hard distribution. The request accepts an optional
`seed`, custom count and difficulty mix, and question IDs to exclude. Both
Chinese and English questions and answers are returned for frontend reveal and
hide interactions.

Use `POST /api/jobs/{job_id}/interview-questions/{question_id}/transcription`
with an `audio` multipart upload to transcribe one recorded English interview
answer. The backend sends the audio to Cloudflare Workers AI and does not store
the recording or transcript. Configure these values in the repository-root
`.env` file:

```text
CLOUDFLARE_ACCOUNT_ID=...
CLOUDFLARE_API_TOKEN=...
CLOUDFLARE_STT_MODEL=@cf/openai/whisper-large-v3-turbo
```

The endpoint accepts WebM, WAV, MP3, M4A/MP4, and OGG files up to 25 MB. The
Cloudflare token remains on the backend and must not be exposed to the frontend.

Use `POST /api/rules-screening` with a `UserProfile` body to run the
hard-constraint rule engine over all analysed jobs; it returns the jobs that
passed as `JobRequirementDocument`s plus per-rule rejection counts. Use
`POST /api/ranking` (no request body) to run the rule engine on the **saved**
profile and then score every passed job with the complete matching formula; it
returns 409 until a profile has been saved, and re-ranks on every call, so a
profile update is reflected immediately. Its lightweight response
returns the top 30 jobs with rank, basic job metadata, and final score; detailed
matching evidence for one selected job is returned by
`POST /api/jobs/{job_id}/match-detail` using a `UserProfile` body.

Profile flow: `POST /api/resumes/parse-pdf` only stores the parsed resume in
`resume_uploads` and returns the whole record (`id` + `resume`);
`GET /api/resumes/history/{id}` returns any earlier upload the same way.
Neither touches the profile. `PUT /api/profile` is the only way to create the
profile: every required field must be filled (422 otherwise), `resume_upload_id`
must point to an existing upload (404 otherwise), and the completed resume is
written back to that upload.
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

Alembic creates the PostgreSQL schema, but it does not include the shared job,
interview-question, responsibility-vector, JD-role ranking, and resume-rewrite
knowledge-base data. The
repository therefore includes the current PostgreSQL custom-format dump at
`SystemCode/backend/data/database/careerpilot-postgresql-20261002.dump`. Its
expected SHA-256 is:

```text
80D8CC733173CCBC2BD114BFA3D38E48904B0F2B0797526387FDB9C43441D36F
```

### Recommended: Docker

Run these commands from the repository root:

```powershell
docker compose up -d postgres
docker compose ps
Get-FileHash `
  "SystemCode/backend/data/database/careerpilot-postgresql-20261002.dump" `
  -Algorithm SHA256
docker cp "SystemCode/backend/data/database/careerpilot-postgresql-20261002.dump" `
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
docker exec careerpilot-postgres psql -U careerpilot -d careerpilot `
  -c "SELECT COUNT(*) AS guidelines FROM resume_guidelines;"
docker exec careerpilot-postgres psql -U careerpilot -d careerpilot `
  -c "SELECT COUNT(*) AS test_resumes FROM resume_uploads;"
```

The current shared snapshot should return `134` jobs, `215` interview
questions, `385` resume-rewrite guidelines, and `10` test resumes. It already
contains migration `20261002_0013`, the 10 hand-parsed test resumes from
`resume test/parsed/` in `resume_uploads` (no `user_profile` or `resume_rewrites` rows), all 618 JD responsibility vectors, all 369 JD Top-3 role
mappings, and all 1540 knowledge-base chunk vectors (385 guideline chunks plus
1155 example chunks). Install the Python
dependencies and apply any migrations added after the snapshot:

```powershell
cd SystemCode/backend
python -m pip install -r requirements.txt
python -m alembic upgrade head
```

`python -m scripts.backfill_job_semantics` remains available and idempotent if
the JD analysis data is later replaced or imported without its semantic cache.
`python -m scripts.backfill_resume_guideline_embeddings` likewise re-embeds only
knowledge-base chunks that are new, edited, or embedded with another model, and
`python -m scripts.evaluate_guideline_retrieval` reports retrieval hit@3 and MRR.

Then start the API and open the Swagger page:

```powershell
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
