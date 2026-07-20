"""
provider_credential_resolver.py — Unified provider credential resolution.

Single entry point for resolving API keys across ALL provider services.
Database is the single source of truth — only ai_providers.api_key_value is used.

Usage:
  from app.services.provider_credential_resolver import resolve_api_key
  key = resolve_api_key(vendor="opencode")  # "sk-..."
  key = resolve_api_key(provider_id="opencode-go")
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_cache: dict[str, dict] = {}  # vendor → {key, url}


# Lazy‑initialised synchronous engine for DB credential lookups.
# Using a sync engine avoids ``asyncio.run()`` inside an async context,
# which would raise RuntimeError and produce a ``RuntimeWarning`` about
# a coroutine that was never awaited.
_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        from sqlalchemy import create_engine
        from app.config import settings
        sync_url = settings.db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        _sync_engine = create_engine(sync_url, pool_size=2, max_overflow=2)
    return _sync_engine


def _query_db(vendor: str) -> dict:
    """Query ai_providers for a matching row, preferring exact vendor match.

    Uses a synchronous SQLAlchemy engine so the caller never needs an event
    loop – safe to call from both sync and async functions without warnings.
    """
    if vendor in _cache:
        return _cache[vendor]

    try:
        engine = _get_sync_engine()
        from sqlalchemy import text

        with engine.connect() as conn:
            # Try exact vendor match first
            result = conn.execute(
                text(
                    "SELECT provider_id, vendor, api_key_value, base_url "
                    "FROM ai_providers "
                    "WHERE LOWER(vendor) = :vendor AND api_key_value IS NOT NULL "
                    "AND api_key_value != '' LIMIT 1"
                ),
                {"vendor": vendor.lower()},
            )
            row = result.fetchone()
            if row:
                _cache[vendor] = {
                    "provider_id": row[0] or "",
                    "vendor": row[1] or "",
                    "api_key_value": row[2] or "",
                    "base_url": row[3] or "",
                }
                return _cache[vendor]

            # Broader match
            result = conn.execute(
                text(
                    "SELECT provider_id, vendor, api_key_value, base_url "
                    "FROM ai_providers "
                    "WHERE vendor ILIKE :pattern AND api_key_value IS NOT NULL "
                    "AND api_key_value != '' LIMIT 1"
                ),
                {"pattern": f"%{vendor}%"},
            )
            row = result.fetchone()
            if row:
                _cache[vendor] = {
                    "provider_id": row[0] or "",
                    "vendor": row[1] or "",
                    "api_key_value": row[2] or "",
                    "base_url": row[3] or "",
                }
                return _cache[vendor]

        _cache[vendor] = {}
        return {}
    except Exception as e:
        logger.debug("DB credential lookup failed for %s: %s", vendor, e)
        _cache[vendor] = {}
        return {}


def resolve_api_key(
    vendor: str = "",
    provider_id: str = "",
) -> str:
    """
    Resolve the API key for a given provider vendor or provider_id.
    Returns "" if no key can be resolved.
    """
    vendor_norm = (vendor or provider_id).strip().lower()
    if not vendor_norm:
        return ""

    # 1) DB: ai_providers.api_key_value — single source of truth
    db = _query_db(vendor_norm)
    if db.get("api_key_value"):
        logger.debug("API key resolved from DB for vendor=%s", vendor_norm)
        return db["api_key_value"]


def resolve_base_url(
    vendor: str = "",
    provider_id: str = "",
) -> str:
    """
    Resolve the base URL for a given provider vendor or provider_id.
    Returns "" if no URL can be resolved.
    """
    vendor_norm = (vendor or provider_id).strip().lower()
    if not vendor_norm:
        return ""

    # 1) DB: ai_providers.base_url
    db = _query_db(vendor_norm)
    if db.get("base_url"):
        return db["base_url"]

    return ""


def resolve_all(
    vendor: str = "",
    provider_id: str = "",
) -> Tuple[str, str]:
    """Return (api_key, base_url) tuple."""
    return resolve_api_key(vendor=vendor, provider_id=provider_id), resolve_base_url(vendor=vendor, provider_id=provider_id)


def invalidate_cache():
    """Clear the credential cache (call after provider updates)."""
    global _cache
    _cache.clear()
