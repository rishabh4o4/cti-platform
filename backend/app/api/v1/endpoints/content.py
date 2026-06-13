import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, get_db, require_any_principal, require_dashboard_principal, require_role
from app.domain.enums import RiskLabel, SourceType, Role, PrincipalType
from app.schemas.auth import Principal
from app.schemas.common import Page
from app.schemas.content import (
    ContentIngestRequest,
    ContentIngestResponse,
    ContentItemDetail,
    ContentItemRead,
)
from app.services.analysis import get_latest_analysis
from app.services.content import (
    get_content_by_id,
    ingest_content,
    list_content,
    soft_delete_content,
)
from app.models.note import AnalystNote
from app.models.audit import AuditLog
from app.schemas.note import AnalystNoteCreate, AnalystNoteRead
from sqlalchemy import select

router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)

# --- Status transition schema & state machine ---

class StatusUpdate(BaseModel):
    status: str

VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"under_review"},
    "under_review": {"escalated", "closed"},
    "escalated": {"under_review", "closed"},
    "closed": {"open"},
}


@router.get("", response_model=Page[ContentItemRead])
async def list_content_items(
    source: SourceType | None = None,
    label: RiskLabel | None = None,
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    entity: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> Page[ContentItemRead]:
    items, total = await list_content(
        db,
        source=source,
        label=label,
        from_ts=from_ts,
        to_ts=to_ts,
        entity=entity,
        limit=limit,
        offset=offset,
    )
    return Page[ContentItemRead](items=items, total=total, limit=limit, offset=offset)


@router.post("/ingest", response_model=ContentIngestResponse, status_code=status.HTTP_202_ACCEPTED)
@_limiter.limit("100/minute")
async def ingest_content_item(
    request: Request,
    payload: ContentIngestRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_any_principal),
) -> ContentIngestResponse:
    if principal.principal_type == PrincipalType.DASHBOARD:
        if principal.role not in [Role.ADMIN, Role.ANALYST]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
    content, created, analysis_enqueued = await ingest_content(
        db,
        payload,
        enqueue=payload.enqueue_analysis,
    )
    
    db.add(AuditLog(
        content_id=content.id,
        analyst_id=getattr(principal, 'user_id', None),
        analyst=principal.subject,
        action="CONTENT_INGESTED",
        details={"source": payload.source, "created": created}
    ))
    await db.commit()
    return ContentIngestResponse(
        content=ContentItemRead.model_validate(content),
        created=created,
        analysis_enqueued=analysis_enqueued,
    )


@router.get("/{content_id}", response_model=ContentItemDetail)
async def get_content_item(
    content_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> ContentItemDetail:
    content = await get_content_by_id(db, content_id)
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content item not found.")

    latest_analysis = await get_latest_analysis(db, content.id)
    base = ContentItemRead.model_validate(content).model_dump()
    return ContentItemDetail(
        **base,
        latest_analysis=latest_analysis,
        alerts=content.alerts,
    )


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content_item(
    content_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_admin()),
) -> Response:
    content = await soft_delete_content(db, content_id)
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content item not found.")
        
    audit = AuditLog(
        content_id=content_id,
        analyst=principal.subject,
        action="CONTENT_DELETED",
        details={"status": content.status}
    )
    db.add(audit)
    await db.commit()
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{content_id}/status", response_model=ContentItemRead)
async def update_content_status(
    content_id: uuid.UUID,
    payload: StatusUpdate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_role([Role.ANALYST])),
) -> ContentItemRead:
    content = await get_content_by_id(db, content_id)
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content item not found.")

    old_status = content.status
    new_status = payload.status

    allowed = VALID_TRANSITIONS.get(old_status)
    if allowed is None or new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition from '{old_status}' to '{new_status}'. "
                   f"Allowed transitions from '{old_status}': {sorted(allowed) if allowed else 'none (terminal state)'}.",
        )

    content.status = new_status

    audit = AuditLog(
        content_id=content_id,
        analyst=principal.subject,
        action="STATUS_UPDATED",
        details={"old_status": old_status, "new_status": new_status},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(content)
    return ContentItemRead.model_validate(content)


@router.post("/{content_id}/notes", response_model=AnalystNoteRead, status_code=status.HTTP_201_CREATED)
async def create_analyst_note(
    content_id: uuid.UUID,
    payload: AnalystNoteCreate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_role([Role.ANALYST])),
) -> AnalystNoteRead:
    content = await get_content_by_id(db, content_id)
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content item not found.")
    
    note = AnalystNote(
        content_id=content_id,
        author=principal.subject,
        note=payload.note,
    )
    db.add(note)
    
    audit = AuditLog(
        content_id=content_id,
        analyst=principal.subject,
        action="NOTE_ADDED",
        details={"note_id": str(note.id), "preview": payload.note[:200]}
    )
    db.add(audit)
    
    await db.commit()
    await db.refresh(note)
    return AnalystNoteRead.model_validate(note)


@router.get("/{content_id}/notes", response_model=list[AnalystNoteRead])
async def list_analyst_notes(
    content_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> list[AnalystNoteRead]:
    result = await db.execute(
        select(AnalystNote)
        .where(AnalystNote.content_id == content_id)
        .order_by(AnalystNote.created_at.desc())
    )
    return [AnalystNoteRead.model_validate(n) for n in result.scalars().all()]

