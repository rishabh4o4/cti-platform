import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.domain.enums import Role


class UserBase(BaseModel):
    username: str
    role: Role = Role.VIEWER
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserUpdateRole(BaseModel):
    role: Role


class UserRead(UserBase):
    id: uuid.UUID
    last_login: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserRead):
    hashed_password: str
