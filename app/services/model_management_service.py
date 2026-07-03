"""
model_management_service.py — DocTel Enterprise Model Management

GitHub Copilot-style model management system with:
- AI Provider Management (Layer 1)
- Model Catalog per provider (Layer 2)
- Extended Model Metadata (Layer 3)
- Capability-Based Classification (Layer 4)
- Model Activation States (Layer 5)
- Chat Visibility Control (Layer 6)
- Role-Based Access Control (Layer 7)
- Department Restrictions (Layer 8)
- Model Marketplace (Layer 9)
- Task-to-Model Mapping (Layer 11)
- Intelligent Model Selection (Layer 12)
- Health Monitoring (Layer 13)
- Audit & Governance (Layer 14)

Stored in a JSON file under the base directory.
"""

from __future__ import annotations

import json
import logging
import uuid
import time
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

_MANAGEMENT_FILE = "model_management.json"
_AUDIT_FILE = "model_audit.json"
_HEALTH_FILE = "model_health.json"

# ── Constants ────────────────────────────────────────────────────────────────

VALID_CAPABILITIES = [
    "chat", "vision", "tools", "code", "reasoning",
    "embedding", "rag", "classification", "summary",
    "extraction", "audio", "comparison",
]

VALID_ROLES = [
    "super_admin", "admin", "manager", "engineer",
    "power_user", "general_user", "guest",
]

ZETDC_DEPARTMENTS = [
    "ict", "generation", "transmission", "distribution",
    "projects", "operations", "finance", "human_resources",
    "procurement", "customer_services",
]

TASK_TYPES = [
    "chat", "summary", "extraction", "classification",
    "comparison", "vision", "embedding", "rag", "code_generation",
]

MODEL_STATES = [
    "active", "inactive", "installed", "downloading",
    "error", "maintenance", "retired",
]

HEALTH_STATUSES = ["healthy", "degraded", "unhealthy", "unknown"]

DEFAULT_PROVIDERS = [
    {
        "id": "ollama",
        "name": "Ollama",
        "vendor": "Ollama",
        "base_url": "http://localhost:11434",
        "api_key_env": "",
        "status": "connected",
        "description": "Local open-source model runner",
        "icon": "ollama",
        "order": 0,
    },
    {
        "id": "google-gemini",
        "name": "Google Gemini",
        "vendor": "Google",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key_env": "GEMINI_API_KEY",
        "status": "disconnected",
        "description": "Google's Gemini family of models",
        "icon": "gemini",
        "order": 1,
    },
    {
        "id": "opencode-go",
        "name": "OpenCode Go",
        "vendor": "OpenCode",
        "base_url": "https://opencode.ai/go/v1",
        "api_key_env": "OPENCODE_GO_API_KEY",
        "status": "disconnected",
        "description": "OpenCode Go API proxy",
        "icon": "opencode",
        "order": 2,
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "vendor": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "status": "disconnected",
        "description": "DeepSeek AI models",
        "icon": "deepseek",
        "order": 3,
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "vendor": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "status": "disconnected",
        "description": "OpenAI GPT models",
        "icon": "openai",
        "order": 4,
    },
    {
        "id": "anthropic",
        "name": "Anthropic",
        "vendor": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
        "status": "disconnected",
        "description": "Anthropic Claude models",
        "icon": "anthropic",
        "order": 5,
    },
    {
        "id": "lm-studio",
        "name": "LM Studio",
        "vendor": "LM Studio",
        "base_url": "http://localhost:1234/v1",
        "api_key_env": "",
        "status": "disconnected",
        "description": "Local model server via LM Studio",
        "icon": "lmstudio",
        "order": 6,
    },
    {
        "id": "mistral",
        "name": "Mistral AI",
        "vendor": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "api_key_env": "MISTRAL_API_KEY",
        "status": "disconnected",
        "description": "Mistral AI cloud models",
        "icon": "mistral",
        "order": 7,
    },
    {
        "id": "huggingface",
        "name": "HuggingFace",
        "vendor": "HuggingFace",
        "base_url": "https://api-inference.huggingface.co",
        "api_key_env": "HUGGINGFACE_API_KEY",
        "status": "disconnected",
        "description": "HuggingFace Inference API",
        "icon": "huggingface",
        "order": 8,
    },
]

