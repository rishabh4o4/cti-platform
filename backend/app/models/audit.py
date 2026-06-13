import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base
from app.utils.datetime import utcnow


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_action_timestamp", "action", "timestamp"),
        Index("ix_audit_logs_analyst_timestamp", "analyst", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), index=True, nullable=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=True)
    analyst_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    analyst: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
