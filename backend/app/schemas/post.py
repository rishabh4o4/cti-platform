import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PostBase(BaseModel):
    title: str
    content: str
    author_id: str
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata")


class PostCreate(PostBase):
    pass


class PostUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    author_id: str | None = None
    metadata_: dict[str, Any] | None = Field(default=None, alias="metadata")


class PostRead(PostBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
