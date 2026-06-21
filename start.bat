@echo off
echo =======================================================
echo Starting Threat Intel Platform (Backend + Frontend)
echo =======================================================

echo.
if not exist .env (
    echo [INFO] .env file not found. Creating one from .env.example with default local settings...
    copy .env.example .env > nul
)

echo.
echo [1/3] Starting Database Services (Docker Compose)...
docker compose up db redis minio neo4j -d

echo.
echo [2/3] Starting Backend (FastAPI)...
start "Backend (FastAPI)" cmd /k "cd backend && if not exist .venv (python -m venv .venv && call .venv\Scripts\activate && pip install -e .[dev]) else (call .venv\Scripts\activate) && alembic upgrade head && uvicorn app.main:app --reload"

echo.
echo [3/3] Starting Frontend (Vite/React)...
start "Frontend (Vite/React)" cmd /k "cd frontend && if not exist node_modules (npm install) && npm run dev"

echo.
echo =======================================================
echo All services are starting up!
echo - Backend API will be available at: http://localhost:8000
echo - Frontend UI will be available at: http://localhost:5173
echo.
echo Keep the new windows open to see logs and press Ctrl+C to stop them.
echo =======================================================
pause
