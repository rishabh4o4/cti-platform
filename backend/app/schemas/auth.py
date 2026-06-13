from pydantic import BaseModel

from app.domain.enums import PrincipalType, Role
import uuid


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class Principal(BaseModel):
    subject: str
    principal_type: PrincipalType
    role: Role | None = None
    user_id: uuid.UUID | None = None
    jti: uuid.UUID | None = None
    exp: int | None = None
