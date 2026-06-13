import uuid
import uuid6
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.domain.enums import RiskLabel

if TYPE_CHECKING:
    from app.models.content import ContentItem

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        Index("ix_analysis_results_content_analyzed_at", "content_id", "analyzed_at"),
        Index("ix_analysis_results_content_analyzed_desc", "content_id", text("analyzed_at DESC")),
        Index("ix_analysis_results_label_score", "risk_label", "risk_score"),
        Index("ix_analysis_results_nlp_flags_gin", "nlp_flags", postgresql_using="gin"),
        Index("ix_analysis_results_vision_flags_gin", "vision_flags", postgresql_using="gin"),
        Index("ix_analysis_results_score_breakdown_gin", "score_breakdown", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_label: Mapped[RiskLabel] = mapped_column(
        Enum(
            RiskLabel,
            name="risk_label",
            native_enum=False,
            length=32,
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
        default=RiskLabel.LOW,
        index=True,
    )
    nlp_flags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    vision_flags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(128), nullable=True)
    weights_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=True)
    data_confidence: Mapped[str] = mapped_column(String(32), nullable=True)
    tactics: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    techniques: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        index=True,
    )

    content: Mapped["ContentItem"] = relationship(back_populates="analyses")
