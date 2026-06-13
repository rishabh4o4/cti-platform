from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import CollectionRunStatus, SourceType
from app.models.collection import CollectionRun
from app.schemas.collector import CollectorRunRequest
from app.utils.datetime import utcnow


async def trigger_collection(
    db: AsyncSession,
    payload: CollectorRunRequest,
    commit: bool = True,
) -> tuple[CollectionRun, str]:
    now = utcnow()
    run = CollectionRun(
        source=payload.source,
        status=CollectionRunStatus.PENDING,
        trigger_type="manual",
        items_fetched=0,
        items_new=0,
        errors=[],
        started_at=now,
        ended_at=None,
    )
    db.add(run)
    if commit:
        await db.commit()
        await db.refresh(run)
    else:
        await db.flush()

    msg = "Collector task enqueued."
    if payload.source == SourceType.REDDIT:
        from app.tasks.reddit import collect_reddit_data
        collect_reddit_data.delay()
    elif payload.source == SourceType.TELEGRAM:
        from app.tasks.telegram import collect_telegram_data
        collect_telegram_data.delay()
    elif payload.source == SourceType.X:
        from app.tasks.x import collect_x_data
        collect_x_data.delay()
    else:
        msg = f"No task mapped for source: {payload.source}"

    return run, msg


async def list_collection_runs(db: AsyncSession, limit: int = 50) -> list[CollectionRun]:
    result = await db.execute(
        select(CollectionRun)
        .distinct(CollectionRun.source)
        .order_by(CollectionRun.source, CollectionRun.started_at.desc())
    )
    return list(result.scalars().all())
