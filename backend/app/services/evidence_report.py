import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence_report import EvidenceReport
from app.schemas.evidence_report import EvidenceReportCreate, EvidenceReportUpdate


async def get_evidence_report(db: AsyncSession, report_id: uuid.UUID) -> EvidenceReport | None:
    result = await db.execute(select(EvidenceReport).where(EvidenceReport.id == report_id))
    return result.scalar_one_or_none()


async def get_evidence_reports(db: AsyncSession, skip: int = 0, limit: int = 100) -> Sequence[EvidenceReport]:
    result = await db.execute(select(EvidenceReport).offset(skip).limit(limit))
    return result.scalars().all()


async def create_evidence_report(db: AsyncSession, obj_in: EvidenceReportCreate) -> EvidenceReport:
    db_obj = EvidenceReport(**obj_in.model_dump(exclude_unset=True))
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def update_evidence_report(db: AsyncSession, db_obj: EvidenceReport, obj_in: EvidenceReportUpdate) -> EvidenceReport:
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def delete_evidence_report(db: AsyncSession, db_obj: EvidenceReport) -> None:
    await db.delete(db_obj)
    await db.commit()
