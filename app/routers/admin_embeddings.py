"""
admin_embeddings.py — Embedding Governance Admin API

Provides REST endpoints for:
- Embedding health dashboard (counts by status)
- Listing documents needing re-embed (mismatches)
- Triggering single-document re-embed
- Triggering bulk re-embed of mismatched documents
- Triggering force re-embed of ALL documents
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.routers.deps import get_db, require_role
from app.db.models import Document, EMBEDDING_VERSION
from app.services.reembedding_service import (
    reembed_document,
    reembed_mismatched_documents,
    reembed_all_documents,
)
from app.services.embedding_service import (
    resolve_embedding_model,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/embeddings", tags=["admin-embeddings"])


# ═══════════════════════════════════════════════════════════════════════════════
# Dashboard — embedding health overview
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/status")
async def embedding_dashboard(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Return embedding health dashboard with document counts by status."""
    # Total documents
    total_result = await db.execute(sa_func.count(Document.id))
    total_docs = total_result.scalar()

    # Status breakdown
    embedded_result = await db.execute(
        select(sa_func.count(Document.id)).where(Document.embedding_provider.isnot(None))
    )
    embedded = embedded_result.scalar()

    pending_result = await db.execute(
        select(sa_func.count(Document.id)).where(Document.embedded_at.is_(None))
    )
    pending = pending_result.scalar()

    version_mismatch_result = await db.execute(
        select(sa_func.count(Document.id)).where(
            Document.embedded_at.isnot(None),
            Document.embedding_version != EMBEDDING_VERSION,
        )
    )
    version_mismatch = version_mismatch_result.scalar()

    # Provider/model mismatch vs TaskMapping
    tm_config = await resolve_embedding_model(db)
    configured_provider = tm_config["provider_name"] if tm_config else None
    configured_model = tm_config["model_id"] if tm_config else None
    provider_model_mismatch = 0

    if configured_provider and configured_model:
        mismatch_result = await db.execute(
            select(sa_func.count(Document.id)).where(
                Document.embedded_at.isnot(None),
                (
                    (Document.embedding_provider != configured_provider)
                    | (Document.embedding_model != configured_model)
                ),
            )
        )
        provider_model_mismatch = mismatch_result.scalar()

    return {
        "total_documents": total_docs or 0,
        "embedded": embedded or 0,
        "pending": pending or 0,
        "version_mismatch": version_mismatch or 0,
        "provider_model_mismatch": provider_model_mismatch or 0,
        "configured_provider": configured_provider,
        "configured_model": configured_model,
        "embedding_version": EMBEDDING_VERSION,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# List documents needing re-embed
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/mismatches")
async def list_embedding_mismatches(
    project_id: Optional[int] = Query(None, description="Filter by project"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """List documents whose embedding provider/model differs from TaskMapping."""
    tm_config = await resolve_embedding_model(db)
    if not tm_config:
        return {"documents": [], "total": 0, "configured": None}

    configured_provider = tm_config["provider_name"]
    configured_model = tm_config["model_id"]

    conditions = [
        (Document.embedding_provider != configured_provider)
        | (Document.embedding_model != configured_model)
        | (Document.embedding_version != EMBEDDING_VERSION)
        | (Document.embedded_at.is_(None))
    ]
    if project_id:
        conditions.append(Document.project_id == project_id)

    result = await db.execute(
        select(
            Document.id,
            Document.filename,
            Document.project_id,
            Document.embedding_provider,
            Document.embedding_model,
            Document.embedding_version,
            Document.embedded_at,
        ).where(*conditions)
    )
    rows = result.all()

    docs = [
        {
            "id": r.id,
            "filename": r.filename,
            "project_id": r.project_id,
            "current_provider": r.embedding_provider,
            "current_model": r.embedding_model,
            "current_version": r.embedding_version,
            "embedded_at": r.embedded_at.isoformat() if r.embedded_at else None,
            "needs_reembed": True,
        }
        for r in rows
    ]

    return {
        "documents": docs,
        "total": len(docs),
        "configured": {
            "provider": configured_provider,
            "model": configured_model,
            "version": EMBEDDING_VERSION,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Single-document re-embed
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/reembed/{doc_id}")
async def trigger_reembed_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Re-embed a single document using the current TaskMapping model."""
    result = await reembed_document(db, doc_id=doc_id)
    if not result["success"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=result.get("error", "Re-embed failed"))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Bulk re-embed — mismatched documents only
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/reembed-mismatched")
async def trigger_reembed_mismatched(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Re-embed all documents whose provider/model differs from TaskMapping."""
    result = await reembed_mismatched_documents(db)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Force re-embed — ALL documents
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/reembed-all")
async def trigger_reembed_all(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Force re-embedding of ALL documents, regardless of current state."""
    result = await reembed_all_documents(db)
    return result
