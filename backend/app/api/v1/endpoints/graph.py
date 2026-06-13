from app.api.deps import require_role
from app.domain.enums import Role
from app.schemas.auth import Principal
import logging
import asyncio

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.db.neo4j_session import get_neo4j_driver

logger = logging.getLogger(__name__)
router = APIRouter()


class FrontierStatus(BaseModel):
    queued: int
    processing: int
    unexplored: int
    explored: int
    failed: int


class GraphStats(BaseModel):
    nodes: dict[str, int]
    edges: dict[str, int]
    total_nodes: int
    total_edges: int
    frontier: FrontierStatus


class NodeDetail(BaseModel):
    id: str
    type: str
    label: str
    risk_score: float | None = None
    member_count: int | None = None
    status: str | None = None


class EdgeDetail(BaseModel):
    id: str
    source: str
    target: str
    type: str
    count: int | None = 1


class GraphTopology(BaseModel):
    nodes: list[NodeDetail]
    edges: list[EdgeDetail]


@router.get("/stats", response_model=GraphStats)
async def get_graph_stats(
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> GraphStats:
    """Return node/edge counts grouped by label/type and frontier queue status."""
    driver = await get_neo4j_driver()
    nodes: dict[str, int] = {}
    edges: dict[str, int] = {}
    total_nodes = 0
    total_edges = 0

    async with driver.session() as session:
        # Node counts by label
        node_result = await session.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count"
        )
        async for record in node_result:
            label = record["label"]
            count = record["count"]
            if label:
                nodes[label] = count
                total_nodes += count

        # Edge counts by type
        edge_result = await session.run(
            "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count"
        )
        async for record in edge_result:
            rel_type = record["type"]
            count = record["count"]
            if rel_type:
                edges[rel_type] = count
                total_edges += count

        # Frontier status breakdown
        frontier_result = await session.run(
            """
            MATCH (c:Channel)
            RETURN c.status AS status, count(c) AS count
            """
        )
        status_counts: dict[str, int] = {}
        async for record in frontier_result:
            status = record["status"]
            if status:
                status_counts[status] = record["count"]

    frontier = FrontierStatus(
        queued=status_counts.get("queued", 0),
        processing=status_counts.get("processing", 0),
        unexplored=status_counts.get("unexplored", 0),
        explored=status_counts.get("explored", 0),
        failed=status_counts.get("failed", 0),
    )

    return GraphStats(
        nodes=nodes,
        edges=edges,
        total_nodes=total_nodes,
        total_edges=total_edges,
        frontier=frontier,
    )


@router.get("/topology", response_model=GraphTopology)
async def get_graph_topology(
    limit: int = Query(default=200, ge=1, le=1000),
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> GraphTopology:
    """Return specific nodes and edges for rendering the graph visualization."""
    driver = await get_neo4j_driver()
    nodes: list[NodeDetail] = []
    edges: list[EdgeDetail] = []

    async with driver.session() as session:
        # Fetch nodes
        node_query = """
        MATCH (n)
        RETURN 
            elementId(n) AS id,
            labels(n)[0] AS type,
            coalesce(n.username, n.domain, "Unknown") AS label,
            n.risk_score AS risk_score,
            n.member_count AS member_count,
            n.status AS status
        LIMIT $limit
        """
        node_result = await session.run(node_query, limit=limit)
        async for record in node_result:
            nodes.append(NodeDetail(
                id=str(record["id"]),
                type=record["type"] or "Unknown",
                label=str(record["label"]),
                risk_score=record["risk_score"],
                member_count=record["member_count"],
                status=record["status"]
            ))

        # Fetch edges
        edge_query = """
        MATCH (s)-[r]->(t)
        RETURN
            elementId(r) AS id,
            elementId(s) AS source,
            elementId(t) AS target,
            type(r) AS type,
            r.count AS count
        LIMIT $limit
        """
        edge_result = await session.run(edge_query, limit=limit*2)
        async for record in edge_result:
            edges.append(EdgeDetail(
                id=str(record["id"]),
                source=str(record["source"]),
                target=str(record["target"]),
                type=record["type"] or "UNKNOWN",
                count=record["count"] if record["count"] is not None else 1
            ))

    return GraphTopology(nodes=nodes, edges=edges)
