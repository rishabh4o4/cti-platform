import uuid
import uuid6
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.domain.enums import CollectionRunStatus, SourceType


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    __table_args__ = (
        Index("ix_collection_runs_source_started", "source", "started_at"),
        Index("ix_collection_runs_status_started", "status", "started_at"),
        Index("ix_collection_runs_errors_gin", "errors", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    source: Mapped[SourceType] = mapped_column(
        Enum(
            SourceType,
            name="source_type",
            native_enum=False,
            length=32,
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
    )
    status: Mapped[CollectionRunStatus] = mapped_column(
        Enum(
            CollectionRunStatus,
            name="collection_run_status",
            native_enum=False,
            length=32,
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
        default=CollectionRunStatus.PENDING,
    )
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    items_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Standardised to list[str]: each entry is a human-readable error message.
    errors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # Arbitrary per-run metadata (e.g. {"is_mock": True} for the X mock client).
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        index=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
