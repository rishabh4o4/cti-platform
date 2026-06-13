from app.domain.enums import Role
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, get_db, require_dashboard_principal, require_role
from app.schemas.auth import Principal
from app.schemas.collector import CollectorRunRequest, CollectorRunResponse, CollectorStatusResponse
from app.services.collectors import trigger_collection, list_collection_runs
from app.models.audit import AuditLog
import json

router = APIRouter()


@router.post("/run", response_model=CollectorRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_collector_run(
    payload: CollectorRunRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin()),
) -> CollectorRunResponse:
    run, msg = await trigger_collection(db, payload, commit=False)
    
    db.add(AuditLog(
        analyst=principal.subject,
        action="COLLECTOR_TRIGGERED",
        details=payload.model_dump(mode="json")
    ))
    await db.commit()
    
    return CollectorRunResponse(
        run=run,
        message=msg,
    )


@router.get("/status", response_model=CollectorStatusResponse)
async def collector_status(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> CollectorStatusResponse:
    runs = await list_collection_runs(db, limit=limit)
    return CollectorStatusResponse(runs=runs)
