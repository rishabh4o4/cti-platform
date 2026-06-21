# Cyber Threat Intelligence Platform

The **Cyber Threat Intelligence Platform** is a comprehensive, production-ready system designed to help law enforcement agencies proactively monitor, analyze, and mitigate cyber threats. By unifying automated data collection, artificial intelligence, and real-time alerts, the platform empowers intelligence analysts to rapidly detect harmful content, map threat actor networks, and respond to incidents efficiently.

## Core Capabilities

- **Automated Data Collection**: Ingests threat data and content from diverse open-source, deep web, and dark web sources for centralized processing.
- **AI-Powered Analysis**: Utilizes advanced Natural Language Processing (NLP) and Computer Vision to automatically score and flag malicious, illicit, or harmful content.
- **Graph-Based Threat Mapping**: Leverages graph database technology (Neo4j) to map complex relationships between entities, uncovering hidden threat actor networks and syndicates.
- **Real-Time Alerting**: Automatically routes high-severity threats to analysts through priority-based alert queues for immediate action.
- **Unified Analyst Dashboard**: Provides law enforcement personnel with a clear, real-time view of the active threat landscape, ongoing investigations, and system telemetry.

This repository provides the complete core architecture, including a FastAPI backend, a modern React/Vite frontend, PostgreSQL models, Celery distributed worker queues, Docker Compose orchestration, and secure authentication primitives. 

*(Note: Specific third-party data collectors and proprietary AI model inference pipelines are implemented as stubs. This intentionally allows agencies to plug in their own classified, proprietary, or specialized models securely without exposing sensitive methods.)*

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
