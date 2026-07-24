"""
knowledge_graph.py — DocTel Knowledge Graph API Router

Exposes the enterprise knowledge graph as a navigable API.
Supports node/edge CRUD, graph discovery, path finding, and exploration.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.routers.deps import (
    Depends,
    get_db,
    User,
    get_current_user,
)

from app.services.knowledge_graph_service import (
    KnowledgeGraphService,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge-graph", tags=["knowledge-graph"])


# ── Node Endpoints ──────────────────────────────────────────────────────────


@router.get("/nodes")
async def search_nodes(
    query: str = Query("", description="Search query"),
    node_type: Optional[str] = Query(None, description="Filter by node type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search knowledge graph nodes."""
    service = KnowledgeGraphService(db)
    nodes, total = await service.search_nodes(
        query=query, node_type=node_type, limit=limit, offset=offset
    )
    return {"nodes": [n.to_dict() for n in nodes], "total": total}


@router.get("/nodes/{node_id}")
async def get_node(
    node_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single graph node by its node_id."""
    service = KnowledgeGraphService(db)
    node = await service.get_node(node_id)
    if not node:
        return JSONResponse(status_code=404, content={"error": "node_not_found"})
    return node.to_dict()


@router.post("/nodes")
async def create_node(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a knowledge graph node."""
    service = KnowledgeGraphService(db)
    node = await service.create_node(
        node_id=payload.get("node_id", payload.get("label", "unknown")),
        node_type=payload.get("node_type", "entity"),
        label=payload.get("label", "Unknown"),
        description=payload.get("description", ""),
        metadata=payload.get("metadata"),
        source_document_id=payload.get("source_document_id"),
        source_project_id=payload.get("source_project_id"),
        importance=payload.get("importance", 0.5),
    )
    return node.to_dict()


@router.delete("/nodes/{node_id}")
async def delete_node(
    node_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a graph node."""
    service = KnowledgeGraphService(db)
    success = await service.delete_node(node_id)
    if not success:
        return JSONResponse(status_code=404, content={"error": "node_not_found"})
    return {"status": "deleted"}


# ── Edge Endpoints ──────────────────────────────────────────────────────────


@router.get("/nodes/{node_id}/edges")
async def get_node_edges(
    node_id: str,
    direction: str = Query("both", regex="^(outgoing|incoming|both)$"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get edges for a graph node."""
    service = KnowledgeGraphService(db)
    edges = await service.get_edges(node_id, direction=direction, limit=limit)
    return {"edges": edges, "total": len(edges)}


@router.post("/edges")
async def create_edge(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a directed edge between two nodes."""
    source = payload.get("source_node_id")
    target = payload.get("target_node_id")
    relation = payload.get("relation", "related_to")
    if not source or not target:
        return JSONResponse(status_code=400, content={"error": "source_node_id and target_node_id required"})

    service = KnowledgeGraphService(db)
    success = await service.create_edge(
        source_node_id=source,
        target_node_id=target,
        relation=relation,
        weight=payload.get("weight", 1.0),
        source_document_id=payload.get("source_document_id"),
        metadata=payload.get("metadata"),
    )
    if not success:
        return JSONResponse(status_code=400, content={"error": "edge_creation_failed"})
    return {"status": "created"}


# ── Discovery Endpoints ─────────────────────────────────────────────────────


@router.get("/discover/by-entity")
async def discover_by_entity(
    entity: str = Query("", description="Entity name to search for"),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Find all graph entities and assets related to a named entity.

    Example: "CRM" → finds policies, workflows, meetings, dashboards, reports.
    """
    if not entity:
        return {"related_entities": [], "related_assets": [], "total": 0}

    service = KnowledgeGraphService(db)

    related_entities = await service.find_related_entities(entity, limit=limit)
    related_assets = await service.find_assets_by_entity(entity, limit=limit)

    return {
        "entity": entity,
        "related_entities": related_entities,
        "related_assets": related_assets,
        "total_entities": len(related_entities),
        "total_assets": len(related_assets),
    }


@router.get("/discover/by-question")
async def discover_by_question(
    question: str = Query("", description="Natural language question"),
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Discover graph knowledge relevant to a user question.

    Called by the orchestrator before executing tools.
    Returns matched nodes, discovered entities, and asset types.
    """
    if not question:
        return {"matched_nodes": [], "graph_summary": "No question provided"}

    service = KnowledgeGraphService(db)
    result = await service.discover_for_question(question, limit=limit)
    return result


# ── Path Endpoints ──────────────────────────────────────────────────────────


@router.get("/path")
async def find_path(
    source: str = Query(..., description="Source node ID"),
    target: str = Query(..., description="Target node ID"),
    max_depth: int = Query(5, ge=1, le=10),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Find dependency/relationship paths between two graph nodes."""
    service = KnowledgeGraphService(db)
    paths = await service.find_dependency_path(source, target, max_depth=max_depth)
    return {"paths": paths, "total_paths": len(paths)}


# ── Explore Endpoint ────────────────────────────────────────────────────────


@router.get("/explore")
async def explore_graph(
    query: str = Query("", description="Search query to focus exploration"),
    node_type: Optional[str] = Query(None, description="Filter by node type"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explore the knowledge graph — returns nodes + edges for visualization.

    The response format is designed for rendering with D3.js, vis.js, or
    any force-directed graph library:
      { nodes: [...], edges: [...], total_nodes, total_edges_shown }
    """
    service = KnowledgeGraphService(db)
    result = await service.explore_graph(
        query=query, node_type=node_type, limit=limit
    )
    return result


# ── Stats Endpoints ─────────────────────────────────────────────────────────


@router.get("/stats")
async def graph_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get overall knowledge graph statistics."""
    service = KnowledgeGraphService(db)
    stats = await service.get_graph_stats()
    return stats


# ── Rebuild Endpoint ────────────────────────────────────────────────────────


@router.post("/rebuild/doc/{document_id}")
async def rebuild_document_graph(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rebuild graph nodes and edges for a specific document from its analysis."""
    from app.db.models import Document as DocModel, DocAnalysis

    result = await db.execute(
        select(DocModel).where(DocModel.id == uuid.UUID(document_id))
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return JSONResponse(status_code=404, content={"error": "document_not_found"})

    analysis_result = await db.execute(
        select(DocAnalysis).where(DocAnalysis.document_id == doc.id)
    )
    analysis = analysis_result.scalar_one_or_none()

    service = KnowledgeGraphService(db)
    await service.add_document_to_graph(
        document_id=str(doc.id),
        document_title=doc.title or doc.filename or "",
        doc_type=doc.doc_type or "",
        project_id=doc.project_id,
        analysis=analysis,
    )
    return {"status": "graph_updated", "document_id": document_id}


