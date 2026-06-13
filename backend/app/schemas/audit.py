import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AuditLogCreate(BaseModel):
    content_id: uuid.UUID | None = None
    case_id: uuid.UUID | None = None
    action: str
    details: str | None = None


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content_id: uuid.UUID | None
    case_id: uuid.UUID | None
    analyst: str
    action: str
    details: str | None
    timestamp: datetime
