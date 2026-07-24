"""
knowledge_assets.py — DocTel Knowledge Asset API Router

Exposes knowledge assets as first-class API resources.
Supports CRUD, search, relationships, and knowledge discovery.
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
    logger,
)

from app.services.knowledge_asset_service import (
    KnowledgeAssetService,
    find_related,
    search_knowledge,
    get_asset_count_by_type,
)

router = APIRouter(prefix="/api/knowledge-assets", tags=["knowledge-assets"])


# ── CRUD Endpoints ──────────────────────────────────────────────────────────


@router.get("")
async def list_assets(
    query: str = Query("", description="Search query"),
    asset_type: Optional[str] = Query(None, description="Filter by asset type"),
    department: Optional[str] = Query(None, description="Filter by department"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List/search knowledge assets across all types."""
    service = KnowledgeAssetService(db)
    assets, total = await service.search_assets(
        query=query,
        asset_type=asset_type,
        department=department,
        limit=limit,
        offset=offset,
    )
    return {
        "assets": [a.to_dict() for a in assets],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{asset_id}")
async def get_asset(
    asset_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single knowledge asset by ID."""
    service = KnowledgeAssetService(db)
    asset = await service.get_asset(asset_id)
    if not asset:
        return JSONResponse(status_code=404, content={"error": "asset_not_found"})
    return asset.to_dict()


@router.patch("/{asset_id}")
async def update_asset(
    asset_id: str,
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a knowledge asset's metadata."""
    service = KnowledgeAssetService(db)
    asset = await service.update_asset(
        asset_id=asset_id,
        title=payload.get("title"),
        description=payload.get("description"),
        tags=payload.get("tags"),
        metadata=payload.get("metadata"),
    )
    if not asset:
        return JSONResponse(status_code=404, content={"error": "asset_not_found"})
    return asset.to_dict()


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a knowledge asset."""
    service = KnowledgeAssetService(db)
    success = await service.delete_asset(asset_id)
    if not success:
        return JSONResponse(status_code=404, content={"error": "asset_not_found"})
    return {"status": "deleted"}


# ── Relationship Endpoints ──────────────────────────────────────────────────


@router.post("/{asset_id}/relationships")
async def create_relationship(
    asset_id: str,
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a relationship from this asset to another."""
    target_id = payload.get("target_id")
    relation_type = payload.get("type", "related_to")
    if not target_id:
        return JSONResponse(status_code=400, content={"error": "target_id_required"})

    service = KnowledgeAssetService(db)
    success = await service.create_relationship(
        source_asset_id=asset_id,
        target_asset_id=target_id,
        relation_type=relation_type,
        metadata=payload.get("metadata"),
    )
    if not success:
        return JSONResponse(status_code=404, content={"error": "relationship_failed"})
    return {"status": "created"}


@router.get("/{asset_id}/relationships")
async def get_relationships(
    asset_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all relationships for an asset."""
    service = KnowledgeAssetService(db)
    relationships = await service.get_relationships(asset_id)
    return {"relationships": relationships, "total": len(relationships)}


# ── Discovery Endpoints ─────────────────────────────────────────────────────


@router.get("/{asset_id}/related")
async def related_assets(
    asset_id: str,
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Find assets related to this one via entity/topic overlap."""
    related = await find_related(db, asset_id, limit=limit)
    return {"related": related, "total": len(related)}


@router.get("/stats/by-type")
async def asset_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get knowledge asset counts grouped by type."""
    counts = await get_asset_count_by_type(db)
    return {"counts": counts, "total": sum(counts.values())}


# ── Discovery Search ────────────────────────────────────────────────────────


@router.get("/discover/explore")
async def explore_knowledge(
    query: str = Query("", description="Discovery query"),
    asset_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explore knowledge assets — unified search for the Knowledge Discovery intent."""
    result = await search_knowledge(
        db, query=query, asset_type=asset_type, limit=limit
    )
    return result
