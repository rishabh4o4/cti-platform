from app.domain.enums import Role
from datetime import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, require_dashboard_principal, require_role
from app.models.audit import AuditLog
from app.schemas.auth import Principal
from app.schemas.audit import AuditLogCreate, AuditLogRead

router = APIRouter()


@router.get("/", response_model=list[AuditLogRead])
async def get_audit_logs(
    analyst: str | None = Query(None, description="Filter by analyst username"),
    action: str | None = Query(None, description="Filter by action name"),
    from_timestamp: datetime | None = Query(None, alias="from_timestamp"),
    to_timestamp: datetime | None = Query(None, alias="to_timestamp"),
    content_id: uuid.UUID = Query(None, description="Filter by content ID"),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> list[AuditLogRead]:
    stmt = select(AuditLog)
    if analyst:
        stmt = stmt.where(AuditLog.analyst == analyst)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if from_timestamp:
        stmt = stmt.where(AuditLog.timestamp >= from_timestamp)
    if to_timestamp:
        stmt = stmt.where(AuditLog.timestamp <= to_timestamp)
    if content_id:
        stmt = stmt.where(AuditLog.content_id == content_id)
        
    stmt = stmt.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
    
    result = await db.execute(stmt)
    return [AuditLogRead.model_validate(log) for log in result.scalars().all()]
