from app.domain.enums import Role, ReliabilityRating
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_dashboard_principal, require_role
from app.models.analysis import AnalysisResult
from app.models.audit import AuditLog
from app.models.content import ContentItem
from app.models.note import AnalystNote
from app.models.evidence_report import EvidenceReport
from app.models.alert import Alert
from app.schemas.auth import Principal

router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ExportSection(BaseModel):
    title: str
    content: str


class ContentExportResponse(BaseModel):
    case_title: str
    exported_at: str
    exported_by: str
    sections: list[ExportSection]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(value: object) -> str:
    """Return a human-readable string for a value that may be a dict/list."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=str)
    if value is None:
        return "N/A"
    return str(value)


def _build_content_section(item: ContentItem) -> ExportSection:
    lines = [
        f"Source: {item.source.value if hasattr(item.source, 'value') else item.source}",
        f"Source ID: {item.source_id}",
        f"Author: {item.author_handle or 'N/A'}",
        f"Status: {item.status}",
        f"Collected At: {item.collected_at.isoformat() if item.collected_at else 'N/A'}",
        "",
        "--- Raw Text ---",
        item.raw_text or "(empty)",
    ]
    return ExportSection(title="Content Overview", content="\n".join(lines))


def _build_risk_section(analysis: AnalysisResult) -> ExportSection:
    lines = [
        f"Risk Score: {analysis.risk_score}",
        f"Risk Label: {analysis.risk_label.value if hasattr(analysis.risk_label, 'value') else analysis.risk_label}",
        f"Model Version: {analysis.model_version}",
        f"Engine Version: {analysis.engine_version or 'N/A'}",
        f"Data Confidence: {analysis.data_confidence or 'N/A'}",
        "",
        "Score Breakdown:",
        _fmt(analysis.score_breakdown),
    ]
    return ExportSection(title="Risk Analysis", content="\n".join(lines))


def _build_entities_section(analysis: AnalysisResult) -> ExportSection:
    nlp = analysis.nlp_flags or {}
    entities = nlp.get("entities", nlp)
    return ExportSection(
        title="Entities Detected",
        content=_fmt(entities) if entities else "No entities detected.",
    )


def _build_mitre_section(analysis: AnalysisResult) -> ExportSection:
    tactics = analysis.tactics or []
    techniques = analysis.techniques or []
    lines = [
        "Tactics:",
        *( (f"  - {t}" for t in tactics) if tactics else ["  (none)"] ),
        "",
        "Techniques:",
        *( (f"  - {t}" for t in techniques) if techniques else ["  (none)"] ),
    ]
    return ExportSection(title="MITRE ATT&CK Mapping", content="\n".join(lines))


def _build_notes_section(notes: list[AnalystNote]) -> ExportSection:
    if not notes:
        return ExportSection(title="Analyst Notes", content="No analyst notes.")
    blocks: list[str] = []
    for n in notes:
        ts = n.created_at.isoformat() if n.created_at else "N/A"
        blocks.append(f"[{ts}] {n.author}:\n{n.note}")
    return ExportSection(title="Analyst Notes", content="\n\n".join(blocks))


def _build_audit_section(logs: list[AuditLog]) -> ExportSection:
    if not logs:
        return ExportSection(title="Audit Trail", content="No audit log entries.")
    lines: list[str] = []
    for entry in logs:
        ts = entry.timestamp.isoformat() if entry.timestamp else "N/A"
        detail = f" – {entry.details}" if entry.details else ""
        lines.append(f"[{ts}] {entry.analyst}: {entry.action}{detail}")
    return ExportSection(title="Audit Trail", content="\n".join(lines))


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/{content_id}/pdf",
    summary="Export content item as structured PDF payload",
)
@_limiter.limit("10/hour")
async def export_content_pdf(
    request: Request,
    content_id: uuid.UUID,
    source_reliability_rating: ReliabilityRating = ReliabilityRating.C_2,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_role([Role.ANALYST])),
) -> Response:
    """
    Build a structured export payload for a content item that the frontend
    can use to generate a client-side PDF.  Includes content overview, risk
    analysis, entities, MITRE mapping, analyst notes, and audit trail.
    """

    # 1. Fetch the content item
    item = await db.get(ContentItem, content_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content item not found.",
        )

    # 2. Latest analysis (most recent by analyzed_at)
    analysis_result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.content_id == content_id)
        .order_by(AnalysisResult.analyzed_at.desc())
        .limit(1)
    )
    analysis: AnalysisResult | None = analysis_result.scalars().first()

    # 3. All analyst notes
    notes_result = await db.execute(
        select(AnalystNote)
        .where(AnalystNote.content_id == content_id)
        .order_by(AnalystNote.created_at.desc())
    )
    notes: list[AnalystNote] = list(notes_result.scalars().all())

    # 4. All audit log entries
    audit_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.content_id == content_id)
        .order_by(AuditLog.timestamp.asc())
    )
    audit_logs: list[AuditLog] = list(audit_result.scalars().all())

    # 5. Compile data for PDF generator
    case_id = f"CASE-{content_id.hex[:8].upper()}"
    report_ref = f"REF-{int(datetime.now(timezone.utc).timestamp())}"
    
    entities = []
    if analysis and analysis.nlp_flags:
        nlp_entities = analysis.nlp_flags.get("entities", [])
        if isinstance(nlp_entities, list):
            for e in nlp_entities:
                if isinstance(e, dict):
                    entities.append({
                        "type": e.get("type", "Unknown"),
                        "value": e.get("value", "Unknown"),
                        "confidence": e.get("confidence", 0.0)
                    })
    
    # Format timeline
    timeline = []
    timeline.append({
        "timestamp": item.collected_at.isoformat() if item.collected_at else "Unknown",
        "description": f"Content collected from {item.source.value if hasattr(item.source, 'value') else item.source}"
    })
    for log in audit_logs:
        timeline.append({
            "timestamp": log.timestamp.isoformat() if log.timestamp else "Unknown",
            "description": f"{log.analyst} performed {log.action}"
        })
        
    formatted_notes = []
    for note in notes:
        formatted_notes.append({
            "author": note.author,
            "timestamp": note.created_at.isoformat() if note.created_at else "Unknown",
            "text": note.note
        })
        
    recommended_actions = []
    if analysis and "recommended_actions" in analysis.score_breakdown:
        recommended_actions = analysis.score_breakdown.get("recommended_actions", [])
        
    report_data = {
        "case_id": case_id,
        "report_ref": report_ref,
        "report_version": f"1.{len(audit_logs)}",  # Basic versioning logic
        "source": str(item.source.value if hasattr(item.source, 'value') else item.source),
        "source_status": str(item.status),
        "risk_score": analysis.risk_score if analysis else 0.0,
        "severity": str(analysis.risk_label.value if hasattr(analysis.risk_label, 'value') else analysis.risk_label) if analysis else "UNKNOWN",
        "threat_category": "TBD",
        "original_message": item.raw_text,
        "content_hash": item.content_hash,
        "collected_at": item.collected_at.isoformat() if item.collected_at else "Unknown",
        "author_handle": item.author_handle or "Unknown",
        "source_url": item.source_id,
        "extracted_entities": entities,
        "related_channels": [],
        "media_urls": item.media_urls if item.media_urls else [],
        "recommended_actions": recommended_actions,
        "timeline": timeline,
        "analyst_notes": formatted_notes,
        "source_reliability_rating": source_reliability_rating or "C / 2",
        "model_version": analysis.model_version if analysis else "N/A",
        "data_confidence": analysis.data_confidence if analysis else "N/A",
        "tactics": analysis.tactics if analysis and analysis.tactics else [],
        "techniques": analysis.techniques if analysis and analysis.techniques else []
    }

    # 6. Generate PDF
    from app.services.pdf_report_generator import EvidenceReportGenerator
    generator = EvidenceReportGenerator()
    pdf_bytes = generator.generate_bytes(report_data)

    # 7. Persist to database
    # Find active alert if any
    alert_result = await db.execute(
        select(Alert).where(Alert.content_id == content_id, Alert.resolved == False).limit(1)
    )
    active_alert = alert_result.scalars().first()
    
    report = EvidenceReport(
        case_number=case_id,
        report_ref=report_ref,
        description=f"Auto-generated PDF report for content {content_id}",
        content_id=content_id,
        alert_id=active_alert.id if active_alert else None,
        source_reliability_rating=source_reliability_rating or "C / 2",
        generated_by=principal.subject,
        evidence_data=report_data,
        status="generated",
    )
    db.add(report)

    audit = AuditLog(
        content_id=content_id,
        analyst=principal.subject,
        action="REPORT_EXPORTED",
        details={"report_ref": report_ref}
    )
    db.add(audit)

    await db.commit()

    from fastapi import Response
    return Response(
        content=pdf_bytes, 
        media_type="application/pdf", 
        headers={
            "Content-Disposition": f'attachment; filename="evidence_report_{case_id}.pdf"',
            "X-Report-Id": str(report.id)
        }
    )


@router.get(
    "/reports",
    summary="List generated evidence reports",
)
async def list_reports(
    content_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> list[dict]:
    query = select(EvidenceReport).order_by(EvidenceReport.created_at.desc())
    if content_id:
        query = query.where(EvidenceReport.content_id == content_id)
        
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    reports = result.scalars().all()
    
    return [
        {
            "id": str(r.id),
            "content_id": str(r.content_id),
            "case_number": r.case_number,
            "report_ref": r.report_ref,
            "generated_by": r.generated_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "status": r.status,
            "source_reliability_rating": r.source_reliability_rating,
        }
        for r in reports
    ]


@router.get(
    "/reports/{report_id}",
    summary="Get report metadata",
)
async def get_report_metadata(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> dict:
    report = await db.get(EvidenceReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    audit = AuditLog(
        content_id=report.content_id,
        analyst=principal.subject,
        action="REPORT_VIEWED",
        details={"report_ref": report.report_ref}
    )
    db.add(audit)
    await db.commit()
        
    return {
        "id": str(report.id),
        "content_id": str(report.content_id),
        "alert_id": str(report.alert_id) if report.alert_id else None,
        "case_number": report.case_number,
        "report_ref": report.report_ref,
        "description": report.description,
        "generated_by": report.generated_by,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "status": report.status,
        "source_reliability_rating": report.source_reliability_rating,
        "evidence_data": report.evidence_data
    }


