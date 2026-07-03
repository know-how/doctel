"""
DocTel – monolithic FastAPI entry point.

This file has been refactored: all endpoint implementations now live in
``app/routers/`` sub-modules.  This skeleton only keeps the application
factory, middleware, exception handlers, the startup event, and the
``include_routers(app)`` call that registers every sub-router.
"""

import os
import json
import yaml
import shutil
import re
import time
import uvicorn
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import asyncio
import uuid
import datetime

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.config import settings
from app.db.database import init_db, get_db, AsyncSessionLocal, _db_path, encrypt_database
from app.security.rbac import get_current_user, require_role
from app.services.ingest_worker import start_worker
from app.services.bootstrap_service import run_bootstrap_scan, start_watcher, get_bootstrap_status
from app.services.system_settings_service import (
    get_effective_settings,
    validate_settings_payload,
    apply_live_settings,
    restart_recommended_for_keys,
)
from app.routers.deps import _sse_broadcast
from app.routers import include_routers

logger = logging.getLogger(__name__)

app = FastAPI(title="DocIntel")

include_routers(app)

# ═══════════════════════════════════════════════════════════════════════════════
# Exception handlers
# ═══════════════════════════════════════════════════════════════════════════════


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        body = await request.body()
        logger.error("=== 422 REQUEST VALIDATION ERROR ===")
        logger.error("URL: %s %s", request.method, request.url.path)
        logger.error("Body: %s", body.decode("utf-8", errors="replace")[:2000])
        logger.error("Errors: %s", exc.errors())
    except Exception:
        pass
    return JSONResponse(status_code=422, content={"error": "validation_error", "detail": exc.errors()})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        detail = exc.detail
        if isinstance(detail, dict) and detail.get("error") == "token_expired":
            return JSONResponse(status_code=401, content={"error": "token_expired"})
        if detail == "token_expired":
            return JSONResponse(status_code=401, content={"error": "token_expired"})
    return JSONResponse(status_code=int(exc.status_code or 500), content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    try:
        logging.getLogger().exception("unhandled error")
    except Exception:
        pass
    return JSONResponse(status_code=500, content={"error": "internal_error"})


# ═══════════════════════════════════════════════════════════════════════════════
# Middleware
# ═══════════════════════════════════════════════════════════════════════════════

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def debug_all_requests(request: Request, call_next):
    path = request.url.path
    method = request.method
    try:
        if method == "POST" and ("/api/ask" in path or "/api/chat" in path):
            print(f"\n=== REQUEST: {method} {path} ===", flush=True)
    except Exception:
        pass
    try:
        response = await call_next(request)
        return response
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail} if isinstance(exc.detail, str) else exc.detail,
        )
    except Exception as exc:
        print(f"\n!!! UNHANDLED EXCEPTION: {method} {path} !!!", flush=True)
        print(f"Error type: {type(exc).__name__}", flush=True)
        print(f"Error: {exc}", flush=True)
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(exc)})


# ═══════════════════════════════════════════════════════════════════════════════
# Startup event — Optimized with critical/non-critical service loading
# ═══════════════════════════════════════════════════════════════════════════════