DEFAULT_MODELS_BY_PROVIDER: Dict[str, List[Dict[str, Any]]] = {
    "ollama": [
        {
            "id": "qwen3:4b",
            "name": "Qwen 3 4B",
            "contextWindow": 32768,
            "supportsChat": True,
            "supportsVision": False,
            "supportsTools": True,
            "supportsCode": True,
            "supportsEmbedding": False,
            "supportsReasoning": True,
            "supportsRag": True,
            "supportsClassification": True,
            "supportsSummary": True,
            "supportsExtraction": True,
            "enabled": True,
            "visibleToUsers": True,
            "isDefault": False,
            "allowedRoles": [],
            "departmentRestrictions": [],
            "state": "installed",
            "pricingTier": "free",
            "license": "Apache 2.0",
        },
        {
            "id": "qwen3:8b",
            "name": "Qwen 3 8B",
            "contextWindow": 32768,
            "supportsChat": True,
            "supportsVision": False,
            "supportsTools": True,
            "supportsCode": True,
            "supportsEmbedding": False,
            "supportsReasoning": True,
            "supportsRag": True,
            "supportsClassification": True,
            "supportsSummary": True,
            "supportsExtraction": True,
            "enabled": True,
            "visibleToUsers": True,
            "isDefault": False,
            "allowedRoles": [],
            "departmentRestrictions": [],
            "state": "installed",
            "pricingTier": "free",
            "license": "Apache 2.0",
        },
        {
            "id": "llama3.2:latest",
            "name": "Llama 3.2",
            "contextWindow": 8192,
            "supportsChat": True,
            "supportsVision": True,
            "supportsTools": False,
            "supportsCode": True,
            "supportsEmbedding": False,
            "supportsReasoning": True,
            "supportsRag": True,
            "supportsClassification": True,
            "supportsSummary": True,
            "supportsExtraction": True,
            "enabled": True,
            "visibleToUsers": True,
            "isDefault": False,
            "allowedRoles": [],
            "departmentRestrictions": [],
            "state": "installed",
            "pricingTier": "free",
            "license": "Meta Llama 3.2 Community",
        },
        {
            "id": "nomic-embed-text",
            "name": "Nomic Embed Text",
            "contextWindow": 8192,
            "supportsChat": False,
            "supportsVision": False,
            "supportsTools": False,
            "supportsCode": False,
            "supportsEmbedding": True,
            "supportsReasoning": False,
            "supportsRag": True,
            "supportsClassification": False,
            "supportsSummary": False,
            "supportsExtraction": False,
            "enabled": True,
            "visibleToUsers": False,
            "isDefault": True,
            "forTasks": ["embedding"],
            "allowedRoles": [],
            "departmentRestrictions": [],
            "state": "installed",
            "pricingTier": "free",
            "license": "Apache 2.0",
        },
    ],
    "google-gemini": [
        {
            "id": "gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "contextWindow": 1048576,
            "supportsChat": True,
            "supportsVision": True,
            "supportsTools": True,
            "supportsCode": True,
            "supportsEmbedding": False,
            "supportsReasoning": True,
            "supportsRag": False,
            "supportsClassification": True,
            "supportsSummary": True,
            "supportsExtraction": True,
            "enabled": False,
            "visibleToUsers": True,
            "isDefault": False,
            "allowedRoles": [],
            "departmentRestrictions": [],
            "state": "available",
            "pricingTier": "pay-as-you-go",
            "license": "Proprietary",
        },
        {
            "id": "gemini-2.5-pro",
            "name": "Gemini 2.5 Pro",
            "contextWindow": 1048576,
            "supportsChat": True,
            "supportsVision": True,
            "supportsTools": True,
            "supportsCode": True,
            "supportsEmbedding": False,
            "supportsReasoning": True,
            "supportsRag": False,
            "supportsClassification": True,
            "supportsSummary": True,
            "supportsExtraction": True,
            "enabled": False,
            "visibleToUsers": True,
            "isDefault": False,
            "allowedRoles": [],
            "departmentRestrictions": [],
            "state": "available",
            "pricingTier": "pay-as-you-go",
            "license": "Proprietary",
        },
    ],
    "opencode-go": [
        {
            "id": "deepseek-v4-flash-free",
            "name": "DeepSeek V4 Flash (Free)",
            "contextWindow": 128000,
            "supportsChat": True,
            "supportsVision": False,
            "supportsTools": True,
            "supportsCode": True,
            "supportsEmbedding": False,
            "supportsReasoning": True,
            "supportsRag": False,
            "supportsClassification": True,
            "supportsSummary": True,
            "supportsExtraction": True,
            "enabled": False,
            "visibleToUsers": True,
            "isDefault": False,
            "allowedRoles": [],
            "departmentRestrictions": [],
            "state": "available",
            "pricingTier": "free",
            "license": "Proprietary",
        },
        {
            "id": "glm-5",
            "name": "GLM 5",
            "contextWindow": 128000,
            "supportsChat": True,
            "supportsVision": True,
            "supportsTools": True,
            "supportsCode": True,
            "supportsEmbedding": False,
            "supportsReasoning": True,
            "supportsRag": False,
            "supportsClassification": True,
            "supportsSummary": True,
            "supportsExtraction": True,
            "enabled": False,
            "visibleToUsers": True,
            "isDefault": False,
            "allowedRoles": [],
            "departmentRestrictions": [],
            "state": "available",
            "pricingTier": "free",
            "license": "Proprietary",
        },
        {
            "id": "kimi-k2.6",
            "name": "Kimi K2.6",
            "contextWindow": 128000,
            "supportsChat": True,
            "supportsVision": True,
            "supportsTools": True,
            "supportsCode": True,
            "supportsEmbedding": False,
            "supportsReasoning": True,
            "supportsRag": False,
            "supportsClassification": True,
            "supportsSummary": True,
            "supportsExtraction": True,
            "enabled": False,
            "visibleToUsers": True,
            "isDefault": False,
            "allowedRoles": [],
            "departmentRestrictions": [],
            "state": "available",
            "pricingTier": "free",
            "license": "Proprietary",
        },
    ],
    "deepseek": [
        {
            "id": "deepseek-v4-pro",
            "name": "DeepSeek V4 Pro",
            "contextWindow": 128000,
            "supportsChat": True,
            "supportsVision": True,
            "supportsTools": True,
            "supportsCode": True,
            "supportsEmbedding": False,
            "supportsReasoning": True,
            "supportsRag": False,
            "supportsClassification": True,
            "supportsSummary": True,
            "supportsExtraction": True,
            "enabled": False,
            "visibleToUsers": True,
            "isDefault": False,
            "allowedRoles": [],
            "departmentRestrictions": [],
            "state": "available",
            "pricingTier": "pay-as-you-go",
            "license": "Proprietary",
        },
    ],
}

