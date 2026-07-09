"""
app_config_service.py — Centralized Application Configuration Service

Provides unified access to all application settings with the following priority:
  1. Database (SystemConfig table) — highest priority, managed via admin UI
  2. Environment variables (.env)
  3. config.yaml file
  4. Hardcoded defaults — lowest priority

This replaces scattered os.getenv() calls and hardcoded defaults throughout
the codebase with a single source of truth.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config_models import SystemConfig
from app.services import config_service as cfg
from app.config import settings as _file_settings

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION SCHEMA — All configurable settings with metadata
# ═══════════════════════════════════════════════════════════════════════════════

# Section: Core Application
CORE_SETTINGS = {
    "app.base_dir": {"default": "C:\\LocalAI", "type": "string", "description": "Base directory for all application data"},
    "app.environment": {"default": "development", "type": "string", "description": "Environment mode (development/production)"},
    "app.offline_only": {"default": True, "type": "bool", "description": "Run in offline-only mode (no external AI calls)"},
    "app.bind_host": {"default": "127.0.0.1", "type": "string", "description": "Host to bind the server to"},
    "app.port": {"default": 8000, "type": "int", "description": "Port to run the server on"},
}

# Section: LLM / Ollama
OLLAMA_SETTINGS = {
    "ollama.text_model": {"default": "qwen3:4b", "type": "string", "description": "Default text generation model"},
    "ollama.fallback_text_model": {"default": "qwen3:4b", "type": "string", "description": "Fallback text model when primary is unavailable"},
    "ollama.vision_model": {"default": "llava:7b", "type": "string", "description": "Model for vision/image tasks"},
    "ollama.embed_model": {"default": "nomic-embed-text", "type": "string", "description": "Model for text embeddings"},
    "ollama.base_url": {"default": "http://localhost:11434", "type": "string", "description": "Ollama API base URL"},
}

# Section: External APIs
EXTERNAL_API_SETTINGS = {
    "api.gemini_api_key": {"default": "", "type": "string", "description": "Google Gemini API key", "secret": True},
    "api.gemini_model": {"default": "gemini-2.5-flash", "type": "string", "description": "Default Gemini model"},
    "api.deepseek_api_key": {"default": "", "type": "string", "description": "DeepSeek API key", "secret": True},
    "api.deepseek_model": {"default": "deepseek-v4-flash-free", "type": "string", "description": "Default DeepSeek model"},
    "api.deepseek_base_url": {"default": "https://opencode.ai/go/v1", "type": "string", "description": "DeepSeek API base URL"},
    "api.opencode_go_api_key": {"default": "", "type": "string", "description": "OpenCode Go API key", "secret": True},
    "api.opencode_zen_api_key": {"default": "", "type": "string", "description": "OpenCode Zen API key", "secret": True},
}

# Section: Model Routing
ROUTING_SETTINGS = {
    "routing.default_model": {"default": "", "type": "string", "description": "System-wide default model (overrides ollama.text_model)"},
    "routing.automatic_switching": {"default": True, "type": "bool", "description": "Enable automatic model switching based on load"},
    "routing.enable_qwen_9b": {"default": False, "type": "bool", "description": "Enable Qwen 9B model for high-capacity tasks"},
    "routing.qwen_9b_model": {"default": "qwen3:8b", "type": "string", "description": "Qwen 9B model identifier"},
}

# Section: RAG / Document Processing
RAG_SETTINGS = {
    "rag.max_context_tokens": {"default": 3000, "type": "int", "description": "Maximum context tokens for RAG responses"},
    "rag.chunk_size": {"default": 1000, "type": "int", "description": "Character chunk size for document splitting"},
    "rag.chunk_overlap": {"default": 150, "type": "int", "description": "Character overlap between chunks"},
    "rag.top_k": {"default": 6, "type": "int", "description": "Number of top chunks to retrieve"},
}

# Section: Auth / Security
AUTH_SETTINGS = {
    "auth.allowed_email_domain": {"default": "zetdc.co.zw", "type": "string", "description": "Allowed email domain for registration"},
    "auth.ad_url": {"default": "", "type": "string", "description": "Active Directory LDAP URL"},
    "auth.ad_domain": {"default": "", "type": "string", "description": "Active Directory domain"},
    "auth.ad_base_dn": {"default": "", "type": "string", "description": "Active Directory base DN"},
    "auth.ad_use_tls": {"default": False, "type": "bool", "description": "Use TLS for AD connections"},
}

# Section: Email
EMAIL_SETTINGS = {
    "email.server_url": {"default": "", "type": "string", "description": "Email server URL"},
    "email.server_endpoint": {"default": "/send", "type": "string", "description": "Email server endpoint"},
    "email.sender_email": {"default": "", "type": "string", "description": "Sender email address"},
    "email.sender_password": {"default": "", "type": "string", "description": "Sender email password", "secret": True},
    "email.smtp_host": {"default": "", "type": "string", "description": "SMTP server host"},
    "email.smtp_port": {"default": 587, "type": "int", "description": "SMTP server port"},
    "email.smtp_user": {"default": "", "type": "string", "description": "SMTP username"},
    "email.smtp_pass": {"default": "", "type": "string", "description": "SMTP password", "secret": True},
    "email.smtp_use_tls": {"default": True, "type": "bool", "description": "Use TLS for SMTP"},
}

# Combine all settings
ALL_SETTINGS = {
    **CORE_SETTINGS,
    **OLLAMA_SETTINGS,
    **EXTERNAL_API_SETTINGS,
    **ROUTING_SETTINGS,
    **RAG_SETTINGS,
    **AUTH_SETTINGS,
    **EMAIL_SETTINGS,
}

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION ACCESS FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

async def get_setting(db: AsyncSession, key: str, default: Any = None) -> Any:
    """Get a setting value from DB, falling back to file settings and defaults."""
    # 1. Try database first
    db_value = await cfg.get_config(key, db)
    if db_value is not None:
        return db_value
    
    # 2. Fall back to file settings (env/config.yaml)
    file_value = _get_file_setting(key)
    if file_value is not None:
        return file_value
    
    # 3. Fall back to hardcoded default
    if key in ALL_SETTINGS:
        return ALL_SETTINGS[key]["default"]
    
    # 4. Return provided default or None
    return default


async def get_setting_str(db: AsyncSession, key: str, default: str = "") -> str:
    """Get setting as string."""
    val = await get_setting(db, key, default)
    return str(val) if val is not None else default


async def get_setting_bool(db: AsyncSession, key: str, default: bool = False) -> bool:
    """Get setting as boolean."""
    val = await get_setting(db, key, default)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("1", "true", "yes", "on")
    return bool(val) if val is not None else default


async def get_setting_int(db: AsyncSession, key: str, default: int = 0) -> int:
    """Get setting as integer."""
    val = await get_setting(db, key, default)
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


async def set_setting(db: AsyncSession, key: str, value: Any, description: str = "") -> SystemConfig:
    """Set a configuration value in the database."""
    if key in ALL_SETTINGS and not description:
        description = ALL_SETTINGS[key].get("description", "")
    return await cfg.set_config(key, value, db, description=description)


async def get_all_settings(db: AsyncSession) -> dict[str, Any]:
    """Get all settings merged (DB overrides file settings)."""
    # Get all file settings
    result = {}
    for key in ALL_SETTINGS:
        result[key] = await get_setting(db, key)
    
    # Add any DB-only settings
    db_settings = await cfg.get_all_config(db)
    for key, value in db_settings.items():
        if key not in result:
            result[key] = value
    
    return result


async def get_settings_by_section(db: AsyncSession, section: str) -> dict[str, Any]:
    """Get all settings for a specific section (e.g., 'ollama', 'api', 'rag')."""
    all_settings = await get_all_settings(db)
    return {k: v for k, v in all_settings.items() if k.startswith(f"{section}.")}


async def reset_setting_to_default(db: AsyncSession, key: str) -> bool:
    """Reset a setting to its default by removing the DB override."""
    return await cfg.delete_config(key, db)


def get_setting_schema() -> dict[str, dict]:
    """Get the full schema of all configurable settings."""
    return ALL_SETTINGS.copy()


def get_sections() -> List[str]:
    """Get list of available configuration sections."""
    sections = set()
    for key in ALL_SETTINGS:
        if "." in key:
            sections.add(key.split(".")[0])
    return sorted(list(sections))


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_file_setting(key: str) -> Any:
    """Get setting from file-based config (config.py/settings object)."""
    # Map config keys to settings object attributes
    mapping = {
        # Core
        "app.base_dir": "base_dir",
        "app.environment": "environment",
        "app.offline_only": "offline_only",
        "app.bind_host": "bind_host",
        "app.port": "port",
        # Ollama
        "ollama.text_model": "text_model",
        "ollama.fallback_text_model": "fallback_text_model",
        "ollama.vision_model": "vision_model",
        "ollama.embed_model": "embed_model",
        "ollama.base_url": "ollama_base_url",
        # External APIs
        "api.gemini_api_key": "gemini_api_key",
        "api.gemini_model": "gemini_model",
        "api.deepseek_api_key": "deepseek_api_key",
        "api.deepseek_model": "deepseek_model",
        "api.deepseek_base_url": "deepseek_base_url",
        "api.opencode_go_api_key": "opencode_go_api_key",
        "api.opencode_zen_api_key": "opencode_zen_api_key",
        # Routing
        "routing.default_model": "default_model",
        "routing.automatic_switching": "automatic_switching",
        "routing.enable_qwen_9b": "enable_qwen_9b",
        "routing.qwen_9b_model": "qwen_9b_model",
        # RAG
        "rag.max_context_tokens": "max_context_tokens",
        "rag.chunk_size": "chunk_size",
        "rag.chunk_overlap": "chunk_overlap",
        "rag.top_k": "top_k",
        # Auth
        "auth.allowed_email_domain": "allowed_email_domain",
        "auth.ad_url": "ad_url",
        "auth.ad_domain": "ad_domain",
        "auth.ad_base_dn": "ad_base_dn",
        "auth.ad_use_tls": "ad_use_tls",
        # Email
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
        attr = mapping[key]
        return getattr(_file_settings, attr, None)
    
    return None
