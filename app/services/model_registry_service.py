"""
model_registry_service.py — DocTel Admin Model Registry

Stores a dynamic registry of AI model providers and their models in a JSON
file under the base directory.  The registry is separate from the Ollama-based
model list; it lets admins define arbitrary cloud / API models and their
capabilities (vision, tool-calling, etc.) for use by the model router and
frontend model picker.

JSON structure:
    [{
      "id": "uuid-or-slug",
      "name": "OpenCodeGO",
      "vendor": "customendpoint",
      "base_url": "https://api.example.com/v1",
      "api_key_value": "",                  # stored key (encrypted at rest in future)
      "models": [{
        "id": "deepseek-v4-pro",
        "name": "DeepSeek V4 Pro",
        "vision": false,
        "toolCalling": true,
        "context_window": 128000,
        "capabilities": ["text", "code", "reasoning"]
      }]
    }]
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

_REGISTRY_FILE = "model_registry.json"


# ── helpers ──────────────────────────────────────────────────────────────────


def _registry_path() -> Path:
    """Return the path to the registry JSON file under base_dir."""
    p = Path(settings.base_dir) / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p / _REGISTRY_FILE


def _load_registry() -> List[Dict[str, Any]]:
    """Load the full provider list from disk.  Returns [] if missing / corrupt."""
    path = _registry_path()
    if not path.exists():
        # Seed from providers.json on first access
        return _seed_from_providers_json()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list) and len(data) > 0:
            return data
        # File exists but empty - seed
        return _seed_from_providers_json()
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load model registry: %s", exc)
        return _seed_from_providers_json()


def _seed_from_providers_json() -> List[Dict[str, Any]]:
    """Seed the registry from app/data/providers.json if available."""
    providers_json_path = Path(__file__).resolve().parent.parent / "data" / "providers.json"
    if not providers_json_path.exists():
        return []
    try:
        raw = providers_json_path.read_text(encoding="utf-8")
        external = json.loads(raw)
    except Exception:
        logger.warning("Failed to parse providers.json for registry seeding")
        return []

    providers = []
    seen_names = set()
    for ep in external:
        name = (ep.get("name") or "").strip()
        if not name or name.lower() in seen_names:
            continue
        seen_names.add(name.lower())
        # Use a stable id from the name
        provider_id = name.lower().replace(" ", "-").replace("_", "-")
        models = []
        for em in ep.get("models", []):
            mid = em.get("id", "").strip()
            if not mid:
                continue
            models.append({
                "id": mid,
                "name": em.get("name", mid),
                "vision": bool(em.get("vision", False)),
                "toolCalling": bool(em.get("toolCalling", False)),
                "context_window": int(em.get("maxInputTokens", 128000)),
                "capabilities": ["text", "chat"],
            })
        providers.append({
            "id": provider_id,
            "name": name,
            "vendor": ep.get("vendor", ""),
            "base_url": "",
            "models": models,
        })

    if providers:
        _save_registry(providers)
        logger.info("Seeded model registry with %d providers from providers.json", len(providers))
    return providers


def _save_registry(providers: List[Dict[str, Any]]) -> None:
    """Atomically write the provider list to disk."""
    path = _registry_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(providers, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(path)


# ── public API ───────────────────────────────────────────────────────────────


def get_all_providers() -> List[Dict[str, Any]]:
    """Return every provider entry (with nested models)."""
    return _load_registry()


def get_provider(provider_id: str) -> Optional[Dict[str, Any]]:
    """Look up a single provider by id."""
    for p in _load_registry():
        if p.get("id") == provider_id:
            return p
    return None


def add_provider(
    name: str,
    vendor: str = "",
    base_url: str = "",
    models: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Append a new provider and return it with a generated id."""
    providers = _load_registry()
    provider = {
        "id": str(uuid.uuid4()),
        "name": name,
        "vendor": vendor or "",
        "base_url": base_url or "",
        "models": models or [],
    }
    providers.append(provider)
    _save_registry(providers)
    logger.info("Added model provider '%s' (id=%s)", name, provider["id"])
    return provider


def update_provider(
    provider_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update fields on an existing provider.  Returns the updated entry or None."""
    providers = _load_registry()
    for idx, p in enumerate(providers):
        if p.get("id") == provider_id:
            # Merge top-level fields (except id and models which have their own endpoint)
            allowed = {"name", "vendor", "base_url"}
            for key, value in updates.items():
                if key in allowed:
                    providers[idx][key] = value
            _save_registry(providers)
            logger.info("Updated provider '%s'", provider_id)
            return providers[idx]
    return None


def delete_provider(provider_id: str) -> bool:
    """Remove a provider and all its models.  Returns True if deleted."""
    providers = _load_registry()
    new_list = [p for p in providers if p.get("id") != provider_id]
    if len(new_list) == len(providers):
        return False
    _save_registry(new_list)
    logger.info("Deleted provider '%s'", provider_id)
    return True


# ── model-level operations ───────────────────────────────────────────────────


def add_model_to_provider(
    provider_id: str,
    model_id: str,
    name: str,
    vision: bool = False,
    toolCalling: bool = False,
    context_window: int = 4096,
    capabilities: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Add a model entry under an existing provider."""
    providers = _load_registry()
    for idx, p in enumerate(providers):
        if p.get("id") == provider_id:
            model_entry = {
                "id": model_id,
                "name": name,
                "vision": vision,
                "toolCalling": toolCalling,
                "context_window": context_window,
                "capabilities": capabilities or [],
            }
            providers[idx].setdefault("models", []).append(model_entry)
            _save_registry(providers)
            logger.info("Added model '%s' to provider '%s'", model_id, provider_id)
            return model_entry
    return None


def remove_model_from_provider(provider_id: str, model_id: str) -> bool:
    """Delete a model from a provider.  Returns True if removed."""
    providers = _load_registry()
    for idx, p in enumerate(providers):
        if p.get("id") == provider_id:
            old_len = len(providers[idx].get("models", []))
            providers[idx]["models"] = [
                m for m in providers[idx].get("models", []) if m.get("id") != model_id
            ]
            if len(providers[idx]["models"]) < old_len:
                _save_registry(providers)
                logger.info("Removed model '%s' from provider '%s'", model_id, provider_id)
                return True
            return False
    return False


def get_registry_flat() -> List[Dict[str, Any]]:
    """Return a flat list of all models across all providers with provider info."""
    flat: List[Dict[str, Any]] = []
    for p in _load_registry():
        provider_name = p.get("name", "")
        provider_id = p.get("id", "")
        for m in p.get("models", []):
            flat.append({
                "provider_id": provider_id,
                "provider_name": provider_name,
                "model_id": m.get("id"),
                "model_name": m.get("name"),
                "vision": m.get("vision", False),
                "toolCalling": m.get("toolCalling", False),
                "context_window": m.get("context_window", 4096),
                "capabilities": m.get("capabilities", []),
            })
    return flat
