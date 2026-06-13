import uuid
import uuid6
import structlog
import hashlib
from datetime import datetime

from sqlalchemy import String as SAString, cast, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import RiskLabel, SourceType
from app.models.analysis import AnalysisResult
from app.models.content import ContentItem
from app.schemas.content import ContentIngestRequest
from app.utils.datetime import utcnow

logger = structlog.get_logger()


async def get_content_by_source_id(
    db: AsyncSession,
    source: SourceType,
    source_id: str,
) -> ContentItem | None:
    result = await db.execute(
        select(ContentItem).where(
            ContentItem.source == source,
            ContentItem.source_id == source_id,
        )
    )
    return result.scalar_one_or_none()


async def get_content_by_id(
    db: AsyncSession,
    content_id: uuid.UUID,
    include_deleted: bool = False,
) -> ContentItem | None:
    stmt = (
        select(ContentItem)
        .options(selectinload(ContentItem.analyses), selectinload(ContentItem.alerts))
        .where(ContentItem.id == content_id)
    )
    if not include_deleted:
        stmt = stmt.where(ContentItem.deleted_at.is_(None))

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_content(
    db: AsyncSession,
    *,
    source: SourceType | None = None,
    label: RiskLabel | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    entity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ContentItem], int]:
    filters = [ContentItem.deleted_at.is_(None)]

    if source:
        filters.append(ContentItem.source == source)
    if from_ts:
        filters.append(ContentItem.collected_at >= from_ts)
    if to_ts:
        filters.append(ContentItem.collected_at <= to_ts)
    if label:
        labeled_content = select(AnalysisResult.content_id).where(
            AnalysisResult.risk_label == label
        )
        filters.append(ContentItem.id.in_(labeled_content))
    if entity:
        escaped_entity = entity.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        entity_content = select(AnalysisResult.content_id).where(
            cast(AnalysisResult.nlp_flags, SAString).ilike(f"%{escaped_entity}%", escape="\\")
        )
        filters.append(ContentItem.id.in_(entity_content))

    # Both queries run inside a single transaction so the COUNT and the page
    # are consistent — new rows inserted between the two calls won't cause
    # the total to drift from the actual page size.
    async with db.begin_nested():
        total_result = await db.execute(
            select(func.count()).select_from(ContentItem).where(*filters)
        )
        total = int(total_result.scalar_one())

        result = await db.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.analyses), selectinload(ContentItem.alerts))
            .where(*filters)
            .order_by(ContentItem.collected_at.desc())
            .limit(limit)
            .offset(offset)
        )
    return list(result.scalars().all()), total


async def ingest_content(
    db: AsyncSession,
    payload: ContentIngestRequest,
    *,
    enqueue: bool = True,
) -> tuple[ContentItem, bool, bool]:
    """Insert a content item if it does not already exist.

    Uses ``INSERT … ON CONFLICT DO NOTHING`` to atomically handle the
    duplicate case without a TOCTOU race between the pre-check SELECT and
    the INSERT.

    Returns:
        (content, created, analysis_enqueued)
    """
    now = utcnow()
    new_id = uuid6.uuid7()

    content_hash_val = hashlib.sha256(payload.raw_text.encode("utf-8")).hexdigest()

    stmt = (
        pg_insert(ContentItem)
        .values(
            id=new_id,
            source=payload.source,
            source_id=payload.source_id,
            author_handle=payload.author_handle,
            raw_text=payload.raw_text,
            content_hash=content_hash_val,
            media_urls=[str(url) for url in payload.media_urls],
            collected_at=payload.collected_at or now,
            metadata_=payload.metadata,
            # TimestampMixin columns have Python-level defaults; supply them
            # explicitly so they are included in the INSERT values clause.
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_content_items_source_source_id")
        .returning(ContentItem.id)
    )

    result = await db.execute(stmt)
    inserted_id = result.scalar_one_or_none()

    if inserted_id is None:
        # A row with (source, source_id) already exists — fetch and return it.
        await db.rollback()
        logger.info(
            "Duplicate content skipped",
            source=payload.source,
            source_id=payload.source_id,
        )
        existing = await get_content_by_source_id(db, payload.source, payload.source_id)
        if existing:
            return existing, False, False
        # Should never happen: conflict fired but record is gone.
        raise RuntimeError(
            f"Conflict on ({payload.source!r}, {payload.source_id!r}) "
            "but existing record not found after rollback."
        )

    await db.commit()

    # Re-fetch with relationships populated (analyses, alerts).
    content = await get_content_by_id(db, inserted_id)
    if content is None:
        raise RuntimeError(f"Inserted content {inserted_id} not found immediately after commit.")

    # Invalidate the dashboard cache so new content is reflected immediately.
    from app.services.cache import delete_key

    await delete_key("dashboard:summary")

    analysis_enqueued = False
    if enqueue and payload.enqueue_analysis:
        from app.tasks.workflow import enqueue_analysis_workflow

        enqueue_analysis_workflow(content.id)
        analysis_enqueued = True

    return content, True, analysis_enqueued


async def soft_delete_content(db: AsyncSession, content_id: uuid.UUID) -> ContentItem | None:
    content = await get_content_by_id(db, content_id)
    if not content:
        return None

    content.deleted_at = utcnow()
    await db.commit()
    await db.refresh(content)
    return content
