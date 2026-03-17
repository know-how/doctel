import json
from pathlib import Path
from typing import Any, Tuple

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.db.models import SystemSetting


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
