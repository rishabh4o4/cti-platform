import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AnalystNoteCreate(BaseModel):
    note: str


class AnalystNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content_id: uuid.UUID
    author: str
    note: str
    created_at: datetime
