import json
import logging
from pathlib import Path
from typing import Any, Optional, Tuple

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.db.models import SystemSetting
from app.services.cache_service import cache, CacheTags

logger = logging.getLogger(__name__)


def _deep_get(d: dict, path: str) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        if part not in cur:
            return None
        cur = cur[part]
    return cur


def _deep_set(d: dict, path: str, value: Any) -> None:
    cur: Any = d
    parts = path.split(".")
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _merge_dict(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict(out[k], v)
        else:
            out[k] = v
    return out


def _flatten(prefix: str, obj: Any, out: dict[str, Any]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            _flatten(key, v, out)
        return
    out[prefix] = obj


def _load_yaml_file() -> dict:
    root_dir = Path(__file__).resolve().parent.parent
    yaml_path = root_dir / "config.yaml"
    try:
        if yaml_path.exists():
            with open(yaml_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        return {}
    return {}


def _defaults_dict() -> dict:
    return Settings().model_dump()


def _file_dict() -> dict:
    return _load_yaml_file()


async def load_db_overrides(db: AsyncSession) -> dict[str, Any]:
    res = await db.execute(select(SystemSetting))
    rows = list(res.scalars().all())
    out: dict[str, Any] = {}
    for r in rows:
        try:
            out[str(r.key)] = json.loads(r.value_json) if r.value_json else None
        except Exception:
            out[str(r.key)] = None
    return out


async def get_effective_settings(db: AsyncSession) -> Tuple[dict, dict]:
    defaults = _defaults_dict()
    file_cfg = _file_dict()
    overrides = await load_db_overrides(db)

    effective = _merge_dict(defaults, file_cfg)
    for k, v in overrides.items():
        _deep_set(effective, k, v)

    sources: dict[str, str] = {}
    flat_defaults: dict[str, Any] = {}
    flat_file: dict[str, Any] = {}
    _flatten("", defaults, flat_defaults)
    _flatten("", file_cfg, flat_file)

    all_keys = set(flat_defaults.keys()) | set(flat_file.keys()) | set(overrides.keys())
    for key in all_keys:
        if key in overrides:
            sources[key] = "db"
        elif key in flat_file:
            sources[key] = "file"
        else:
            sources[key] = "default"

    return effective, sources


async def validate_settings_payload(db: AsyncSession, payload: dict) -> dict:
    effective, _ = await get_effective_settings(db)
    patch_flat: dict[str, Any] = {}
    _flatten("", payload or {}, patch_flat)
    merged = dict(effective)
    for k, v in patch_flat.items():
        _deep_set(merged, k, v)
    Settings(**merged)
    return patch_flat


def apply_live_settings(effective: dict) -> None:
    try:
        new_settings = Settings(**effective)
    except Exception:
        return
    settings.__dict__.update(new_settings.__dict__)


def restart_recommended_for_keys(keys: list[str]) -> dict[str, bool]:
    disruptive_prefixes = [
        "base_dir",
        "storage.",
        "bootstrap.schedule_seconds",
    ]
    out: dict[str, bool] = {}
    for k in keys:
        out[k] = any(k == p or k.startswith(p) for p in disruptive_prefixes)
    return out


# ── Cache-Aware Settings Helpers ────────────────────────────────────────────


async def get_effective_settings_cached(
    db: AsyncSession, use_cache: bool = True
) -> Tuple[dict, dict]:
    """Get effective settings, using cache if available."""
    CACHE_KEY = "effective_settings"
    CACHE_TTL = 60  # 60 seconds

    if use_cache:
        cached = await cache.get(CACHE_KEY)
        if cached is not None:
            return cached["effective"], cached["sources"]

    effective, sources = await get_effective_settings(db)
    await cache.set(
        CACHE_KEY,
        {"effective": effective, "sources": sources},
        ttl_seconds=CACHE_TTL,
        tags=[CacheTags.SETTINGS],
    )
    return effective, sources


async def invalidate_settings_cache() -> None:
    """Invalidate the settings cache when settings are updated."""
    await cache.invalidate_by_tag(CacheTags.SETTINGS)
    logger.debug("Settings cache invalidated")


async def save_settings_with_verification(
    db: AsyncSession,
    patch_flat: dict,
    user_id,
) -> Tuple[bool, Optional[str], dict]:
    """
    Save settings with full DB transaction verification.

    Returns:
        (success, error_message, changed_keys)
    """
    from app.db.database import AsyncSessionLocal

    changed_keys = list(patch_flat.keys())
    effective_before, _ = await get_effective_settings(db)

    try:
        for key, value in patch_flat.items():
            from app.config import _deep_get_value as dgv
            old_value = dgv(effective_before, key)

            # Upsert SystemSetting row
            res = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
            row = res.scalar_one_or_none()
            if not row:
                row = SystemSetting(
                    key=key,
                    value_json=json.dumps(value),
                    updated_by_user_id=user_id,
                )
            else:
                row.value_json = json.dumps(value)
                row.updated_by_user_id = user_id
            db.add(row)

            # Create audit record
            from app.db.models import SettingsAudit
            audit = SettingsAudit(
                key=key,
                old_value_json=json.dumps(old_value),
                new_value_json=json.dumps(value),
                changed_by_user_id=user_id,
            )
            db.add(audit)

        # Commit transaction
        await db.commit()

        # Verify the write by reading back
        verify_ok = True
        for key in changed_keys:
            res = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
            row = res.scalar_one_or_none()
            if row is None:
                verify_ok = False
                break

        if not verify_ok:
            # Rollback verification failed — this shouldn't happen with proper SQL
            logger.error("Write verification failed for settings keys: %s", changed_keys)
            return False, "Write verification failed — database did not persist changes", {}

        # Invalidate cache so next read picks up changes
        await invalidate_settings_cache()

        # Apply live
        effective_after, sources = await get_effective_settings(db)
        apply_live_settings(effective_after)

        return True, None, {"changed_keys": changed_keys, "sources": sources}

    except Exception as e:
        await db.rollback()
        logger.error("Settings save failed (rolled back): %s", e)
        return False, f"Database transaction failed: {e}", {}
