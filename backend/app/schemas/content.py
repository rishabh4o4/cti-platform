import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import SourceType
from app.schemas.alert import AlertRead
from app.schemas.analysis import AnalysisResultRead


class RawContentItem(BaseModel):
    source: SourceType
    source_id: str = Field(min_length=1, max_length=512)
    author_handle: str | None = Field(default=None, max_length=512)
    raw_text: str = Field(default="", max_length=100000)
    media_urls: list[str] = Field(default_factory=list)
    collected_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContentIngestRequest(RawContentItem):
    enqueue_analysis: bool = True


class ContentItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    source: SourceType
    source_id: str
    author_handle: str | None = None
    raw_text: str
    media_urls: list[str]
    collected_at: datetime
    deleted_at: datetime | None = None
    status: str = "open"
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime


class ContentItemDetail(ContentItemRead):
    latest_analysis: AnalysisResultRead | None = None
    alerts: list[AlertRead] = Field(default_factory=list)


class ContentIngestResponse(BaseModel):
    content: ContentItemRead
    created: bool
    analysis_enqueued: bool

