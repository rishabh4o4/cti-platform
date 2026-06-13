import structlog
from typing import Any

from asgiref.sync import async_to_sync
from celery import group
from sqlalchemy import select

from app.db.session import async_session_maker
from app.models.collection import CollectionRun
from app.models.content import ContentItem
from app.domain.enums import SourceType, CollectionRunStatus
from app.tasks.celery_app import celery_app
from app.services.reddit import RedditCollector
from app.tasks.ingest import persist_raw_content
from app.utils.datetime import utcnow  # Fix 1.3: canonical import

logger = structlog.get_logger()


@celery_app.task(
    name="app.tasks.reddit.collect_reddit_data",
    bind=True,
    max_retries=1,
)
def collect_reddit_data(self: Any) -> dict[str, Any]:
    return async_to_sync(_collect_reddit_data)()


async def _collect_reddit_data() -> dict[str, Any]:
    async with async_session_maker() as db:
        collector = RedditCollector()
        run = CollectionRun(
            source=SourceType.REDDIT,
            status=CollectionRunStatus.RUNNING,
            trigger_type="scheduled",
            metadata_={"is_mock": True} if collector.is_mock else {},
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        items, errors = collector.process_subreddits()

        items_fetched = len(items)

        try:
            # Fix 2.1: dispatch all items as a single Celery group instead of
            # one .delay() call per item, reducing broker round-trips from N to 1.
            if items:
                job = group(
                    persist_raw_content.s(item.model_dump(mode="json"))
                    for item in items
                )
                job.apply_async()

            # Fix 1.1: count items_new by checking which source_ids are new.
            # A batch SELECT is far cheaper than N individual round-trips.
            source_ids = [item.source_id for item in items]
            if source_ids:
                existing_result = await db.execute(
                    select(ContentItem.source_id).where(
                        ContentItem.source == SourceType.REDDIT,
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
            logger.exception("Failed to dispatch reddit items")
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
