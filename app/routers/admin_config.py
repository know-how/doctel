"""
admin_config.py — Centralized Configuration Management API

Provides admin endpoints for managing all application settings via the database.
Replaces scattered configuration across .env, config.yaml, and hardcoded values.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.routers.deps import (
    get_db,
    get_current_user,
    require_role,
    User,
)
from app.services import app_config_service as app_cfg

router = APIRouter(prefix="/api/admin/config", tags=["admin-config"])


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION SCHEMA & METADATA
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/schema")
async def get_config_schema(
    user: User = Depends(require_role(["admin"])),
):
    """Get the full schema of all configurable settings with metadata."""
    return {
        "schema": app_cfg.get_setting_schema(),
        "sections": app_cfg.get_sections(),
    }


@router.get("/sections")
async def get_config_sections(
    user: User = Depends(require_role(["admin"])),
):
    """Get list of available configuration sections."""
    return {"sections": app_cfg.get_sections()}


# ═══════════════════════════════════════════════════════════════════════════════
#  SETTINGS CRUD
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/settings")
async def get_all_settings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get all settings with their current values (DB overrides file settings)."""
    settings = await app_cfg.get_all_settings(db)
    return {"settings": settings}


@router.get("/settings/{section}")
async def get_settings_by_section(
    section: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get all settings for a specific section (e.g., 'ollama', 'api', 'rag')."""
    settings = await app_cfg.get_settings_by_section(db, section)
    return {"section": section, "settings": settings}


@router.get("/setting/{key}")
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a single setting value by key."""
    value = await app_cfg.get_setting(db, key)
    schema = app_cfg.get_setting_schema()
    meta = schema.get(key, {})
    return {
        "key": key,
        "value": value,
        "type": meta.get("type", "unknown"),
        "description": meta.get("description", ""),
        "is_secret": meta.get("secret", False),
    }


@router.post("/setting/{key}")
async def set_setting(
    key: str,
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Set a configuration value in the database."""
    value = payload.get("value")
    description = payload.get("description", "")
    
    if value is None:
        raise HTTPException(status_code=400, detail="value is required")
    
    # Validate key exists in schema
    schema = app_cfg.get_setting_schema()
    if key not in schema:
        raise HTTPException(status_code=400, detail=f"Unknown setting key: {key}")
    
    # Set the value
    await app_cfg.set_setting(db, key, value, description)
    
    # Fetch the effective value to confirm
    effective = await app_cfg.get_setting(db, key)
    
    return {
        "key": key,
        "value": effective,
        "description": description or schema.get(key, {}).get("description", ""),
        "updated_at": None,  # Set on next fetch to avoid async lazy-load issues
    }


@router.post("/settings/bulk")
async def set_settings_bulk(
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Set multiple configuration values at once."""
    settings = payload.get("settings", {})
    results = []
    errors = []
    
    schema = app_cfg.get_setting_schema()
    
    for key, value in settings.items():
        if key not in schema:
            errors.append({"key": key, "error": "Unknown setting key"})
            continue
        
        try:
            await app_cfg.set_setting(db, key, value)
            effective = await app_cfg.get_setting(db, key)
            results.append({
                "key": key,
                "value": effective,
                "updated_at": None,
            })
        except Exception as e:
            errors.append({"key": key, "error": str(e)})
    
    return {
        "updated": results,
        "errors": errors,
        "total_updated": len(results),
        "total_errors": len(errors),
    }


@router.delete("/setting/{key}")
async def reset_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Reset a setting to its default by removing the DB override."""
    deleted = await app_cfg.reset_setting_to_default(db, key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Setting not found: {key}")
    
    # Return the default value
    schema = app_cfg.get_setting_schema()
    default_value = schema.get(key, {}).get("default")
    
    return {
        "key": key,
        "reset": True,
        "default_value": default_value,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  EFFECTIVE SETTINGS (For debugging)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/effective/{key}")
async def get_effective_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get the effective value of a setting, showing where it comes from."""
    # Check if overridden in DB
    from app.services import config_service as cfg
    db_value = await cfg.get_config(key, db)
    
    schema = app_cfg.get_setting_schema()
    meta = schema.get(key, {})
    default_value = meta.get("default")
    
    # Get file setting value
    file_value = None
    if key in schema:
        mapping = {
            "app.base_dir": "base_dir",
            "app.environment": "environment",
            "app.offline_only": "offline_only",
            "app.bind_host": "bind_host",
            "app.port": "port",
            "ollama.text_model": "text_model",
            "ollama.fallback_text_model": "fallback_text_model",
            "ollama.vision_model": "vision_model",
            "ollama.embed_model": "embed_model",
            "ollama.base_url": "ollama_base_url",
            "api.gemini_api_key": "gemini_api_key",
            "api.gemini_model": "gemini_model",
            "api.deepseek_api_key": "deepseek_api_key",
            "api.deepseek_model": "deepseek_model",
            "api.deepseek_base_url": "deepseek_base_url",
            "api.opencode_go_api_key": "opencode_go_api_key",
            "api.opencode_zen_api_key": "opencode_zen_api_key",
            "routing.default_model": "default_model",
            "routing.automatic_switching": "automatic_switching",
            "routing.enable_qwen_9b": "enable_qwen_9b",
            "routing.qwen_9b_model": "qwen_9b_model",
            "rag.max_context_tokens": "max_context_tokens",
            "rag.chunk_size": "chunk_size",
            "rag.chunk_overlap": "chunk_overlap",
            "rag.top_k": "top_k",
            "auth.allowed_email_domain": "allowed_email_domain",
            "auth.ad_url": "ad_url",
            "auth.ad_domain": "ad_domain",
            "auth.ad_base_dn": "ad_base_dn",
            "auth.ad_use_tls": "ad_use_tls",
            "email.server_url": "email_server_url",
            "email.server_endpoint": "email_server_endpoint",
            "email.sender_email": "email_sender_email",
            "email.sender_password": "email_sender_password",
            "email.smtp_host": "smtp_host",
            "email.smtp_port": "smtp_port",
            "email.smtp_user": "smtp_user",
            "email.smtp_pass": "smtp_pass",
            "email.smtp_use_tls": "smtp_use_tls",
        }
        if key in mapping:
            from app.config import settings as _file_settings
            file_value = getattr(_file_settings, mapping[key], None)
    
    effective_value = await app_cfg.get_setting(db, key)
    
    source = "default"
    if db_value is not None:
        source = "database"
    elif file_value is not None and file_value != default_value:
        source = "environment/file"
    
    return {
        "key": key,
        "effective_value": effective_value,
        "source": source,
        "database_value": db_value,
        "file_value": file_value,
        "default_value": default_value,
        "description": meta.get("description", ""),
        "type": meta.get("type", "unknown"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM DEFAULTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/defaults")
async def get_all_defaults(
    user: User = Depends(require_role(["admin"])),
):
    """Get all default values (hardcoded fallbacks)."""
    schema = app_cfg.get_setting_schema()
    defaults = {k: v["default"] for k, v in schema.items()}
    return {"defaults": defaults}


@router.get("/defaults/{section}")
async def get_defaults_by_section(
    section: str,
    user: User = Depends(require_role(["admin"])),
):
    """Get default values for a specific section."""
    schema = app_cfg.get_setting_schema()
    defaults = {k: v["default"] for k, v in schema.items() if k.startswith(f"{section}.")}
    return {"section": section, "defaults": defaults}
