"""
DocTel API Routers.

Each sub-module defines an APIRouter that is imported lazily inside
``include_routers()`` so that importing ``app.routers.deps`` does not
trigger a circular-import chain via the router sub-modules.
"""

import logging

logger = logging.getLogger(__name__)


def _try_import_router(module_name: str, attr: str = "router"):
    """Try importing a router module; return None if missing."""
    try:
        mod = __import__(f"app.routers.{module_name}", fromlist=[attr])
        return getattr(mod, attr, None)
    except Exception as exc:
        logger.warning("Router '%s' not available: %s", module_name, exc)
        return None


def include_routers(app) -> None:
    """Register all API sub‑routers onto the FastAPI application.

    Missing routers are silently skipped (warning logged).
    Imports are deferred to avoid circular imports: ``main.py`` imports
    ``_sse_broadcast`` from ``app.routers.deps`` before router modules
    have been fully loaded.
    """
    _ROUTERS = [
        "health",
        "auth",
        "models",
        "settings",
        "projects",
        "documents",
        "ingest",
        "chat",
        "ask",
        "vision",
        "audio",
        "charts",
        "admin",
        "admin_config",
        "training",
        "sync",
        "team",
        "analyze",
        "outputs",
        "compat",
        "model_management",
        "system_diagnostics",
        "config_lookup",
        "prompt_suggestions",
        "enterprise_admin",
        "admin_embeddings",
        "agent_gateway",
        "processing_control",
        "admin_jobs",
        "voice",
    ]
    for name in _ROUTERS:
        router = _try_import_router(name)
        if router is not None:
            app.include_router(router)


__all__ = [
    "include_routers",
    "ingest_router",
    "processing_control_router",
    "admin_jobs_router",
    "chat_router",
    "ask_router",
    "vision_router",
    "audio_router",
    "charts_router",
    "admin_router",
    "training_router",
    "sync_router",
    "team_router",
    "analyze_router",
    "outputs_router",
    "compat_router",
]
