import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.domain.enums import RiskLabel, SourceType


class TrendPoint(BaseModel):
    day: date
    count: int


class DashboardSummaryResponse(BaseModel):
    total_items_24h: int
    open_alerts: int
    average_risk_score: float
    items_by_source: dict[SourceType, int]
    seven_day_trend: list[TrendPoint]


class HeatmapCell(BaseModel):
    source: SourceType
    label: RiskLabel
    count: int


class TopThreatItem(BaseModel):
    content_id: uuid.UUID
    source: SourceType
    author_handle: str | None = None
    raw_text_preview: str
    risk_score: float
    risk_label: RiskLabel
    analyzed_at: datetime
