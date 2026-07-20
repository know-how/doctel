"""
DocTel sync router.

Endpoints for model router status, SSE event stream (cross-platform sync),
polling fallback for mobile clients, and logout with SSE broadcast.
"""

import asyncio

from fastapi import APIRouter

from app.routers.deps import (
    Depends,
    Request,
    User,
    AsyncSession,
    get_db,
    get_current_user,
    JSONResponse,
    StreamingResponse,
    logger,
    _sse_clients,
    _sse_poll_buffer,
    _sse_poll_lock,
    _sse_broadcast,
    _sse_generator,
    auth_service,
)

router = APIRouter(tags=["sync"])


# ─────────────────────────────────────────────────────────────────────────────
# Model Router Status API
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/router/status")
async def api_router_status(user: User = Depends(get_current_user)):
    """Return which intelligence tiers are currently available."""
    from app.services.model_router import get_router_status
    return get_router_status()


# ─────────────────────────────────────────────────────────────────────────────
# SSE – Sync Event Stream (cross-platform logout + training events)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/sync/events")
async def api_sync_events(user: User = Depends(get_current_user)):
    """
    Server-Sent Events stream for cross-platform sync.
    Clients receive events like:
      {"event": "session.logout", "data": {}}
      {"event": "training.complete", "data": {"adapter_id": "..."}}
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    _sse_clients.add(queue)
    return StreamingResponse(
        _sse_generator(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/sync/poll")
async def api_sync_poll(user: User = Depends(get_current_user)):
    """Polling endpoint for mobile clients that cannot use SSE."""
    async with _sse_poll_lock:
        if _sse_poll_buffer:
            evt = _sse_poll_buffer.pop(0)
            return JSONResponse(evt)
    return JSONResponse({"event": None})


# ─────────────────────────────────────────────────────────────────────────────
# Logout – revoke token + broadcast session.logout to SSE clients
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/auth/logout")
async def auth_logout_with_broadcast(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Log out the current user: invalidate session token and broadcast logout
    event to all connected SSE clients (web + mobile) for cross-platform sync.
    Also cancels any pending ingestion jobs uploaded by this user and resets
    the model-selection cache.
    """
    # Revoke the bearer token from the in-memory session store
    try:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if token and not token.startswith("local-"):
                await auth_service.revoke_token(token)
    except Exception:
        pass

    # Cancel any queued ingestion jobs that belong to this user
    try:
        from app.services.job_poller import cancel_job
        from sqlalchemy import select as _select
        from app.db.models import Document as _Document
        pending_result = await db.execute(
            _select(_Document.id).where(
                _Document.uploaded_by_user_id == user.id,
                _Document.status.in_(["uploaded", "ingesting"]),
            )
        )
        pending_ids = [row[0] for row in pending_result.all()]
        for pid in pending_ids:
            await cancel_job(document_id=pid, owner_id=user.id)
    except Exception:
        pass

    # Reset model-selection cache so next user starts fresh
    try:
        from app.services.model_router import force_select
        force_select(None)
    except Exception:
        pass

    # Broadcast to all SSE subscribers (web + mobile)
    await _sse_broadcast("session.logout", {"user_id": user.id, "ec_number": user.ec_number or ""})

    return {"success": True, "broadcast": True}
