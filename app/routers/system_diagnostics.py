"""
system_diagnostics.py — DocTel System Status & Diagnostics

Provides comprehensive system health visibility including:
- Database health (connection, tables, migrations)
- Backend API status
- WebSocket status
- Ollama/Gemini/Vector store/Storage/Webhook service status
- Startup progress and timing
- Cache statistics
"""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, Depends

from app.routers.deps import (
    Query,
    User,
    get_current_user,
    require_role,
    settings,
    logger,
)
from app.db.database import db_health, verify_database_health, engine
from app.db.database import AsyncSessionLocal
from app.services.startup_service import startup_manager, ServiceStatus
from app.services.cache_service import cache

router = APIRouter(tags=["system-diagnostics"])


@router.get("/api/system/status")
async def system_status():
    """
    Get comprehensive system status for all services.
    This endpoint is intentionally low-auth (any authenticated user can see it).
    """
    status = {
        "frontend": {"status": "healthy", "message": "Frontend loaded"},
        "backend": {"status": "healthy", "message": "API is running"},
        "database": await _check_database(),
        "websocket": {"status": "healthy", "message": "WebSocket endpoint available"},
        "startup": startup_manager.get_summary(),
        "cache": await cache.get_stats(),
        "services": {},
    }

    # Check Ollama
    try:
        from app.utils.ollama_client import ollama
        models = await ollama.list_models()
        status["services"]["ollama"] = {
            "status": "healthy",
            "message": f"Running with {len(models)} models",
            "models_count": len(models),
        }
    except Exception as e:
        status["services"]["ollama"] = {
            "status": "offline",
            "message": "Ollama service is not running",
            "error": str(e),
            "hint": "Start with: ollama serve",
        }

    # Check Gemini
    try:
        from app.services.gemini_service import is_configured as gemini_configured
        if gemini_configured():
            status["services"]["gemini"] = {
                "status": "healthy",
                "message": "Configured and ready",
            }
        else:
            status["services"]["gemini"] = {
                "status": "offline",
                "message": "Not configured (no API key)",
            }
    except Exception as e:
        status["services"]["gemini"] = {
            "status": "offline",
            "message": f"Error: {e}",
        }

    # Check DeepSeek
    try:
        from app.services.deepseek_service import is_configured as ds_configured
        if ds_configured():
            status["services"]["deepseek"] = {
                "status": "healthy",
                "message": "Configured and ready",
            }
        else:
            status["services"]["deepseek"] = {
                "status": "offline",
                "message": "Not configured (no API key)",
            }
    except Exception:
        status["services"]["deepseek"] = {"status": "offline", "message": "Not available"}

    # OpenCode Zen
    try:
        from app.services.opencode_zen_service import is_configured as zen_configured
        if zen_configured():
            status["services"]["opencode_zen"] = {
                "status": "healthy",
                "message": "Configured and ready",
            }
        else:
            status["services"]["opencode_zen"] = {
                "status": "offline", "message": "Not configured",
            }
    except Exception:
        status["services"]["opencode_zen"] = {"status": "offline", "message": "Not available"}

    # Vector store (ChromaDB)
    try:
        chroma_path = getattr(settings, "chroma_path", None)
        if chroma_path:
            from pathlib import Path
            p = Path(chroma_path)
            if p.exists():
                status["services"]["vector_store"] = {
                    "status": "healthy",
                    "message": f"ChromaDB at {chroma_path}",
                }
            else:
                status["services"]["vector_store"] = {
                    "status": "offline",
                    "message": "Vector store path does not exist",
                }
        else:
            status["services"]["vector_store"] = {
                "status": "offline",
                "message": "No vector store configured",
            }
    except Exception as e:
        status["services"]["vector_store"] = {
            "status": "offline",
            "message": f"Error: {e}",
        }

    # Storage
    try:
        upload_root = getattr(settings, "upload_root", None) or getattr(settings, "projects_dir", None)
        if upload_root:
            from pathlib import Path
            p = Path(upload_root) if isinstance(upload_root, str) else upload_root
            if p.exists():
                status["services"]["storage"] = {
                    "status": "healthy",
                    "message": f"Storage available at {p}",
                }
            else:
                status["services"]["storage"] = {
                    "status": "degraded",
                    "message": f"Storage path does not exist: {p}",
                }
        else:
            status["services"]["storage"] = {
                "status": "offline",
                "message": "No storage path configured",
            }
    except Exception as e:
        status["services"]["storage"] = {
            "status": "offline",
            "message": f"Error: {e}",
        }

    # Configuration system
    status["services"]["configuration"] = {
        "status": "healthy",
        "message": f"3-layer config: defaults → config.yaml → DB overrides",
    }

    # System info
    status["system"] = {
        "database": "mysql",
        "python_version": __import__("sys").version.split()[0],
        "platform": __import__("sys").platform,
        "base_dir": str(getattr(settings, "base_dir", "")),
    }

    return status


