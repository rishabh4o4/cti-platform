# AI Harmful Content Detection Backend

Production-ready FastAPI backend skeleton for the threat intelligence architecture. It includes PostgreSQL models, Alembic migrations, Redis, Celery queues, Docker Compose, auth primitives, and API routes for content, analysis, alerts, dashboard data, and collector controls.

Collectors and AI model pipelines are intentionally not implemented yet. Their task entry points return explicit placeholder metadata so the rest of the system can be wired, tested, and extended safely.

## Quick Start

```bash
# 1. Bootstrap environment variables
copy .env.example .env
# Edit .env and set the three REQUIRED secrets:
#   JWT_SECRET_KEY  — generate with: python -c "import secrets; print(secrets.token_hex(32))"
#   ANALYST_PASSWORD — a strong password (bcrypt-hashed automatically at startup)
#   MINIO_SECRET_KEY — a strong MinIO secret
# Optional tuning:
#   GUNICORN_WORKERS — Defaults to 2. Formula: (2 × CPU_cores) + 1
#   NEO4J_MAX_POOL_SIZE — Defaults to 10.

# 2. Start all services (Backend + Frontend + DBs)
docker compose -f docker-compose.prod.yml up --build
```

The UI will be available at `http://localhost:80` (or `http://localhost` depending on your setup).
The API will be available at `http://localhost:8000`.
The Neo4j Graph Database Browser UI is available at `http://localhost:7474`.

Useful endpoints:

- `GET /api/v1/health` — liveness probe (unauthenticated)
- `GET /api/v1/health/deep` — deep dependency check (requires JWT)
- `GET /api/v1/graph/stats` — Neo4j graph nodes and edge statistics
- `POST /api/v1/auth/token`
- `POST /api/v1/content/ingest`
- `GET /api/v1/content`
- `GET /api/v1/dashboard/summary`

## Local Development

For development, you can start all services automatically on Windows using the provided batch script:

```cmd
start.bat
```

Alternatively, you can start the services manually:

**1. Start Database Services**
```bash
docker compose up db redis minio neo4j -d
```

**2. Start the Backend**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

**3. Start the Frontend**
```bash
cd frontend
npm install
npm run dev
```

Run tests:

```bash
cd backend
pytest
```

## Architecture Notes

- FastAPI is the only externally exposed application service.
- PostgreSQL stores durable evidence and operational records.
- Redis is used as the Celery broker, result backend, and dashboard/config cache.
- Celery queues are split by future workload: `ingest`, `nlp`, `vision`, `scoring`, and `alerts`.
- `content_items` are soft-deleted with `deleted_at`; records are not hard-deleted by API routes.
- `analysis_results` are append-only and versioned by `model_version`.
- Collector control endpoints exist, but collector implementations are deferred.
- NLP and vision workers are placeholders only; no model inference code is included.

## Default Local Auth

Dashboard-style routes use JWT bearer auth. Local credentials come from `.env`:

- `ANALYST_USERNAME`
- `ANALYST_PASSWORD` — stored as plaintext in `.env`, **bcrypt-hashed automatically at startup**

Internal service calls may use:

- `X-API-Key: <one value from INTERNAL_API_KEYS>`

Replace these primitives with an IdP or government SSO integration before production deployment.

## First Migration

The `alembic/versions/` directory is empty in the skeleton. Generate the initial schema:

```bash
cd backend
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```
