"""Health check, readiness, metrics, and WebSocket health endpoints."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.routers.deps import (
    BasicResponse,
    logger,
    settings,
    load_model_cache,
    update_installed_models,
    _is_generation_model,
    _is_embedding_model,
    AsyncSession,
    Depends,
    get_db,
    select,
    Project,
    _metrics,
)
from app.db.database import verify_database_health, engine

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=BasicResponse)
async def api_health_app():
    return BasicResponse(ok=True)


@router.get("/healthz", response_model=BasicResponse)
async def healthz():
    """Legacy health endpoint used by frontend for connection checks."""
    return BasicResponse(ok=True)


@router.get("/health/database")
async def health_database():
    """Return database connection health status."""
    driver = settings.db_url.split("://")[0] if "://" in settings.db_url else settings.db_url
    try:
        health = await verify_database_health()
        pool = engine.pool
        pool_name = pool.__class__.__name__ if pool else "unknown"
        return {
            "connected": health.connected,
            "driver": driver,
            "pool": pool_name,
            "healthy": health.healthy,
            "tables_exist": health.tables_exist,
            "latency_ms": health.latency_ms,
            "migrations_complete": health.migrations_complete,
            "error": health.error,
        }
    except Exception as e:
        return {
            "connected": False,
            "driver": driver,
            "pool": "unknown",
            "healthy": False,
            "error": str(e),
        }


@router.get("/api/health/ollama")
async def api_health_ollama():
    """Return Ollama health status with model list. Returns dict directly to avoid schema mismatch."""
    from app.utils.ollama_client import ollama
    try:
        models = await ollama.list_models()
        update_installed_models(models)
    except Exception:
        cache = load_model_cache()
        return {
            "ok": False,
            "reason": "unreachable",
            "hint": "Start Ollama (ollama serve) and retry.",
            "models": [],
            "installed": cache.get("installed") or [],
        }
    present = set(models)
    return {
        "ok": True,
        "models": models,
        "installed": models,
        "available": list(settings.available_models or []),
        "present": list(present),
    }


# ── Simple health / liveness ────────────────────────────────────────────────


@router.get("/healthz")
async def health():
    return {"status": "ok"}


@router.get("/api/health/detailed")
async def api_health_detailed():
    """
    Detailed health check that reports the status of:
    - Backend API (this server)
    - Ollama (local LLM service)
    - External AI services (Gemini, DeepSeek, etc.)

    Returns specific error information to help diagnose connection issues.
    """
    status = {
        "backend": {"ok": True, "status": "running"},
        "ollama": {"ok": False, "status": "unknown", "error": None},
        "external_services": {},
    }

    # Check Ollama (local models) - with defensive imports
    try:
        from app.utils.ollama_client import ollama
        models = await ollama.list_models()
        status["ollama"] = {
            "ok": True,
            "status": "connected",
            "models_count": len(models),
        }
    except Exception as e:
        status["ollama"] = {
            "ok": False,
            "status": "unreachable",
            "error": "Ollama service is not running. Start it with 'ollama serve'",
            "hint": "Start Ollama (ollama serve) and retry.",
        }

    # Check external services (only report if configured) - with defensive imports
    try:
        from app.services.gemini_service import is_configured as gemini_configured
        if gemini_configured():
            status["external_services"]["gemini"] = {"configured": True, "type": "cloud"}
    except Exception:
        pass

    try:
        from app.services.deepseek_service import is_configured as deepseek_configured
        if deepseek_configured():
            status["external_services"]["deepseek"] = {"configured": True, "type": "cloud"}
    except Exception:
        pass

    try:
        from app.services.opencode_zen_service import is_configured as zen_configured
        if zen_configured():
            status["external_services"]["opencode_zen"] = {"configured": True, "type": "cloud"}
    except Exception:
        pass

    try:
        from app.services.huggingface_service import is_configured as hf_configured
        if hf_configured():
            status["external_services"]["huggingface"] = {"configured": True, "type": "cloud"}
    except Exception:
        pass

    # Overall status
    all_ok = status["backend"]["ok"] and status["ollama"]["ok"]
    status["overall"] = {
        "ok": all_ok,
        "message": "All systems operational" if all_ok else "Some services are unavailable",
    }

    return status


# ── WebSocket health (ping/pong with timeout & heartbeat) ──────────────────


import asyncio as _asyncio


@router.websocket("/ws")
async def websocket_health(websocket: WebSocket):
    """
    WebSocket health endpoint with:
    - 5-second connection timeout
    - 30-second ping/pong heartbeats
    - Clean disconnection handling
    """
    # Accept with a 5-second timeout
    try:
        await _asyncio.wait_for(websocket.accept(), timeout=5.0)
    except _asyncio.TimeoutError:
        logger.warning("WebSocket connection timed out after 5s")
        return
    except Exception as e:
        logger.warning("WebSocket accept failed: %s", e)
        return

    last_pong = _asyncio.get_event_loop().time()
    HEARTBEAT_INTERVAL = 30  # seconds

    async def heartbeat_check():
        """Background task to check heartbeat."""
        nonlocal last_pong
        while True:
            await _asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                await websocket.send_text("ping")
                # Wait for pong with 5s timeout
                try:
                    data = await _asyncio.wait_for(
                        websocket.receive_text(), timeout=5.0
                    )
                    if data == "pong":
                        last_pong = _asyncio.get_event_loop().time()
                except _asyncio.TimeoutError:
                    logger.warning("WebSocket heartbeat timeout - no pong received")
                    return  # Exit heartbeat, connection will close
            except Exception:
                return  # Connection closed

    # Start heartbeat task
    hb_task = _asyncio.create_task(heartbeat_check())

    try:
        while True:
            try:
                data = await _asyncio.wait_for(
                    websocket.receive_text(), timeout=HEARTBEAT_INTERVAL + 10
                )
                if data == "ping":
                    await websocket.send_text("pong")
                elif data == "pong":
                    last_pong = _asyncio.get_event_loop().time()
            except _asyncio.TimeoutError:
                logger.warning("WebSocket receive timed out")
                break
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected")
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
    finally:
        hb_task.cancel()
        try:
            await hb_task
        except _asyncio.CancelledError:
            pass


# ── Readiness probe ─────────────────────────────────────────────────────────


@router.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)):
    await db.execute(select(Project).limit(1))
    from app.utils.ollama_client import ollama

    try:
        models = await ollama.list_models()
    except Exception:
        return {"status": "not_ready", "reason": "ollama_unreachable"}
    return {"status": "ready", "models": models}


# ── Metrics ─────────────────────────────────────────────────────────────────


@router.get("/metrics")
async def metrics():
    return _metrics
