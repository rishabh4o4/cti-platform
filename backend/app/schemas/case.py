import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class CaseCreate(BaseModel):
    title: str


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_number: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
