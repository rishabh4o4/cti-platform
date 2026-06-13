import secrets
import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token, is_token_revoked
from app.db.session import get_db
from app.domain.enums import PrincipalType, Role
from app.schemas.auth import Principal
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def _principal_from_bearer(
    credentials: HTTPAuthorizationCredentials | None,
) -> Principal | None:
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return None
    return Principal(
        subject=str(payload["sub"]),
        principal_type=PrincipalType.DASHBOARD,
        role=Role(payload.get("role")) if payload.get("role") else None,
        user_id=uuid.UUID(payload["user_id"]) if payload.get("user_id") else None,
        jti=uuid.UUID(payload["jti"]) if payload.get("jti") else None,
        exp=payload.get("exp"),
    )


def _principal_from_api_key(api_key: str | None) -> Principal | None:
    if not api_key:
        return None
    for configured_key in settings.internal_api_keys:
        if secrets.compare_digest(api_key, configured_key):
            return Principal(
                subject="internal-service",
                principal_type=PrincipalType.INTERNAL_SERVICE,
            )
    return None


async def require_dashboard_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    principal = _principal_from_bearer(credentials)
    if principal:
        if principal.jti and await is_token_revoked(str(principal.jti), str(principal.user_id) if principal.user_id else None):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked.",
            )
        return principal
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid bearer token required.",
    )


async def require_any_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Depends(api_key_scheme),
) -> Principal:
    principal = _principal_from_bearer(credentials) or _principal_from_api_key(api_key)
    if principal:
        return principal
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid bearer token or X-API-Key required.",
    )


def require_role(allowed_roles: list[Role]) -> Callable:
    async def role_checker(
        principal: Principal = Depends(require_dashboard_principal),
        db: AsyncSession = Depends(get_db),
    ) -> Principal:
        if principal.user_id:
            user = await db.get(User, principal.user_id)
            if not user or not user.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive or deleted.")
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
        
        if principal.role != Role.ADMIN and principal.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
        
        return principal
    return role_checker


def require_admin() -> Callable:
    return require_role([Role.ADMIN])


__all__ = [
    "get_db",
    "require_dashboard_principal",
    "require_any_principal",
    "require_role",
    "require_admin",
]
