from app.domain.enums import Role
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, cast, String
from pydantic import BaseModel

from app.api.deps import get_db, require_dashboard_principal, require_role
from app.schemas.auth import Principal
from app.models.content import ContentItem
from app.models.analysis import AnalysisResult


class SearchResult(BaseModel):
    id: str
    type: str  # 'content' | 'entity' | 'author'
    title: str
    subtitle: str
    url: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    query: str


router = APIRouter()


@router.get("", response_model=SearchResponse)
async def global_search(
    q: str = Query(..., min_length=2, description="Search query (minimum 2 characters)"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> SearchResponse:
    search_term = f"%{q}%"

    # --- content + author matches ---
    content_stmt = (
        select(ContentItem)
        .where(
            ContentItem.deleted_at.is_(None),
            or_(
                ContentItem.raw_text.ilike(search_term),
                ContentItem.author_handle.ilike(search_term),
            ),
        )
        .order_by(ContentItem.collected_at.desc())
        .limit(limit)
    )
    content_rows = (await db.execute(content_stmt)).scalars().all()

    # --- entity matches (JSONB text search on nlp_flags) ---
    entity_stmt = (
        select(AnalysisResult, ContentItem)
        .join(ContentItem, AnalysisResult.content_id == ContentItem.id)
        .where(
            ContentItem.deleted_at.is_(None),
            cast(AnalysisResult.nlp_flags, String).ilike(search_term),
        )
        .order_by(ContentItem.collected_at.desc())
        .limit(limit)
    )
    entity_rows = (await db.execute(entity_stmt)).all()

    seen_ids: set[uuid.UUID] = set()
    results: list[SearchResult] = []

    # Build results from content / author matches
    for item in content_rows:
        if item.id in seen_ids:
            continue
        seen_ids.add(item.id)

        if item.author_handle and q.lower() in item.author_handle.lower():
            results.append(
                SearchResult(
                    id=str(item.id),
                    type="author",
                    title=item.author_handle,
                    subtitle=item.source.value if item.source else "",
                    url=f"/investigation/{item.id}",
                )
            )

        if item.raw_text and q.lower() in item.raw_text.lower():
            results.append(
                SearchResult(
                    id=str(item.id),
                    type="content",
                    title=item.raw_text[:100],
                    subtitle=item.source.value if item.source else "",
                    url=f"/investigation/{item.id}",
                )
            )

    # Build results from entity matches
    for analysis, content_item in entity_rows:
        if content_item.id in seen_ids:
            continue
        seen_ids.add(content_item.id)

        # Try to extract a meaningful entity preview from nlp_flags
        preview = _extract_entity_preview(analysis.nlp_flags, q)
        results.append(
            SearchResult(
                id=str(content_item.id),
                type="entity",
                title=preview,
                subtitle="Entity match",
                url=f"/investigation/{content_item.id}",
            )
        )

    # Enforce global limit
    results = results[:limit]

    return SearchResponse(results=results, total=len(results), query=q)


def _extract_entity_preview(nlp_flags: dict, query: str) -> str:
    """Walk the entities sub-dict inside nlp_flags and return the first
    value that matches *query* (case-insensitive).  Falls back to a
    generic label when nothing concrete is found."""
    entities = nlp_flags.get("entities", {})
    q_lower = query.lower()
    for _category, values in entities.items():
        if isinstance(values, list):
            for v in values:
                if isinstance(v, str) and q_lower in v.lower():
                    return v
    return f"Entity match: {query}"