AUTOMATIC_ROUTING_RULES = {
    "code_generation": {
        "description": "Code queries → best code model",
        "priority_capabilities": ["code", "reasoning"],
        "preferred_family": "deepseek",
    },
    "summary": {
        "description": "Document summary → general chat model",
        "priority_capabilities": ["summary", "reasoning"],
        "preferred_family": "qwen",
    },
    "vision": {
        "description": "Image analysis → vision-capable model",
        "priority_capabilities": ["vision", "chat"],
        "preferred_family": "gemini",
    },
    "extraction": {
        "description": "Entity extraction → reasoning model",
        "priority_capabilities": ["extraction", "reasoning"],
        "preferred_family": "deepseek",
    },
    "chat": {
        "description": "General chat → default chat model",
        "priority_capabilities": ["chat"],
        "preferred_family": None,
    },
    "embedding": {
        "description": "Embedding → embedding-specialized model",
        "priority_capabilities": ["embedding"],
        "preferred_family": "nomic",
    },
    "rag": {
        "description": "RAG queries → chat + reasoning model",
        "priority_capabilities": ["rag", "chat"],
        "preferred_family": None,
    },
    "classification": {
        "description": "Classification → general model",
        "priority_capabilities": ["classification"],
        "preferred_family": None,
    },
}


# ── File I/O ─────────────────────────────────────────────────────────────────


def _data_path(filename: str) -> Path:
    p = Path(settings.base_dir) / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p / filename


def _load_json(filename: str, default: Any = None) -> Any:
    path = _data_path(filename)
    if not path.exists():
        return default if default is not None else {}
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load %s: %s", filename, exc)
        return default if default is not None else {}


def _save_json(filename: str, data: Any) -> None:
    path = _data_path(filename)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# ── Audit helpers ────────────────────────────────────────────────────────────


