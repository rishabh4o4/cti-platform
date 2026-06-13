import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import RiskLabel


class AnalysisResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content_id: uuid.UUID
    risk_score: float
    risk_label: RiskLabel
    nlp_flags: dict[str, Any] = Field(default_factory=dict)
    vision_flags: dict[str, Any] = Field(default_factory=dict)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    tactics: list[str] = Field(default_factory=list)
    techniques: list[str] = Field(default_factory=list)
    weights_snapshot: dict[str, Any] | None = None
    model_version: str
    analyzed_at: datetime


class AnalysisResultUpdate(BaseModel):
    tactics: list[str] | None = None
    techniques: list[str] | None = None


class AnalysisTriggerResponse(BaseModel):
    content_id: uuid.UUID
    enqueued: bool
    message: str


class RiskLabelCount(BaseModel):
    label: RiskLabel
    count: int


class SourceCount(BaseModel):
    source: str
    count: int


class ScoreBucket(BaseModel):
    bucket: str
    count: int


class AnalysisStatsResponse(BaseModel):
    total_analyzed: int
    label_counts: list[RiskLabelCount]
    source_breakdown: list[SourceCount]
    score_distribution: list[ScoreBucket]
