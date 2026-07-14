"""
audit_service.py — Interaction Audit Trail Logging

Writes entries to the ``interaction_audits`` table (Pillar 20) for
document-level actions such as viewing, downloading, and previewing chunks.

Usage::

    await log_interaction(
        db=db,
        user_id=user.id,
        action_type="download_document",
        resource_type="document",
        resource_id=f"doc_{doc.id}",
        details={"filename": doc.filename, "project_id": doc.project_id},
        ip_address=request.client.host if request else None,
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enterprise_models import InteractionAudit

logger = logging.getLogger(__name__)

# ── Known action types ─────────────────────────────────────────────────────

ACTION_TYPES = {
    "view_document",
    "download_document",
    "preview_document",
    "open_document",
    "search_documents",
    "list_documents",
}


async def log_interaction(
    db: AsyncSession,
    user_id: int | None,
    action_type: str,
    resource_type: str = "document",
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> InteractionAudit:
    """Persist an action to the interaction audit trail.

    Args:
        db: Active database session.
        user_id: The acting user's ID (may be None for anonymous actions).
        action_type: One of ``ACTION_TYPES`` (e.g. ``"download_document"``).
        resource_type: Type of resource being accessed (default ``"document"``).
        resource_id: String identifier of the resource (e.g. ``"doc_42"``).
        details: Arbitrary JSON-serialisable dict for extra context.
        ip_address: Client IP address if available.

    Returns:
        The created ``InteractionAudit`` ORM instance.
    """
    # Map action_type → a human-readable prompt-like summary
    prompt_text = _build_prompt_text(action_type, resource_type, resource_id, details)

    entry = InteractionAudit(
        user_id=user_id,
        prompt_text=prompt_text,
        provider_id="doctel.rbac",
        model_id="rbac.policy.v1",
        vendor="internal",
        response_text="",
        reasoning_text="",
        duration_ms=0,
        tokens_input=0,
        tokens_output=0,
        tokens_total=0,
    )

    # Store action metadata in citations_json as a lightweight payload
    payload: dict[str, Any] = {
        "action": action_type,
        "resourceType": resource_type,
        "resourceId": resource_id,
        "ipAddress": ip_address,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if details:
        payload["details"] = details
    entry.citations_json = __import__("json").dumps(payload, ensure_ascii=False)

    db.add(entry)
    await db.commit()
    logger.debug("Audit logged: action=%s resource=%s user=%s", action_type, resource_id, user_id)
    return entry


def _build_prompt_text(
    action_type: str,
    resource_type: str,
    resource_id: str | None,
    details: dict[str, Any] | None,
) -> str:
    """Build a human-readable summary string."""
    rid = resource_id or "unknown"
    base = f"{action_type} on {resource_type} {rid}"
    if details and "filename" in details:
        base += f" ({details['filename']})"
    return base
