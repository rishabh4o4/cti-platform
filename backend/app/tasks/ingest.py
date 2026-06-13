from datetime import timedelta
from typing import Any

from asgiref.sync import async_to_sync
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from redis.exceptions import ConnectionError as RedisConnectionError

from app.schemas.content import ContentIngestRequest
from app.tasks.celery_app import celery_app
from app.utils.datetime import utcnow

# How long a run may stay in RUNNING before the watchdog marks it FAILED.
_STALE_RUN_THRESHOLD_MINUTES = 10


@celery_app.task(
    name="app.tasks.ingest.persist_raw_content",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    # Fix 5.3: only retry on *transient* infrastructure errors.
    # IntegrityError (duplicate) and ValidationError (bad payload) are
    # non-transient and should not burn retry budget.
    autoretry_for=(OperationalError, RedisConnectionError, OSError, TimeoutError),
    retry_backoff=True,
)
def persist_raw_content(self, payload: dict[str, Any]) -> dict[str, Any]:
    return async_to_sync(_persist_raw_content)(payload)


async def _persist_raw_content(payload: dict[str, Any]) -> dict[str, Any]:
    from app.db.session import async_session_maker
    from app.services.content import ingest_content

    request = ContentIngestRequest.model_validate(payload)
    async with async_session_maker() as db:
        content, created, analysis_enqueued = await ingest_content(db, request, enqueue=True)
        return {
            "content_id": str(content.id),
            "created": created,
            "analysis_enqueued": analysis_enqueued,
        }


# ---------------------------------------------------------------------------
# Fix 5.1: Watchdog task — resets CollectionRuns stuck in RUNNING.
#
# If a Celery worker is OOM-killed or SIGKILL'd mid-task, its CollectionRun
# row is left permanently in RUNNING status.  This periodic task detects runs
# that have been RUNNING for longer than _STALE_RUN_THRESHOLD_MINUTES and
# marks them FAILED so the dashboard doesn't show phantom in-progress jobs.
#
# Scheduled in celery_app.py beat_schedule as "reset-stale-runs".
# ---------------------------------------------------------------------------

@celery_app.task(name="app.tasks.ingest.reset_stale_collection_runs")
def reset_stale_collection_runs() -> dict[str, Any]:
    return async_to_sync(_reset_stale_collection_runs)()


async def _reset_stale_collection_runs() -> dict[str, Any]:
    import structlog
    from app.db.session import async_session_maker
    from app.domain.enums import CollectionRunStatus
    from app.models.collection import CollectionRun

    logger = structlog.get_logger()

    cutoff = utcnow() - timedelta(minutes=_STALE_RUN_THRESHOLD_MINUTES)

    async with async_session_maker() as db:
        result = await db.execute(
            update(CollectionRun)
            .where(
                CollectionRun.status == CollectionRunStatus.RUNNING,
                CollectionRun.started_at < cutoff,
            )
            .values(
                status=CollectionRunStatus.FAILED,
                ended_at=utcnow(),
                errors=CollectionRun.errors + [
                    f"Run marked FAILED by watchdog: still RUNNING after "
                    f"{_STALE_RUN_THRESHOLD_MINUTES} minutes."
                ],
            )
            .returning(CollectionRun.id)
        )
        stale_ids = [str(row[0]) for row in result.fetchall()]
        await db.commit()

    if stale_ids:
        logger.warning(
            "Watchdog reset stale CollectionRuns",
            count=len(stale_ids),
            run_ids=stale_ids,
        )

    return {"reset_count": len(stale_ids), "run_ids": stale_ids}
