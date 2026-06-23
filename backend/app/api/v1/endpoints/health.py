import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select, text

from app.api.deps import require_role
from app.core.config import settings
from app.db.neo4j_session import get_neo4j_driver
from app.db.session import async_session_maker
from app.domain.enums import CollectionRunStatus, Role, SourceType
from app.models.collection import CollectionRun
from app.schemas.auth import Principal
from app.services.cache import get_redis
from app.tasks.celery_app import celery_app

router = APIRouter()


@router.get("/")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/deep")
async def deep_health(
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> dict:
    """Detailed dependency health check. Requires a valid bearer token."""
    checks: dict[str, str] = {}

    try:
        async with async_session_maker() as db:
            await db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:  # pragma: no cover - defensive health detail
        checks["postgres"] = "error"

    try:
        await get_redis().ping()
        checks["redis"] = "ok"
    except Exception:  # pragma: no cover - defensive health detail
        checks["redis"] = "error"

    status = "ok" if all(value == "ok" for value in checks.values()) else "degraded"
    return {"status": status, "checks": checks}


async def _get_latest_run(source: SourceType) -> CollectionRun | None:
    async with async_session_maker() as db:
        result = await db.execute(
            select(CollectionRun)
            .where(CollectionRun.source == source)
            .order_by(CollectionRun.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


def _ping_celery() -> dict[str, Any]:
    return celery_app.control.ping(timeout=2.0)


async def _check_neo4j() -> int:
    driver = await get_neo4j_driver()
    async with driver.session() as session:
        result = await session.run("MATCH (n) RETURN count(n) AS c LIMIT 1")
        record = await result.single()
        return record["c"]


@router.get("/test-error")
async def get_test_error():
    """Endpoint to verify the global exception handler."""
    raise RuntimeError("Deliberate unhandled exception")


@router.get("/system")
async def system_health(
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> dict[str, Any]:
    components = []
    
    # --- Database ---
    t0 = time.time()
    db_status = "ERROR"
    db_detail = "Failed to execute SELECT 1"
    try:
        async with async_session_maker() as db:
            await db.execute(text("SELECT 1"))
        db_status = "LIVE"
        db_detail = "OK"
    except Exception as e:
        db_detail = str(e)
    components.append({"name": "Database", "status": db_status, "latency_ms": int((time.time() - t0) * 1000), "detail": db_detail})

    # --- Redis ---
    t0 = time.time()
    redis_status = "ERROR"
    redis_detail = "Failed to ping Redis"
    try:
        await get_redis().ping()
        redis_status = "LIVE"
        redis_detail = "OK"
    except Exception as e:
        redis_detail = str(e)
    components.append({"name": "Redis", "status": redis_status, "latency_ms": int((time.time() - t0) * 1000), "detail": redis_detail})

    # --- Celery ---
    t0 = time.time()
    celery_status = "ERROR"
    celery_detail = "timeout"
    try:
        ping_result = await asyncio.to_thread(_ping_celery)
        if ping_result:
            celery_status = "LIVE"
            celery_detail = str(ping_result)
        else:
            celery_status = "ERROR"
            celery_detail = "timeout"
    except Exception as e:
        celery_detail = str(e)
    components.append({"name": "Celery", "status": celery_status, "latency_ms": int((time.time() - t0) * 1000), "detail": celery_detail})

    # --- Telegram ---
    t0 = time.time()
    telegram_status = "ERROR"
    telegram_detail = ""
    try:
        if not settings.telegram_session_string or settings.telegram_session_string == "dummy":
            telegram_status = "OFFLINE"
            telegram_detail = "StringSession is dummy or not configured"
        else:
            run = await _get_latest_run(SourceType.TELEGRAM)
            if not run:
                telegram_status = "OFFLINE"
                telegram_detail = "No runs exist"
            elif run.status == CollectionRunStatus.FAILED:
                telegram_status = "ERROR"
                telegram_detail = f"Last run failed. Errors: {run.errors}"
            else:
                telegram_status = "LIVE"
                telegram_detail = f"Last run status: {run.status}"
    except Exception as e:
        telegram_detail = str(e)
    components.append({"name": "Telegram", "status": telegram_status, "latency_ms": int((time.time() - t0) * 1000), "detail": telegram_detail})

    # --- Reddit ---
    t0 = time.time()
    reddit_status = "ERROR"
    reddit_detail = ""
    try:
        run = await _get_latest_run(SourceType.REDDIT)
        if not run:
            reddit_status = "OFFLINE"
            reddit_detail = "No runs exist"
        elif run.metadata_.get("is_mock"):
            reddit_status = "MOCK"
            reddit_detail = "Latest run was mock"
        else:
            reddit_status = "LIVE"
            reddit_detail = f"Latest run completed at {run.ended_at}"
    except Exception as e:
        reddit_detail = str(e)
    components.append({"name": "Reddit", "status": reddit_status, "latency_ms": int((time.time() - t0) * 1000), "detail": reddit_detail})

    # --- X ---
    t0 = time.time()
    x_status = "ERROR"
    x_detail = ""
    try:
        run = await _get_latest_run(SourceType.X)
        if not run:
            x_status = "OFFLINE"
            x_detail = "No runs exist"
        elif run.metadata_.get("is_mock"):
            x_status = "MOCK"
            x_detail = "Latest run was mock"
        else:
            x_status = "LIVE"
            x_detail = f"Latest run completed at {run.ended_at}"
    except Exception as e:
        x_detail = str(e)
    components.append({"name": "X", "status": x_status, "latency_ms": int((time.time() - t0) * 1000), "detail": x_detail})

    # --- NLP Engine ---
    t0 = time.time()
    nlp_status = "ERROR"
    nlp_detail = ""
    try:
        sig = celery_app.signature("app.tasks.nlp.ping_nlp")
        async_result = sig.apply_async()
        model_name = await asyncio.to_thread(async_result.get, timeout=2.0)
        nlp_status = "LIVE"
        nlp_detail = f"Model loaded: {model_name}"
    except Exception as e:
        nlp_detail = str(e)
    components.append({"name": "NLP Engine", "status": nlp_status, "latency_ms": int((time.time() - t0) * 1000), "detail": nlp_detail})

    # --- Graph Engine ---
    t0 = time.time()
    graph_status = "ERROR"
    graph_detail = ""
    try:
        node_count = await _check_neo4j()
        graph_status = "LIVE"
        graph_detail = f"Neo4j node count query ok ({node_count})"
    except Exception as e:
        graph_detail = str(e)
    components.append({"name": "Graph Engine", "status": graph_status, "latency_ms": int((time.time() - t0) * 1000), "detail": graph_detail})

    # --- Calculate Overall Status ---
    overall = "HEALTHY"
    has_error = any(c["status"] == "ERROR" for c in components)
    
    db_redis_error = any(
        c["status"] == "ERROR" and c["name"] in ("Database", "Redis") 
        for c in components
    )

    if db_redis_error:
        overall = "CRITICAL"
    elif has_error:
        overall = "DEGRADED"

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "overall": overall,
        "components": components
    }
