import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


from app.domain.enums import RiskLabel, SourceType

class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content_id: uuid.UUID
    threshold_hit: float
    notified_via: list[str]
    severity: RiskLabel
    resolved: bool
    resolved_by: str | None = None
    analyst_note: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    escalated_at: datetime | None = None
    suppress_until: datetime | None = None


class AlertResolveRequest(BaseModel):
    analyst_note: str | None = Field(default=None, max_length=4000)
    suppress_minutes: int = Field(default=0, ge=0, le=1440)


class AlertConfigRequest(BaseModel):
    high_threshold: float = Field(ge=0, le=100)
    critical_threshold: float = Field(ge=0, le=100)
    notification_channels: list[str] = Field(default_factory=list)


class AlertConfigResponse(AlertConfigRequest):
    source: str


from app.domain.enums import RiskLabel, SourceType

class AlertWebSocketPayload(BaseModel):
    id: uuid.UUID
    content_id: uuid.UUID
    severity: RiskLabel
    risk_score: float
    created_at: datetime
    source: SourceType
    author_handle: str | None
    raw_text: str
    top_factors: list[str]
    data_confidence: float
