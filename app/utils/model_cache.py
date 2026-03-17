import json
import time
from pathlib import Path
from typing import Any

from app.config import settings


def _cache_path() -> Path:
    path = Path(settings.base_dir) / "data" / "ollama"
    path.mkdir(parents=True, exist_ok=True)
    return path / "model_cache.json"


def load_model_cache() -> dict[str, Any]:
    p = _cache_path()
    if not p.exists():
        return {"installed": [], "updated_at": 0, "pulls": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {"installed": [], "updated_at": 0, "pulls": {}}
    except Exception:
        return {"installed": [], "updated_at": 0, "pulls": {}}


def save_model_cache(cache: dict[str, Any]) -> None:
    p = _cache_path()
    p.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def update_installed_models(installed: list[str]) -> dict[str, Any]:
    cache = load_model_cache()
    cache["installed"] = list(installed or [])
    cache["updated_at"] = int(time.time())
    save_model_cache(cache)
    return cache


def set_pull_state(model: str, state: str, last_line: str | None = None) -> dict[str, Any]:
    cache = load_model_cache()
    pulls = cache.get("pulls") or {}
    pulls[model] = {
        "state": state,
        "updated_at": int(time.time()),
        "last_line": last_line or "",
    }
    cache["pulls"] = pulls
    save_model_cache(cache)
    return cache
