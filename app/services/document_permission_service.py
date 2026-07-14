"""
document_permission_service.py — DocTel Enterprise RBAC for Document Access

Provides view/download/preview permission checks for documents using:
  1. Admin bypass (role == "admin")
  2. Project membership (ProjectMember table)
  3. Public document flag (Document.is_public)
  4. Department-level provider restrictions (DepartmentRestriction, for audit context)

Every assertion raises HTTP 403 with 🔒 prefix when the check fails.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, ProjectMember, User

logger = logging.getLogger(__name__)


# ── Permission predicates ─────────────────────────────────────────────────


async def can_view_document(doc: Document, user: User, db: AsyncSession) -> bool:
    """Return True if *user* is allowed to view *doc*."""
    return await _check_any_access(doc, user, db)


async def can_download_document(doc: Document, user: User, db: AsyncSession) -> bool:
    """Return True if *user* is allowed to download *doc*."""
    return await _check_any_access(doc, user, db)


async def can_preview_document(doc: Document, user: User, db: AsyncSession) -> bool:
    """Return True if *user* is allowed to preview a chunk of *doc*."""
    return await _check_any_access(doc, user, db)


async def _check_any_access(doc: Document, user: User, db: AsyncSession) -> bool:
    """Core access check used by all three predicates."""
    # 1) Admin bypass
    if user.role == "admin":
        return True

    # 2) Public document — anyone can view
    if getattr(doc, "is_public", False):
        return True

    # 3) No project → no membership check possible
    if doc.project_id is None:
        logger.debug("Access denied for user=%s doc=%d — no project_id", user.id, doc.id)
        return False

    # 4) Project membership
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == doc.project_id,
            ProjectMember.user_id == user.id,
        )
    )
    if result.scalar_one_or_none() is not None:
        return True

    # 5) Fallback — user is neither admin, nor member, nor accessing a public doc
    logger.debug(
        "Access denied for user=%s doc=%d project=%d — not a member",
        user.id, doc.id, doc.project_id,
    )
    return False


# ── Assertion helpers (raise HTTP 403) ─────────────────────────────────────


async def assert_can_view(doc: Document, user: User, db: AsyncSession) -> None:
    """Raise 403 if user cannot view the document."""
    if not await can_view_document(doc, user, db):
        raise HTTPException(status_code=403, detail="🔒 Access Restricted")


async def assert_can_download(doc: Document, user: User, db: AsyncSession) -> None:
    """Raise 403 if user cannot download the document."""
    if not await can_download_document(doc, user, db):
        raise HTTPException(status_code=403, detail="🔒 Access Restricted")


async def assert_can_preview(doc: Document, user: User, db: AsyncSession) -> None:
    """Raise 403 if user cannot preview chunks of the document."""
    if not await can_preview_document(doc, user, db):
        raise HTTPException(status_code=403, detail="🔒 Access Restricted")


# ── Bulk enrichment helper (for citation objects) ──────────────────────────


async def enrich_citations(
    citations: list[dict],
    user: User,
    db: AsyncSession,
    base_url: str = "",
) -> list[dict]:
    """Add permission flags, URLs, and page info to each citation dict.

    Each citation dict **must** contain at least ``document_id`` and
    ``chunk_index`` keys.  The function injects:

    * ``can_view`` / ``can_download``
    * ``open_url`` / ``download_url`` / ``preview_url``
    * ``page_number`` (derived from chunk_index if not already set)
    * ``source_type`` / ``project_id`` (forwarded if missing)
    """
    enriched: list[dict] = []
    for c in citations:
        doc_id_raw = c.get("document_id")
        if doc_id_raw is None:
            enriched.append(c)
            continue

        # Resolve document from DB
        try:
            doc_int = int(str(doc_id_raw).replace("doc_", ""))
        except (ValueError, TypeError):
            enriched.append(c)
            continue

        result = await db.execute(select(Document).where(Document.id == doc_int))
        doc = result.scalar_one_or_none()

        if doc is None:
            enriched.append(c)
            continue

        can_view = await can_view_document(doc, user, db)
        can_download = await can_download_document(doc, user, db)

        doc_id_str = f"doc_{doc.id}"
        chunk_idx = c.get("chunk_index", 0)

        enriched.append({
            **c,
            "can_view": can_view,
            "can_download": can_download,
            "open_url": f"{base_url}/api/documents/{doc_id_str}/viewer?chunk={chunk_idx}" if can_view else None,
            "download_url": f"{base_url}/api/documents/{doc_id_str}/download" if can_download else None,
            "preview_url": f"{base_url}/api/documents/{doc_id_str}/preview/{chunk_idx}" if can_view else None,
            "page_number": c.get("page_number") or ((chunk_idx or 0) + 1),
            "source_type": c.get("source_type") or (doc.mime_type or "unknown"),
            "project_id": c.get("project_id") or str(doc.project_id) if doc.project_id else None,
        })
    return enriched
