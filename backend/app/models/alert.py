import uuid
import uuid6
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, text, Enum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

from app.domain.enums import RiskLabel

if TYPE_CHECKING:
    from app.models.content import ContentItem


class Alert(TimestampMixin, Base):
    """
    Fired when a ContentItem's risk score breaches the configured threshold.

    Inherits created_at / updated_at from TimestampMixin for full audit trail.
    resolved_at records when the alert was explicitly resolved by an analyst.
    """

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_content_resolved", "content_id", "resolved"),
        Index("ix_alerts_created_resolved", "created_at", "resolved"),
        Index("ix_alerts_notified_via_gin", "notified_via", postgresql_using="gin"),
        Index("uq_alerts_content_unresolved", "content_id", unique=True, postgresql_where=text("resolved = false")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    threshold_hit: Mapped[float] = mapped_column(Float, nullable=False)
    # Standardised to list[str]: each entry is a notification channel name.
    notified_via: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    analyst_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    severity: Mapped[RiskLabel] = mapped_column(
        Enum(
            RiskLabel,
            name="risk_label",
            native_enum=False,
            length=32,
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
        default=RiskLabel.HIGH,
    )
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suppress_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    content: Mapped["ContentItem"] = relationship(back_populates="alerts")
