import uuid
import uuid6
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow
from app.domain.enums import SourceType
from app.models.alert import Alert
from app.models.analysis import AnalysisResult


class ContentItem(TimestampMixin, Base):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_content_items_source_source_id"),
        Index("ix_content_items_source_collected_at", "source", "collected_at"),
        Index("ix_content_items_active", "collected_at", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_content_items_media_urls_gin", "media_urls", postgresql_using="gin"),
        Index("ix_content_items_metadata_gin", "metadata", postgresql_using="gin"),
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
    source_id: Mapped[str] = mapped_column(String(512), nullable=False)
    author_handle: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    media_urls: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='open', index=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    analyses: Mapped[list["AnalysisResult"]] = relationship(
        back_populates="content",
        cascade="all, delete-orphan",
        order_by=lambda: AnalysisResult.analyzed_at.desc(),
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="content",
        cascade="all, delete-orphan",
        order_by=lambda: Alert.created_at.desc(),
    )
