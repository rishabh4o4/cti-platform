from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ApiMessage(BaseModel):
    message: str


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)


class JsonDict(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: dict[str, Any] = Field(default_factory=dict)
