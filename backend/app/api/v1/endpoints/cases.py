from app.domain.enums import Role
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.api.deps import get_db, require_dashboard_principal, require_role
from app.models.case import Case
from app.schemas.auth import Principal
from app.schemas.case import CaseCreate, CaseRead
from app.models.audit import AuditLog

router = APIRouter()


@router.post("/", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_role([Role.ANALYST])),
) -> CaseRead:
    # Get sequence number
    result = await db.execute(text("SELECT nextval('case_sequence')"))
    seq_val = result.scalar()
    
    current_year = datetime.now().year
    case_number = f"LEO-{current_year}-{seq_val:04d}"

    new_case = Case(
        case_number=case_number,
        title=payload.title,
    )
    db.add(new_case)
    
    db.add(AuditLog(
        case_id=new_case.id,
        analyst_id=principal.user_id,
        analyst=principal.subject,
        action="CASE_CREATED",
        details={"case_number": case_number, "title": payload.title}
    ))
    
    await db.commit()
    await db.refresh(new_case)
    return CaseRead.model_validate(new_case)
