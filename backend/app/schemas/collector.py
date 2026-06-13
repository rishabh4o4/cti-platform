import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import CollectionRunStatus, SourceType


class CollectorRunRequest(BaseModel):
    source: SourceType
    reason: str | None = None


class CollectionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    source: SourceType
    status: CollectionRunStatus
    trigger_type: str
    items_fetched: int
    items_new: int
    errors: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    started_at: datetime
    ended_at: datetime | None = None


class CollectorRunResponse(BaseModel):
    run: CollectionRunRead
    message: str


class CollectorStatusResponse(BaseModel):
    runs: list[CollectionRunRead]