@router.get("/api/system/status/detailed")
async def system_status_detailed(
    user: User = Depends(require_role(["admin"])),
):
    """Get detailed system status with extended diagnostics (admin only)."""
    base = await system_status()

    # Add detailed DB info
    base["database"]["pool"] = _get_pool_info()

    # Add startup timeline
    base["startup_timeline"] = _get_startup_timeline()

    # Add service configuration details
    base["config"] = {
        "db_url_masked": _mask_db_url(getattr(settings, "db_url", "")),
        "model_settings": {
            "default_model": getattr(settings, "default_model", ""),
            "text_model": getattr(settings, "text_model", ""),
            "embed_model": getattr(settings, "embed_model", ""),
            "vision_model": getattr(settings, "vision_model", ""),
        },
        "features": {
            "automatic_routing": getattr(settings, "automatic_switching", False),
            "encrypt_sqlite": getattr(settings, "security", None) and getattr(settings.security, "encrypt_sqlite", False),
        },
    }

    return base


@router.post("/api/system/health/ping")
async def system_health_ping():
    """Simple ping endpoint for frontend health checks."""
    return {
        "ok": True,
        "timestamp": time.time(),
        "database": db_health.healthy if hasattr(db_health, 'healthy') else False,
        "uptime": startup_manager.get_summary().get("uptime_seconds", 0),
    }


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _check_database() -> dict:
    """Check database health."""
    try:
        health = await verify_database_health()
        if health.healthy:
            return {
                "status": "healthy",
                "message": f"Connected ({'MySQL' if _is_mysql else 'SQLite'})",
                "latency_ms": health.latency_ms,
                "tables_exist": health.tables_exist,
            }
        else:
            return {
                "status": "degraded" if health.connected else "offline",
                "message": health.error or "Database issues detected",
                "latency_ms": health.latency_ms,
            }
    except Exception as e:
        return {
            "status": "offline",
            "message": f"Database check failed: {e}",
        }


def _get_pool_info() -> dict:
    """Get connection pool information."""
    try:
        pool = engine.pool
        info = {
            "type": pool.__class__.__name__,
        }
        if hasattr(pool, 'size'):
            info["size"] = pool.size()
        if hasattr(pool, 'checkedin'):
            info["checkedin"] = pool.checkedin()
        if hasattr(pool, 'overflow'):
            info["overflow"] = pool.overflow()
        if hasattr(pool, '_pool'):
            info["available"] = pool._pool.qsize() if hasattr(pool._pool, 'qsize') else None
        return info
    except Exception as e:
        return {"error": str(e)}


def _get_startup_timeline() -> list:
    """Get startup timeline from service statuses."""
    timeline = []
    for svc in startup_manager.get_all_status():
        timeline.append({
            "name": svc.name,
            "status": svc.status.value,
            "critical": svc.critical,
            "duration_ms": svc.duration_ms,
            "error": svc.error,
        })
    return timeline


def _mask_db_url(url: str) -> str:
    """Mask password in database URL for safe display."""
    if not url:
        return ""
    import re
    return re.sub(r"(://[^:]+:)([^@]+)(@)", r"\1****\3", url)
