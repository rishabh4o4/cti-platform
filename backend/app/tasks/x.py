import structlog
from typing import Any

from asgiref.sync import async_to_sync  # Fix 2.4/5.2: consistent async bridging
from celery import group
from sqlalchemy import select

from app.db.session import async_session_maker
from app.models.collection import CollectionRun
from app.models.content import ContentItem
from app.domain.enums import SourceType, CollectionRunStatus
from app.tasks.celery_app import celery_app
from app.tasks.ingest import persist_raw_content
from app.services.x import XCollector
from app.utils.datetime import utcnow  # Fix 1.3: canonical import

logger = structlog.get_logger()


@celery_app.task(
    name="app.tasks.x.collect_x_data",
    bind=True,
    max_retries=1,
)
def collect_x_data(self: Any) -> dict[str, Any]:
    # Fix 2.4/5.2: use async_to_sync instead of manual asyncio.new_event_loop().
    return async_to_sync(_collect_x_data)()


async def _collect_x_data() -> dict[str, Any]:
    async with async_session_maker() as db:
        run = CollectionRun(
            source=SourceType.X,
            status=CollectionRunStatus.RUNNING,
            trigger_type="scheduled",
            # Fix 1.2: metadata_ column now exists on CollectionRun — this flag
            # is no longer silently dropped.
            metadata_={"is_mock": True},
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        collector = XCollector()
        items, errors = await collector.process_accounts()

        items_fetched = len(items)

        try:
            # Fix 2.1: single Celery group dispatch instead of N individual .delay() calls.
            if items:
                job = group(
                    persist_raw_content.s(item.model_dump(mode="json"))
                    for item in items
                )
                job.apply_async()

            # Fix 1.1: count items_new via a batch SELECT of already-stored source_ids.
            source_ids = [item.source_id for item in items]
            if source_ids:
                existing_result = await db.execute(
                    select(ContentItem.source_id).where(
                        ContentItem.source == SourceType.X,
                        ContentItem.source_id.in_(source_ids),
                    )
                )
                existing_ids = set(existing_result.scalars().all())
            else:
                existing_ids = set()

            items_new = sum(1 for item in items if item.source_id not in existing_ids)

            run.status = CollectionRunStatus.COMPLETED if not errors else CollectionRunStatus.FAILED
            run.items_fetched = items_fetched
            run.items_new = items_new
            run.errors = errors
            run.ended_at = utcnow()

            await db.commit()
        except Exception as e:
            logger.exception("Failed to dispatch X items")
            run.status = CollectionRunStatus.FAILED
            run.errors = errors + [str(e)]
            run.ended_at = utcnow()
            await db.commit()

        return {
            "run_id": str(run.id),
            "status": run.status.value,
            "items_fetched": items_fetched,
            "errors": run.errors,
        }