def _add_audit_entry(
    action: str,
    entity_type: str,
    entity_id: str,
    details: Dict[str, Any],
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add an audit log entry."""
    audit = _load_json(_AUDIT_FILE, [])
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "entityType": entity_type,
        "entityId": entity_id,
        "details": details,
        "userId": user_id or "system",
        "userName": user_name or "System",
    }
    audit.insert(0, entry)
    # Keep max 1000 entries
    if len(audit) > 1000:
        audit = audit[:1000]
    _save_json(_AUDIT_FILE, audit)
    return entry


def get_audit_log(limit: int = 100, action: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve audit log entries."""
    audit = _load_json(_AUDIT_FILE, [])
    if action:
        audit = [e for e in audit if e.get("action") == action]
    return audit[:limit]


# ── Provider Management (Layer 1) ────────────────────────────────────────────


def _get_management_data() -> Dict[str, Any]:
    """Load full management data or initialize with defaults."""
    data = _load_json(_MANAGEMENT_FILE, None)
    if data is None or "providers" not in data:
        data = {
            "providers": DEFAULT_PROVIDERS,
            "taskMapping": {},
            "automaticRouting": True,
            "lastUpdated": datetime.utcnow().isoformat(),
        }
        # Add default models
        for prov in data["providers"]:
            prov_id = prov["id"]
            if prov_id in DEFAULT_MODELS_BY_PROVIDER:
                prov["models"] = DEFAULT_MODELS_BY_PROVIDER[prov_id]
            else:
                prov["models"] = []
        # Merge models from providers.json (if available)
        _merge_providers_json_into(data)
        _save_json(_MANAGEMENT_FILE, data)
    return data


def _merge_providers_json_into(data: Dict[str, Any]) -> None:
    """Merge models from app/data/providers.json into the V2 management data.
    Matches providers by name and adds/updates their model lists."""
    import json as _json
    from pathlib import Path as _Path
    providers_json_path = _Path(__file__).resolve().parent.parent / "data" / "providers.json"
    if not providers_json_path.exists():
        return
    try:
        raw = providers_json_path.read_text(encoding="utf-8")
        external_providers = _json.loads(raw)
    except Exception:
        logger.warning("Failed to parse providers.json for V2 seeding")
        return

    # Build lookup by (lowercased, space-stripped name)
    ext_by_name = {}
    for ep in external_providers:
        name = (ep.get("name") or "").lower().replace(" ", "")
        ext_by_name[name] = ep

    for prov in data.get("providers", []):
        prov_name = (prov.get("name") or "").lower().replace(" ", "")
        # Determine prefix based on provider name keywords
        prov_name_lower = (prov.get("name") or "").lower()
        if prov_name_lower == "opencode go" or prov_name_lower == "opencodego":
            prefix = "go/"
        elif any(kw in prov_name_lower for kw in ["opencode", "zen"]):
            prefix = "zen/"
        elif prov_name_lower == "ollama":
            prefix = ""
        else:
            prefix = ""
        if prov_name in ext_by_name:
            ep = ext_by_name[prov_name]
            ext_models = ep.get("models", [])
            if not ext_models:
                continue
            # Convert providers.json models to V2 format
            prefix = "go/" if "go" in prov_name else "zen/"
            v2_models = []
            seen_ids = set()
            for em in ext_models:
                mid = em.get("id", "").strip()
                if not mid or mid in seen_ids:
                    continue
                seen_ids.add(mid)
                prefixed_id = f"{prefix}{mid}"
                v2_models.append({
                    "id": prefixed_id,
                    "name": em.get("name", mid),
                    "contextWindow": int(em.get("maxInputTokens", 128000)),
                    "supportsChat": True,
                    "supportsVision": bool(em.get("vision", False)),
                    "supportsTools": bool(em.get("toolCalling", False)),
                    "supportsCode": True,
                    "supportsEmbedding": False,
                    "supportsReasoning": True,
                    "supportsRag": True,
                    "supportsClassification": True,
                    "supportsSummary": True,
                    "supportsExtraction": True,
                    "enabled": True,
                    "visibleToUsers": True,
                    "isDefault": False,
                    "allowedRoles": [],
                    "departmentRestrictions": [],
                    "state": "available",
                    "pricingTier": "free",
                    "license": "Proprietary",
                })
            if v2_models:
                prov["models"] = v2_models


def _save_management_data(data: Dict[str, Any]) -> None:
    data["lastUpdated"] = datetime.utcnow().isoformat()
    _save_json(_MANAGEMENT_FILE, data)


def _get_health_data() -> Dict[str, Any]:
    health = _load_json(_HEALTH_FILE, {})
    if not health:
        health = {
            "providers": {},
            "models": {},
            "lastUpdated": datetime.utcnow().isoformat(),
        }
        _save_json(_HEALTH_FILE, health)
    return health


def _save_health_data(data: Dict[str, Any]) -> None:
    data["lastUpdated"] = datetime.utcnow().isoformat()
    _save_json(_HEALTH_FILE, data)


# ── Public Provider API ──────────────────────────────────────────────────────


def get_all_providers() -> List[Dict[str, Any]]:
    """Return all providers with their models."""
    data = _get_management_data()
    return data.get("providers", [])


def get_provider(provider_id: str) -> Optional[Dict[str, Any]]:
    """Get a single provider by ID."""
    for p in get_all_providers():
        if p.get("id") == provider_id:
            return p
    return None


def add_provider(
    name: str,
    vendor: str = "",
    base_url: str = "",
    api_key_env: str = "",
    description: str = "",
    icon: str = "generic",
) -> Dict[str, Any]:
    """Register a new AI provider."""
    data = _get_management_data()
    provider_id = name.lower().replace(" ", "-").replace("_", "-")
    # Ensure unique ID
    existing_ids = {p.get("id") for p in data.get("providers", [])}
    if provider_id in existing_ids:
        provider_id = f"{provider_id}-{uuid.uuid4().hex[:6]}"

    provider = {
        "id": provider_id,
        "name": name,
        "vendor": vendor or name,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "status": "disconnected",
        "description": description,
        "icon": icon,
        "order": len(data.get("providers", [])),
        "models": [],
    }
    data.setdefault("providers", []).append(provider)
    _save_management_data(data)
    _add_audit_entry("provider_added", "provider", provider_id, {
        "name": name, "vendor": vendor,
    })
    logger.info("Added provider '%s' (id=%s)", name, provider_id)
    return provider


def update_provider(provider_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update provider metadata."""
    data = _get_management_data()
    providers = data.get("providers", [])
    for p in providers:
        if p.get("id") == provider_id:
            allowed = {"name", "vendor", "base_url", "api_key_env", "description", "icon", "status"}
            old_values = {}
            for key in allowed:
                if key in updates:
                    old_values[key] = p.get(key)
                    p[key] = updates[key]
            _save_management_data(data)
            _add_audit_entry("provider_updated", "provider", provider_id, {
                "changes": updates,
            })
            return p
    return None


def delete_provider(provider_id: str) -> bool:
    """Remove a provider and all its models."""
    data = _get_management_data()
    providers = data.get("providers", [])
    new_list = [p for p in providers if p.get("id") != provider_id]
    if len(new_list) == len(providers):
        return False
    data["providers"] = new_list
    _save_management_data(data)
    _add_audit_entry("provider_removed", "provider", provider_id, {})
    return True


def reorder_providers(provider_ids: List[str]) -> bool:
    """Reorder providers by the given list of IDs."""
    data = _get_management_data()
    providers = data.get("providers", [])
    id_map = {p["id"]: p for p in providers}
    ordered = []
    for pid in provider_ids:
        if pid in id_map:
            ordered.append(id_map[pid])
    # Add any providers not in the list
    for p in providers:
        if p["id"] not in provider_ids:
            ordered.append(p)
    for i, p in enumerate(ordered):
        p["order"] = i
    data["providers"] = ordered
    _save_management_data(data)
    return True


# ── Model Catalog (Layer 2) & Metadata (Layer 3) ───────────────────────────


def get_models_by_provider(provider_id: str) -> List[Dict[str, Any]]:
    """Get all models for a provider."""
    provider = get_provider(provider_id)
    return provider.get("models", []) if provider else []


def get_model(provider_id: str, model_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific model by provider ID and model ID."""
    models = get_models_by_provider(provider_id)
    for m in models:
        if m.get("id") == model_id:
            return m
    return None


def add_model_to_provider(
    provider_id: str,
    model_id: str,
    name: str,
    contextWindow: int = 4096,
    supportsChat: bool = True,
    supportsVision: bool = False,
    supportsTools: bool = False,
    supportsCode: bool = False,
    supportsEmbedding: bool = False,
    supportsReasoning: bool = False,
    supportsRag: bool = False,
    supportsClassification: bool = False,
    supportsSummary: bool = False,
    supportsExtraction: bool = False,
    enabled: bool = True,
    visibleToUsers: bool = True,
    isDefault: bool = False,
    state: str = "available",
    pricingTier: str = "free",
    license: str = "Proprietary",
    forTasks: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Add a model to a provider."""
    data = _get_management_data()
    providers = data.get("providers", [])
    for p in providers:
        if p.get("id") == provider_id:
            model = {
                "id": model_id,
                "name": name,
                "contextWindow": contextWindow,
                "supportsChat": supportsChat,
                "supportsVision": supportsVision,
                "supportsTools": supportsTools,
                "supportsCode": supportsCode,
                "supportsEmbedding": supportsEmbedding,
                "supportsReasoning": supportsReasoning,
                "supportsRag": supportsRag,
                "supportsClassification": supportsClassification,
                "supportsSummary": supportsSummary,
                "supportsExtraction": supportsExtraction,
                "enabled": enabled,
                "visibleToUsers": visibleToUsers,
                "isDefault": isDefault,
                "allowedRoles": [],
                "departmentRestrictions": [],
                "state": state,
                "pricingTier": pricingTier,
                "license": license,
                "forTasks": forTasks or [],
            }
            p.setdefault("models", []).append(model)
            _save_management_data(data)
            _add_audit_entry("model_added", "model", model_id, {
                "providerId": provider_id,
                "name": name,
            })
            return model
    return None


def update_model(
    provider_id: str, model_id: str, updates: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Update model metadata."""
    data = _get_management_data()
    for p in data.get("providers", []):
        if p.get("id") == provider_id:
            for m in p.get("models", []):
                if m.get("id") == model_id:
                    allowed = {
                        "name", "contextWindow", "supportsChat", "supportsVision",
                        "supportsTools", "supportsCode", "supportsEmbedding",
                        "supportsReasoning", "supportsRag", "supportsClassification",
                        "supportsSummary", "supportsExtraction", "enabled",
                        "visibleToUsers", "isDefault", "allowedRoles",
                        "departmentRestrictions", "state", "pricingTier",
                        "license", "forTasks",
                    }
                    old_values = {}
                    for key in updates:
                        if key in allowed:
                            if key not in old_values:
                                old_values[key] = m.get(key)
                            m[key] = updates[key]
                    _save_management_data(data)
                    _add_audit_entry("model_updated", "model", model_id, {
                        "providerId": provider_id,
                        "changes": updates,
                    })
                    return m
    return None


def remove_model_from_provider(provider_id: str, model_id: str) -> bool:
    """Remove a model from a provider."""
    data = _get_management_data()
    for p in data.get("providers", []):
        if p.get("id") == provider_id:
            old_len = len(p.get("models", []))
            p["models"] = [m for m in p.get("models", []) if m.get("id") != model_id]
            if len(p["models"]) < old_len:
                _save_management_data(data)
                _add_audit_entry("model_removed", "model", model_id, {
                    "providerId": provider_id,
                })
                return True
            return False
    return False


# ── Model Activation (Layer 5) ─────────────────────────────────────────────


def set_model_state(provider_id: str, model_id: str, state: str) -> Optional[Dict[str, Any]]:
    """Set model activation state: active, inactive, maintenance, retired, etc."""
    if state not in MODEL_STATES:
        return None
    return update_model(provider_id, model_id, {"state": state, "enabled": state == "active"})


def set_model_enabled(provider_id: str, model_id: str, enabled: bool) -> Optional[Dict[str, Any]]:
    """Enable or disable a model."""
    return update_model(provider_id, model_id, {"enabled": enabled})


# ── Chat Visibility Control (Layer 6) ──────────────────────────────────────


def set_model_visibility(provider_id: str, model_id: str, visible: bool) -> Optional[Dict[str, Any]]:
    """Toggle whether a model appears in the chat model selector."""
    return update_model(provider_id, model_id, {"visibleToUsers": visible})


def get_visible_chat_models(user_role: str = "general_user", user_department: str = "") -> List[Dict[str, Any]]:
    """Get models that should appear in the chat picker for a given user."""
    visible_models = []
    for p in get_all_providers():
        for m in p.get("models", []):
            # Must be installed/enabled
            if not m.get("enabled", False):
                continue
            if not m.get("visibleToUsers", False):
                continue
            if m.get("state") not in ("active", "installed"):
                continue
            # Must support chat
            if not m.get("supportsChat", False):
                continue
            # Role check
            allowed_roles = m.get("allowedRoles", [])
            if allowed_roles and user_role not in allowed_roles:
                continue
            # Department check
            dept_restrictions = m.get("departmentRestrictions", [])
            if dept_restrictions and user_department not in dept_restrictions:
                continue
            visible_models.append({
                **m,
                "provider_name": p.get("name"),
                "provider_id": p.get("id"),
            })
    return visible_models


# ── Role-Based Access (Layer 7) ──────────────────────────────────────────────


def set_model_allowed_roles(
    provider_id: str, model_id: str, roles: List[str]
) -> Optional[Dict[str, Any]]:
    """Set which roles can access a model."""
    invalid = [r for r in roles if r not in VALID_ROLES]
    if invalid:
        logger.warning("Invalid roles: %s", invalid)
    valid_roles = [r for r in roles if r in VALID_ROLES]
    return update_model(provider_id, model_id, {"allowedRoles": valid_roles})


def set_model_department_restrictions(
    provider_id: str, model_id: str, departments: List[str]
) -> Optional[Dict[str, Any]]:
    """Set which departments can access a model (empty = all)."""
    invalid = [d for d in departments if d not in ZETDC_DEPARTMENTS]
    if invalid:
        logger.warning("Invalid departments: %s", invalid)
    valid_depts = [d for d in departments if d in ZETDC_DEPARTMENTS]
    return update_model(provider_id, model_id, {"departmentRestrictions": valid_depts})


# ── Task-to-Model Mapping (Layer 11) ─────────────────────────────────────────


def get_task_mapping() -> Dict[str, Any]:
    """Get the current task-to-model mapping."""
    data = _get_management_data()
    return data.get("taskMapping", {})


def set_task_mapping(task_type: str, provider_id: str, model_id: str) -> bool:
    """Assign a specific model to a task type."""
    if task_type not in TASK_TYPES:
        return False
    data = _get_management_data()
    data.setdefault("taskMapping", {})
    data["taskMapping"][task_type] = {
        "providerId": provider_id,
        "modelId": model_id,
    }
    _save_management_data(data)
    _add_audit_entry("task_mapping_updated", "task", task_type, {
        "providerId": provider_id,
        "modelId": model_id,
    })
    return True


def remove_task_mapping(task_type: str) -> bool:
    """Remove a task-to-model mapping (revert to automatic)."""
    if task_type not in TASK_TYPES:
        return False
    data = _get_management_data()
    data.setdefault("taskMapping", {})
    if task_type in data["taskMapping"]:
        del data["taskMapping"][task_type]
        _save_management_data(data)
        return True
    return False


# ── Intelligent Model Selection (Layer 12) ───────────────────────────────────


def is_automatic_routing_enabled() -> bool:
    """Check if automatic model routing is enabled."""
    data = _get_management_data()
    return data.get("automaticRouting", True)


def set_automatic_routing(enabled: bool) -> None:
    """Enable or disable automatic model routing."""
    data = _get_management_data()
    data["automaticRouting"] = enabled
    _save_management_data(data)
    _add_audit_entry("automatic_routing", "system", "routing", {
        "enabled": enabled,
    })


def select_best_model_for_task(
    task_type: str,
    user_role: str = "general_user",
    user_department: str = "",
) -> Optional[Dict[str, Any]]:
    """Intelligently select the best model for a given task.

    Uses: 1) explicit task mapping, 2) automatic routing rules, 3) fallback.
    """
    # 1. Check explicit task mapping
    mapping = get_task_mapping()
    if task_type in mapping:
        entry = mapping[task_type]
        model = get_model(entry["providerId"], entry["modelId"])
        if model and model.get("enabled"):
            return {**model, "provider_id": entry["providerId"], "selection": "explicit_mapping"}

    # 2. Automatic routing
    if is_automatic_routing_enabled() and task_type in AUTOMATIC_ROUTING_RULES:
        rules = AUTOMATIC_ROUTING_RULES[task_type]
        candidates = []
        for p in get_all_providers():
            for m in p.get("models", []):
                if not m.get("enabled"):
                    continue
                if not m.get("visibleToUsers"):
                    continue
                # Check capabilities
                caps = rules.get("priority_capabilities", [])
                if caps:
                    for cap in caps:
                        cap_key = f"supports{cap.capitalize()}"
                        if m.get(cap_key, False):
                            candidates.append({
                                **m,
                                "provider_id": p.get("id"),
                                "provider_name": p.get("name"),
                                "score": _score_model_for_caps(m, caps),
                            })
        if candidates:
            # Sort by score descending
            candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
            best = candidates[0]
            # Preferred family boost
            preferred = rules.get("preferred_family")
            if preferred:
                for c in candidates:
                    if preferred.lower() in c.get("id", "").lower() or preferred.lower() in c.get("name", "").lower():
                        return {**c, "selection": "automatic_routing", "reason": rules.get("description", "")}
            return {**best, "selection": "automatic_routing", "reason": rules.get("description", "")}

    # 3. Fallback to first enabled chat model
    for p in get_all_providers():
        for m in p.get("models", []):
            if m.get("enabled") and m.get("supportsChat"):
                return {**m, "provider_id": p.get("id"), "selection": "fallback"}

    return None


def _score_model_for_caps(model: Dict[str, Any], capabilities: List[str]) -> int:
    """Score a model based on how many required capabilities it supports."""
    score = 0
    for cap in capabilities:
        cap_key = f"supports{cap.capitalize()}"
        if model.get(cap_key, False):
            score += 10
    # Bonus for larger context
    ctx = model.get("contextWindow", 0)
    if ctx > 100000:
        score += 5
    elif ctx > 32000:
        score += 3
    elif ctx > 8000:
        score += 1
    return score


# ── Health Monitoring (Layer 13) ────────────────────────────────────────────


def record_health_ping(
    provider_id: str,
    model_id: Optional[str] = None,
    latency_ms: Optional[float] = None,
    success: bool = True,
    tokens_used: int = 0,
) -> None:
    """Record a health ping for a provider or model."""
    health = _get_health_data()

    window = 60  # Keep last 60 pings per entity
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "latency_ms": latency_ms,
        "success": success,
        "tokens_used": tokens_used,
    }

    # Provider health
    health.setdefault("providers", {}).setdefault(provider_id, {"pings": []})
    pp = health["providers"][provider_id]
    pp["pings"].append(entry)
    if len(pp["pings"]) > window:
        pp["pings"] = pp["pings"][-window:]

    # Model health
    if model_id:
        key = f"{provider_id}/{model_id}"
        health.setdefault("models", {}).setdefault(key, {"pings": []})
        mp = health["models"][key]
        mp["pings"].append(entry)
        if len(mp["pings"]) > window:
            mp["pings"] = mp["pings"][-window:]

    _save_health_data(health)


def compute_health_summary(
    provider_id: Optional[str] = None,
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute health summary (availability, latency, success rate, etc.)."""
    health = _get_health_data()

    if provider_id and model_id:
        key = f"{provider_id}/{model_id}"
        pings = health.get("models", {}).get(key, {}).get("pings", [])
        prefix = f"Model {model_id}"
    elif provider_id:
        pings = health.get("providers", {}).get(provider_id, {}).get("pings", [])
        prefix = f"Provider {provider_id}"
    else:
        # Aggregate all
        all_pings = []
        for pp in health.get("providers", {}).values():
            all_pings.extend(pp.get("pings", []))
        pings = all_pings
        prefix = "System"

    return _compute_stats(pings, prefix)


def compute_all_health_summaries() -> Dict[str, Any]:
    """Compute health summaries for all providers and models."""
    health = _get_health_data()
    result = {
        "providers": {},
        "models": {},
        "system": _compute_stats(
            [p for pp in health.get("providers", {}).values() for p in pp.get("pings", [])],
            "System",
        ),
    }

    for prov_id, prov_data in health.get("providers", {}).items():
        result["providers"][prov_id] = _compute_stats(prov_data.get("pings", []), f"Provider {prov_id}")

    for key, mod_data in health.get("models", {}).items():
        result["models"][key] = _compute_stats(mod_data.get("pings", []), f"Model {key}")

    return result


def _compute_stats(pings: List[Dict[str, Any]], label: str) -> Dict[str, Any]:
    """Compute statistics from a list of ping entries."""
    if not pings:
        return {
            "label": label,
            "status": "unknown",
            "totalRequests": 0,
            "successCount": 0,
            "errorCount": 0,
            "successRate": 100.0,
            "avgLatencyMs": None,
            "p95LatencyMs": None,
            "totalTokens": 0,
            "lastChecked": None,
            "recentErrors": [],
        }

    total = len(pings)
    successes = sum(1 for p in pings if p.get("success", True))
    errors = total - successes
    latencies = [p.get("latency_ms") for p in pings if p.get("latency_ms") is not None]
    total_tokens = sum(p.get("tokens_used", 0) for p in pings)

    success_rate = (successes / total * 100) if total > 0 else 100.0
    avg_latency = (sum(latencies) / len(latencies)) if latencies else None
    p95_latency = _percentile(sorted(latencies), 95) if latencies else None

    recent_errors = [
        {"timestamp": p["timestamp"], "latency_ms": p.get("latency_ms")}
        for p in pings[-10:] if not p.get("success", True)
    ]

    if errors > total * 0.5:
        status = "unhealthy"
    elif errors > total * 0.2:
        status = "degraded"
    elif total > 0:
        status = "healthy"
    else:
        status = "unknown"

    return {
        "label": label,
        "status": status,
        "totalRequests": total,
        "successCount": successes,
        "errorCount": errors,
        "successRate": round(success_rate, 2),
        "avgLatencyMs": round(avg_latency, 2) if avg_latency else None,
        "p95LatencyMs": round(p95_latency, 2) if p95_latency else None,
        "totalTokens": total_tokens,
        "lastChecked": pings[-1]["timestamp"] if pings else None,
        "recentErrors": recent_errors,
    }


def _percentile(sorted_data: List[float], percentile: int) -> float:
    """Compute the nth percentile of a sorted list."""
    if not sorted_data:
        return 0.0
    k = (percentile / 100.0) * (len(sorted_data) - 1)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


# ── Model Marketplace (Layer 9) ──────────────────────────────────────────────


def get_marketplace_catalog() -> List[Dict[str, Any]]:
    """Return available models from the marketplace for installation."""
    catalog = []
    for p in get_all_providers():
        provider_name = p.get("name", "")
        for m in p.get("models", []):
            state = m.get("state", "available")
            if state in ("installed", "active"):
                continue  # Already installed
            catalog.append({
                "modelId": m.get("id"),
                "modelName": m.get("name"),
                "providerId": p.get("id"),
                "providerName": provider_name,
                "contextWindow": m.get("contextWindow", 4096),
                "capabilities": _model_capabilities_list(m),
                "pricingTier": m.get("pricingTier", "free"),
                "license": m.get("license", "Proprietary"),
                "state": state,
            })
    return catalog


def _model_capabilities_list(model: Dict[str, Any]) -> List[str]:
    """Return list of supported capability names."""
    caps = []
    mapping = {
        "supportsChat": "chat",
        "supportsVision": "vision",
        "supportsTools": "tools",
        "supportsCode": "code",
        "supportsReasoning": "reasoning",
        "supportsEmbedding": "embedding",
        "supportsRag": "rag",
        "supportsClassification": "classification",
        "supportsSummary": "summary",
        "supportsExtraction": "extraction",
    }
    for key, label in mapping.items():
        if model.get(key, False):
            caps.append(label)
    return caps


# ── Full Catalog Export ──────────────────────────────────────────────────────


def get_full_catalog() -> Dict[str, Any]:
    """Export the entire model management catalog for the frontend."""
    data = _get_management_data()
    providers = data.get("providers", [])
    task_mapping = data.get("taskMapping", {})

    enriched_providers = []
    for p in providers:
        models = []
        for m in p.get("models", []):
            models.append({
                **m,
                "capabilities": _model_capabilities_list(m),
            })
        health = compute_health_summary(provider_id=p.get("id"))
        enriched_providers.append({
            **p,
            "models": models,
            "health": health,
        })

    # Compute task mapping with model info
    enriched_task_mapping = {}
    for task_type, mapping_entry in task_mapping.items():
        prov_id = mapping_entry.get("providerId")
        mod_id = mapping_entry.get("modelId")
        model_data = get_model(prov_id, mod_id)
        enriched_task_mapping[task_type] = {
            "providerId": prov_id,
            "modelId": mod_id,
            "modelName": model_data.get("name") if model_data else None,
            "providerName": get_provider(prov_id).get("name") if get_provider(prov_id) else None,
        }

    return {
        "providers": enriched_providers,
        "taskMapping": enriched_task_mapping,
        "automaticRouting": data.get("automaticRouting", True),
        "taskTypes": TASK_TYPES,
        "validRoles": VALID_ROLES,
        "validDepartments": ZETDC_DEPARTMENTS,
        "validCapabilities": VALID_CAPABILITIES,
        "automaticRoutingRules": AUTOMATIC_ROUTING_RULES,
        "marketplace": get_marketplace_catalog(),
    }