@app.on_event("startup")
async def startup():
    startup_start = time.time()

    # ── Phase 1: Logging (fast, no deps) ────────────────────────────────────
    _setup_logging()

    # ── Phase 2: Critical Services (must complete before app is usable) ─────
    from app.services.startup_service import startup_manager, ServiceStatus

    # Register all services with the startup manager

    # 2a. Database (critical)
    async def _init_db():
        health = await init_db()
        if not health.healthy:
            raise RuntimeError(health.error or "Database initialization failed")
        return {"latency_ms": health.latency_ms}

    startup_manager.register("database", _init_db, critical=True)

    # 2b. Settings load (critical, depends on DB)
    async def _load_settings():
        try:
            async with AsyncSessionLocal() as db:
                effective, _ = await get_effective_settings(db)
                apply_live_settings(effective)
        except Exception as e:
            logger.warning("Settings load degraded (defaults will be used): %s", e)

    startup_manager.register("configuration", _load_settings, critical=True, depends_on=["database"])

    # 2c. Ingest worker (critical - enables document processing)
    async def _start_ingest():
        await start_worker()

    startup_manager.register("ingest_worker", _start_ingest, critical=True)

    # Start critical services (sequential, dependency-ordered)
    critical_results = await startup_manager.start_critical()
    for svc in critical_results:
        if svc.status == ServiceStatus.HEALTHY:
            logger.info("✓ Critical service '%s' ready (%.1fms)", svc.name, svc.duration_ms or 0)
        else:
            logger.warning("⚠ Critical service '%s' %s: %s", svc.name, svc.status.value, svc.error or "")

    # ── Phase 3: Non-Critical Services (parallel, async) ────────────────────

    # 3a. Ollama health check
    async def _check_ollama():
        from app.utils.ollama_client import ollama
        await ollama.list_models()

    startup_manager.register("ollama", _check_ollama)

    # 3b. Gemini service check
    async def _check_gemini():
        from app.services.gemini_service import is_configured
        is_configured()

    startup_manager.register("gemini", _check_gemini)

    # 3c. DeepSeek service check
    async def _check_deepseek():
        from app.services.deepseek_service import is_configured
        is_configured()

    startup_manager.register("deepseek", _check_deepseek)

    # 3d. Bootstrap scan (file indexing)
    startup_manager.register("bootstrap_scan", lambda: asyncio.create_task(run_bootstrap_scan()))

    # 3e. File watcher
    async def _start_watcher_svc():
        await start_watcher()

    startup_manager.register("file_watcher", _start_watcher_svc)

    # Start all non-critical services in parallel
    non_critical_results = await startup_manager.start_non_critical()

    # ── Phase 4: Wire training SSE (fast, no deps) ──────────────────────────
    _event_loop = asyncio.get_event_loop()
    from app.training.training_scheduler import scheduler as _training_scheduler

    def _on_training_complete(adapter_id: str) -> None:
        _event_loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(
                _sse_broadcast("training.complete", {"adapter_id": adapter_id})
            )
        )

    _training_scheduler.set_completion_callback(_on_training_complete)

    # ── Phase 5: Warm cache ─────────────────────────────────────────────────
    try:
        from app.services.cache_service import cache_warmer, CacheTags
        from app.services.system_settings_service import get_effective_settings

        async def _warm_settings():
            async with AsyncSessionLocal() as db:
                eff, _ = await get_effective_settings(db)
                return eff

        cache_warmer.register("effective_settings", _warm_settings, tags=[CacheTags.SETTINGS])
        asyncio.create_task(cache_warmer.warm_all())
    except Exception as e:
        logger.warning("Cache warmer init failed: %s", e)

    total_ms = round((time.time() - startup_start) * 1000, 1)
    logger.info("=" * 60)
    logger.info("DocTel startup complete in %.1fms", total_ms)
    logger.info("Critical services: %d/%d healthy",
                sum(1 for s in critical_results if s.status == ServiceStatus.HEALTHY),
                len(critical_results))
    logger.info("=" * 60)


def _setup_logging() -> None:
    """Configure logging handlers (called early in startup)."""
    try:
        log_path = settings.projects_dir.parent.parent / "logs" / "app.log"
    except Exception:
        log_path = Path("logs/app.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Avoid duplicate handlers
    root_logger = logging.getLogger()
    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        handler = RotatingFileHandler(
            str(log_path), maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s level=%(levelname)s msg=%(message)s"))
        root_logger.addHandler(handler)

    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        console.setLevel(logging.DEBUG)
        root_logger.addHandler(console)

    root_logger.setLevel(logging.INFO)


# ═══════════════════════════════════════════════════════════════════════════════
# Shutdown event – encrypt SQLite at rest (SQLite only)
# ═══════════════════════════════════════════════════════════════════════════════


@app.on_event("shutdown")
async def shutdown():
    from app.db.database import _is_sqlite
    if _is_sqlite and encrypt_database is not None and _db_path is not None:
        encrypt_database(_db_path, settings.base_dir)


# ═══════════════════════════════════════════════════════════════════════════════
# Direct entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.bind_host, port=settings.port, reload=True)
