import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceReportBase(BaseModel):
    case_number: str
    description: str
    status: str = "open"
    assigned_to: str | None = None
    source_reliability_rating: str = "C / 2"
    evidence_data: dict[str, Any] = Field(default_factory=dict)


class EvidenceReportCreate(EvidenceReportBase):
    pass


class EvidenceReportUpdate(BaseModel):
    case_number: str | None = None
    description: str | None = None
    status: str | None = None
    assigned_to: str | None = None
    source_reliability_rating: str | None = None
    evidence_data: dict[str, Any] | None = None


class EvidenceReportRead(EvidenceReportBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
