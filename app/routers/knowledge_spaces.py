"""
knowledge_spaces.py — DocTel Knowledge Space API Router

Exposes knowledge spaces as first-class API resources.
Supports CRUD, asset management, knowledge discovery, and stats.
"""

from __future__ import annotations

import logging
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

from app.services.knowledge_space_service import (
    KnowledgeSpaceService,
    search_knowledge_spaces,
    discover_spaces_for_question,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge-spaces", tags=["knowledge-spaces"])


# ── CRUD Endpoints ──────────────────────────────────────────────────────────


@router.get("")
async def list_spaces(
    query: str = Query("", description="Search query"),
    department: Optional[str] = Query(None, description="Filter by department"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List/search knowledge spaces."""
    spaces = await search_knowledge_spaces(
        db, query=query, department=department, limit=limit
    )
    return {"spaces": spaces, "total": len(spaces)}


@router.post("")
async def create_space(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new knowledge space."""
    service = KnowledgeSpaceService(db)
    space = await service.create_space(
        name=payload.get("name", "Untitled Space"),
        description=payload.get("description", ""),
        department=payload.get("department", ""),
        tags=payload.get("tags"),
        owner_id=str(user.id) if user.id else None,
    )
    return _space_to_dict(space, service)


@router.get("/{space_id}")
async def get_space(
    space_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single knowledge space by ID."""
    service = KnowledgeSpaceService(db)
    space = await service.get_space(space_id)
    if not space:
        return JSONResponse(status_code=404, content={"error": "space_not_found"})
    return _space_to_dict(space, service)


@router.patch("/{space_id}")
async def update_space(
    space_id: str,
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a knowledge space."""
    service = KnowledgeSpaceService(db)
    space = await service.update_space(
        space_id=space_id,
        name=payload.get("name"),
        description=payload.get("description"),
        department=payload.get("department"),
        tags=payload.get("tags"),
        is_active=payload.get("is_active"),
    )
    if not space:
        return JSONResponse(status_code=404, content={"error": "space_not_found"})
    return _space_to_dict(space, service)


@router.delete("/{space_id}")
async def delete_space(
    space_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a knowledge space."""
    service = KnowledgeSpaceService(db)
    success = await service.delete_space(space_id)
    if not success:
        return JSONResponse(status_code=404, content={"error": "space_not_found"})
    return {"status": "deleted"}


# ── Asset Management Endpoints ──────────────────────────────────────────────


@router.get("/{space_id}/assets")
async def list_space_assets(
    space_id: str,
    asset_type: Optional[str] = Query(None, description="Filter by asset type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all assets in a knowledge space."""
    service = KnowledgeSpaceService(db)
    assets, total = await service.get_space_assets(
        space_id, asset_type=asset_type, limit=limit, offset=offset
    )
    return {"assets": assets, "total": total}


@router.get("/{space_id}/assets/counts")
async def get_space_asset_counts(
    space_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get asset type counts for a knowledge space."""
    service = KnowledgeSpaceService(db)
    counts = await service.get_space_asset_counts(space_id)
    return counts


@router.post("/{space_id}/assets")
async def add_asset_to_space(
    space_id: str,
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a document as an asset to a knowledge space."""
    document_id = payload.get("document_id")
    if not document_id:
        return JSONResponse(status_code=400, content={"error": "document_id_required"})

    service = KnowledgeSpaceService(db)
    success = await service.add_asset_to_space(space_id, document_id)
    if not success:
        return JSONResponse(status_code=404, content={"error": "add_asset_failed"})
    return {"status": "added"}


@router.delete("/{space_id}/assets/{document_id}")
async def remove_asset_from_space(
    space_id: str,
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a document from a knowledge space."""
    service = KnowledgeSpaceService(db)
    success = await service.remove_asset_from_space(space_id, document_id)
    if not success:
        return JSONResponse(status_code=404, content={"error": "remove_asset_failed"})
    return {"status": "removed"}


# ── Discovery Endpoints ─────────────────────────────────────────────────────


@router.get("/{space_id}/related")
async def related_spaces(
    space_id: str,
    limit: int = Query(5, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Find spaces related to this one via shared topics/entities."""
    service = KnowledgeSpaceService(db)
    related = await service.find_related_spaces(space_id, limit=limit)
    return {"related": related, "total": len(related)}


@router.get("/discover/by-question")
async def discover_by_question(
    question: str = Query("", description="Natural language question"),
    limit: int = Query(5, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Discover knowledge spaces relevant to a user question.

    Called by the orchestrator before building the execution plan.
    Returns spaces with relevance scores and asset type counts.
    """
    results = await discover_spaces_for_question(db, question=question, limit=limit)
    return {"spaces": results, "total": len(results)}


# ── Stats Endpoints ─────────────────────────────────────────────────────────


@router.get("/{space_id}/insights")
async def space_insights(
    space_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get comprehensive insights for a single knowledge space.

    Returns asset counts by type, recent assets, related spaces,
    media breakdown (audio/video/image/csv/document), and metadata.
    """
    service = KnowledgeSpaceService(db)
    insights = await service.get_space_insights(space_id)
    return insights


@router.get("/stats/summary")
async def space_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get overall knowledge space statistics."""
    service = KnowledgeSpaceService(db)
    stats = await service.get_space_stats()
    return stats


# ── Helpers ─────────────────────────────────────────────────────────────────


def _space_to_dict(space, service: KnowledgeSpaceService) -> dict[str, Any]:
    """Convert a Workspace ORM object to a clean dict."""
    meta = service._extract_meta(space.description)
    return {
        "space_id": str(space.id),
        "name": space.name,
        "description": service._strip_meta(space.description),
        "department": meta.get("department", ""),
        "tags": meta.get("tags", []),
        "owner_id": str(space.owner_id) if space.owner_id else None,
        "is_active": space.is_active,
        "created_at": space.created_at.isoformat() if space.created_at else None,
        "updated_at": space.updated_at.isoformat() if space.updated_at else None,
    }
