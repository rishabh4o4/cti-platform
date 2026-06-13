import uuid
import uuid6
from typing import Any

from sqlalchemy import Index, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class EvidenceReport(TimestampMixin, Base):
    __tablename__ = "evidence_reports"
    __table_args__ = (
        Index("ix_evidence_reports_evidence_data_gin", "evidence_data", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    content_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False, index=True)
    alert_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=True, index=True)
    case_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    report_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open", index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    source_reliability_rating: Mapped[str] = mapped_column(String(10), nullable=False, default="C / 2")
    evidence_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
