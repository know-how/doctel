"""
model_management_service.py — DocTel Enterprise Model Management (DB-Backed)

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

All data stored in MySQL via config_service.py — no more JSON file I/O.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.config_models import (
    AIProvider,
    AIModel,
    TaskMapping,
    HealthRecord,
)
from app.services import config_service as cfg
from app.services.model_availability_service import ModelStatus

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

VALID_CAPABILITIES = [
    "chat", "vision", "tools", "code", "reasoning",
    "embedding", "rag", "classification", "summary",
    "extraction", "audio", "comparison",
]

# ── Provider Templates ───────────────────────────────────────────────────────
# Pre-configured provider templates for common AI providers

PROVIDER_TEMPLATES = {
    "openai": {
        "name": "OpenAI",
        "vendor": "OpenAI",
        "provider_type": "openai",
        "base_url": "https://api.openai.com/v1",
        "models_endpoint": "https://api.openai.com/v1/models",
        "chat_endpoint": "https://api.openai.com/v1/chat/completions",
        "messages_endpoint": "",
        "embeddings_endpoint": "https://api.openai.com/v1/embeddings",
        "health_endpoint": "",
        "icon": "openai",
    },
    "anthropic": {
        "name": "Anthropic",
        "vendor": "Anthropic",
        "provider_type": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "models_endpoint": "",
        "chat_endpoint": "",
        "messages_endpoint": "https://api.anthropic.com/v1/messages",
        "embeddings_endpoint": "",
        "health_endpoint": "",
        "icon": "anthropic",
    },
    "opencode_go": {
        "name": "OpenCode Go",
        "vendor": "OpenCode",
        "provider_type": "openai",
        "base_url": "https://opencode.ai/zen/go/v1",
        "models_endpoint": "https://opencode.ai/zen/go/v1/models",
        "chat_endpoint": "https://opencode.ai/zen/go/v1/chat/completions",
        "messages_endpoint": "https://opencode.ai/zen/go/v1/messages",
        "embeddings_endpoint": "",
        "health_endpoint": "",
        "icon": "opencode",
    },
    "opencode_zen": {
        "name": "OpenCode Zen",
        "vendor": "OpenCode",
        "provider_type": "openai",
        "base_url": "https://opencode.ai/zen/v1",
        "models_endpoint": "https://opencode.ai/zen/v1/models",
        "chat_endpoint": "https://opencode.ai/zen/v1/chat/completions",
        "messages_endpoint": "https://opencode.ai/zen/v1/messages",
        "embeddings_endpoint": "",
        "health_endpoint": "",
        "icon": "opencode",
    },
    "ollama": {
        "name": "Ollama",
        "vendor": "Ollama",
        "provider_type": "openai",
        "base_url": "http://localhost:11434/v1",
        "models_endpoint": "http://localhost:11434/v1/models",
        "chat_endpoint": "http://localhost:11434/v1/chat/completions",
        "messages_endpoint": "",
        "embeddings_endpoint": "http://localhost:11434/v1/embeddings",
        "health_endpoint": "http://localhost:11434/api/tags",
        "icon": "ollama",
    },
    "gemini": {
        "name": "Google Gemini",
        "vendor": "Google",
        "provider_type": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models_endpoint": "",
        "chat_endpoint": "",
        "messages_endpoint": "",
        "embeddings_endpoint": "",
        "health_endpoint": "",
        "icon": "gemini",
    },
    "deepseek": {
        "name": "DeepSeek",
        "vendor": "DeepSeek",
        "provider_type": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "models_endpoint": "https://api.deepseek.com/v1/models",
        "chat_endpoint": "https://api.deepseek.com/v1/chat/completions",
        "messages_endpoint": "",
        "embeddings_endpoint": "",
        "health_endpoint": "",
        "icon": "deepseek",
    },
}


def get_provider_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Get a provider template by ID."""
    return PROVIDER_TEMPLATES.get(template_id)


def list_provider_templates() -> List[Dict[str, Any]]:
    """List all available provider templates."""
    return [
        {"id": k, "name": v["name"], "vendor": v["vendor"], "icon": v["icon"]}
        for k, v in PROVIDER_TEMPLATES.items()
    ]

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE-DRIVEN CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
#
# The following hardcoded enums have been moved to database lookup tables:
# - VALID_ROLES        → roles table (use lookup_service.get_valid_roles(db))
# - ZETDC_DEPARTMENTS  → departments table (use lookup_service.get_zetdc_departments(db))
# - TASK_TYPES         → task_types table (use lookup_service.get_task_types_list(db))
# - MODEL_STATES       → model_statuses table (use lookup_service.get_model_states_list(db))
#
# HEALTH_STATUSES remains as a system enum (operational states).
#
# Import lookup_service for database-driven configuration:
#   from app.services import lookup_service
#   roles = await lookup_service.get_valid_roles(db)
#   is_valid = await lookup_service.validate_role(db, "admin")
# ═══════════════════════════════════════════════════════════════════════════════

HEALTH_STATUSES = ["healthy", "degraded", "unhealthy", "unknown"]

# Backward compatibility: lazy-loaded database values
# These will be populated from the database on first use
_valid_roles_cache: List[str] = []
_departments_cache: List[str] = []
_task_types_cache: List[str] = []
_model_states_cache: List[str] = []


async def _load_config_from_db(db: AsyncSession) -> None:
    """Load configuration from database into memory cache."""
    global _valid_roles_cache, _departments_cache, _task_types_cache, _model_states_cache
    from app.services import lookup_service
    _valid_roles_cache = await lookup_service.get_valid_roles(db)
    _departments_cache = await lookup_service.get_zetdc_departments(db)
    _task_types_cache = await lookup_service.get_task_types_list(db)
    _model_states_cache = await lookup_service.get_model_states_list(db)


def get_valid_roles() -> List[str]:
    """Get valid roles. Loads from cache or returns empty list if not loaded."""
    return _valid_roles_cache


def get_departments() -> List[str]:
    """Get departments. Loads from cache or returns empty list if not loaded."""
    return _departments_cache


def get_task_types() -> List[str]:
    """Get task types. Loads from cache or returns empty list if not loaded."""
    return _task_types_cache


def get_model_states() -> List[str]:
    """Get model states. Loads from cache or returns empty list if not loaded."""
    return _model_states_cache


# Deprecated: Use lookup_service directly for database-driven validation
async def validate_task_type(db: AsyncSession, task_type: str) -> bool:
    """Validate if a task type exists in the database."""
    from app.services import lookup_service
    return await lookup_service.validate_task_type(db, task_type)



# ═══════════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _provider_to_dict(provider: AIProvider, include_models: bool = True,
                       include_key: bool = False) -> dict:
    """Convert an AIProvider ORM instance to the dict shape expected by routers."""
    d = {
        "id": provider.provider_id,
        "name": provider.name,
        "vendor": provider.vendor,
        "base_url": provider.base_url,
        "status": provider.status,
        "visibleToUsers": getattr(provider, "visible_to_users", True),
        "description": provider.description,
        "icon": provider.icon,
        "order": provider.sort_order,
        "providerType": provider.provider_type,
        "modelsEndpoint": provider.models_endpoint,
        "chatEndpoint": provider.chat_endpoint,
        "messagesEndpoint": provider.messages_endpoint,
        "embeddingsEndpoint": provider.embeddings_endpoint,
        "healthEndpoint": provider.health_endpoint,
    }
    if include_key:
        d["api_key_value"] = provider.api_key_value
    if include_models:
        d["models"] = [_model_to_dict(m) for m in (provider.models or [])]
    else:
        d["models"] = []
    return d


def _model_to_dict(model: AIModel) -> dict:
    """Convert an AIModel ORM instance to the dict shape expected by routers."""
    return {
        "id": model.model_id,
        "name": model.display_name,
        "contextWindow": model.context_window,
        "supportsChat": model.supports_chat,
        "supportsVision": model.supports_vision,
        "supportsTools": model.supports_tools,
        "supportsCode": model.supports_code,
        "supportsEmbedding": model.supports_embedding,
        "supportsReasoning": model.supports_reasoning,
        "supportsRag": model.supports_rag,
        "supportsClassification": model.supports_classification,
        "supportsSummary": model.supports_summary,
        "supportsExtraction": model.supports_extraction,
        "supportsAudio": model.supports_audio,
        "supportsComparison": model.supports_comparison,
        "state": model.state,
        "visibleToUsers": getattr(model, "visible_to_users", True),
        "endpointType": model.endpoint_type,
        "isDefault": model.is_default,
        "pricingTier": model.pricing_tier,
        "license": model.license,
        "allowedRoles": json.loads(model.allowed_roles) if model.allowed_roles else [],
        "departmentRestrictions": json.loads(model.department_restrictions) if model.department_restrictions else [],
        "forTasks": json.loads(model.for_tasks) if model.for_tasks else [],
    }


async def _get_provider_orm(provider_id: str, db: AsyncSession) -> Optional[AIProvider]:
    """Get provider ORM instance by provider_id string."""
    res = await db.execute(
        select(AIProvider).where(AIProvider.provider_id == provider_id)
    )
    return res.scalar_one_or_none()


async def _get_model_orm(provider_id: str, model_id: str,
                          db: AsyncSession) -> Optional[AIModel]:
    """Get model ORM instance by provider_id + model_id strings."""
    provider = await _get_provider_orm(provider_id, db)
    if not provider:
        return None
    res = await db.execute(
        select(AIModel).where(
            AIModel.provider_id == provider.id,
            AIModel.model_id == model_id,
        )
    )
    return res.scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT & GOVERNANCE
# ═══════════════════════════════════════════════════════════════════════════════

async def get_audit_log(db: AsyncSession, limit: int = 100,
                         action: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve audit log entries."""
    entries = await cfg.get_audit_log(db=db, action=action, limit=limit)
    return [e.to_dict() for e in entries]


# ═══════════════════════════════════════════════════════════════════════════════
#  PROVIDER MANAGEMENT (Layer 1)
# ═══════════════════════════════════════════════════════════════════════════════

async def get_all_providers(db: AsyncSession) -> List[Dict[str, Any]]:
    """Get all providers with their models."""
    providers = await cfg.get_all_providers(db)
    result = []
    for p in providers:
        d = _provider_to_dict(p, include_models=True)
        result.append(d)
    return result


async def get_provider(db: AsyncSession, provider_id: str) -> Optional[Dict[str, Any]]:
    """Get a single provider with its models."""
    provider = await _get_provider_orm(provider_id, db)
    if not provider:
        return None
    return _provider_to_dict(provider, include_models=True, include_key=True)


async def add_provider(
    db: AsyncSession,
    name: str,
    vendor: str = "",
    base_url: str = "",
    api_key_value: str = "",
    description: str = "",
    icon: str = "generic",
    provider_type: str = "openai",
    models_endpoint: str = "",
    chat_endpoint: str = "",
    messages_endpoint: str = "",
    embeddings_endpoint: str = "",
    health_endpoint: str = "",
    visible_to_users: bool = True,
    sort_order: int = 0,
) -> Dict[str, Any]:
    """Register a new AI provider with flexible endpoint configuration."""
    provider_id = name.lower().replace(" ", "-").replace("_", "-")
    provider = await cfg.add_provider(
        db=db,
        provider_id=provider_id,
        name=name,
        vendor=vendor or name,
        base_url=base_url,
        api_key_value=api_key_value,
        description=description,
        icon=icon,
        sort_order=sort_order,
        provider_type=provider_type,
        models_endpoint=models_endpoint,
        chat_endpoint=chat_endpoint,
        messages_endpoint=messages_endpoint,
        embeddings_endpoint=embeddings_endpoint,
        health_endpoint=health_endpoint,
        visible_to_users=visible_to_users,
    )
    return _provider_to_dict(provider, include_models=True)


async def update_provider(db: AsyncSession, provider_id: str,
                           updates: dict) -> Optional[Dict[str, Any]]:
    """Update a provider's metadata."""
    provider = await cfg.update_provider(db, provider_id, updates)
    if not provider:
        return None
    return _provider_to_dict(provider, include_models=True)


async def delete_provider(db: AsyncSession, provider_id: str) -> bool:
    """Delete a provider and all its models."""
    return await cfg.delete_provider(db, provider_id)


async def reorder_providers(db: AsyncSession, provider_ids: List[str]) -> bool:
    """Reorder providers by setting sort_order."""
    for idx, pid in enumerate(provider_ids):
        prov = await _get_provider_orm(pid, db)
        if prov:
            prov.sort_order = idx
    await db.commit()
    return True


# ═══════════════════════════════════════════════════════════════════════════════
#  MODEL CRUD (Layers 2, 3, 4)
# ═══════════════════════════════════════════════════════════════════════════════

async def get_models_by_provider(db: AsyncSession, provider_id: str) -> List[Dict[str, Any]]:
    """List all models for a provider."""
    models = await cfg.get_models_by_provider_id(provider_id, db)
    return [_model_to_dict(m) for m in models]


async def get_model(db: AsyncSession, provider_id: str,
                     model_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific model by provider_id and model_id."""
    model = await _get_model_orm(provider_id, model_id, db)
    if not model:
        return None
    return _model_to_dict(model)


async def add_model_to_provider(
    db: AsyncSession,
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
    supportsAudio: bool = False,
    supportsComparison: bool = False,
    state: str = "available",
    pricingTier: str = "free",
    license: str = "Proprietary",
    forTasks: Optional[list] = None,
    isDefault: bool = False,
) -> Optional[Dict[str, Any]]:
    """Add a model to a provider."""
    capabilities = {
        "chat": supportsChat,
        "vision": supportsVision,
        "tools": supportsTools,
        "code": supportsCode,
        "embedding": supportsEmbedding,
        "reasoning": supportsReasoning,
        "rag": supportsRag,
        "classification": supportsClassification,
        "summary": supportsSummary,
        "extraction": supportsExtraction,
        "audio": supportsAudio,
        "comparison": supportsComparison,
    }
    try:
        model = await cfg.add_model(
            db=db,
            provider_id_str=provider_id,
            model_id=model_id,
            display_name=name,
            context_window=contextWindow,
            capabilities=capabilities,
            state=state,
            pricing_tier=pricingTier,
            license=license,
            for_tasks=forTasks or [],
            is_default=isDefault,
        )
        return _model_to_dict(model)
    except ValueError:
        return None


async def update_model(db: AsyncSession, provider_id: str, model_id: str,
                        updates: dict) -> Optional[Dict[str, Any]]:
    """Update a model's metadata."""
    # Map camelCase keys from frontend to snake_case DB columns
    key_map = {
        "name": "display_name",
        "contextWindow": "context_window",
        "supportsChat": "supports_chat",
        "supportsVision": "supports_vision",
        "supportsTools": "supports_tools",
        "supportsCode": "supports_code",
        "supportsEmbedding": "supports_embedding",
        "supportsReasoning": "supports_reasoning",
        "supportsRag": "supports_rag",
        "supportsClassification": "supports_classification",
        "supportsSummary": "supports_summary",
        "supportsExtraction": "supports_extraction",
        "supportsAudio": "supports_audio",
        "supportsComparison": "supports_comparison",
        "isDefault": "is_default",
        "pricingTier": "pricing_tier",
        "allowedRoles": "allowed_roles",
        "departmentRestrictions": "department_restrictions",
        "forTasks": "for_tasks",
        "visibleToUsers": "visible_to_users",
    }
    db_updates = {}
    for k, v in updates.items():
        col = key_map.get(k, k)
        db_updates[col] = v
    model = await cfg.update_model(db, provider_id, model_id, db_updates)
    if not model:
        return None
    return _model_to_dict(model)


async def remove_model_from_provider(db: AsyncSession, provider_id: str,
                                      model_id: str) -> bool:
    """Remove a model from a provider."""
    return await cfg.delete_model(db, provider_id, model_id)


# ═══════════════════════════════════════════════════════════════════════════════
#  MODEL ACTIVATION (Layer 5)
# ═══════════════════════════════════════════════════════════════════════════════

async def set_model_state(db: AsyncSession, provider_id: str, model_id: str,
                           state: str) -> Optional[Dict[str, Any]]:
    """Set model activation state."""
    model = await cfg.update_model(db, provider_id, model_id, {"state": state})
    if not model:
        return None
    return _model_to_dict(model)


async def set_model_visibility(db: AsyncSession, provider_id: str, model_id: str,
                                visible_to_users: bool) -> Optional[Dict[str, Any]]:
    """Set whether a model is visible to end users."""
    model = await cfg.update_model(db, provider_id, model_id,
                                    {"visible_to_users": visible_to_users})
    if not model:
        return None
    return _model_to_dict(model)


async def set_provider_visibility(db: AsyncSession, provider_id: str,
                                   visible_to_users: bool) -> Optional[Dict[str, Any]]:
    """Set whether a provider is visible to end users."""
    provider = await _get_provider_orm(provider_id, db)
    if not provider:
        return None
    provider.visible_to_users = visible_to_users
    await db.commit()
    await db.refresh(provider)
    return _provider_to_dict(provider, include_models=False)


# ═══════════════════════════════════════════════════════════════════════════════
#  ROLE-BASED ACCESS (Layer 6) & DEPARTMENT RESTRICTIONS (Layer 7)
# ═══════════════════════════════════════════════════════════════════════════════

async def set_model_allowed_roles(db: AsyncSession, provider_id: str, model_id: str,
                                   roles: List[str]) -> Optional[Dict[str, Any]]:
    """Set which roles can access a model."""
    model = await cfg.update_model(db, provider_id, model_id,
                                    {"allowed_roles": json.dumps(roles)})
    if not model:
        return None
    return _model_to_dict(model)


async def set_model_department_restrictions(
    db: AsyncSession, provider_id: str, model_id: str,
    departments: List[str],
) -> Optional[Dict[str, Any]]:
    """Set which departments can access a model."""
    model = await cfg.update_model(db, provider_id, model_id,
                                    {"department_restrictions": json.dumps(departments)})
    if not model:
        return None
    return _model_to_dict(model)


# ═══════════════════════════════════════════════════════════════════════════════
#  TASK-TO-MODEL MAPPING (Layer 11)
# ═══════════════════════════════════════════════════════════════════════════════

async def get_task_mapping(db: AsyncSession) -> Dict[str, Any]:
    """Get the task-to-model mapping."""
    return await cfg.get_task_mapping(db)


async def set_task_mapping(db: AsyncSession, task_type: str, provider_id: str,
                            model_id: str) -> bool:
    """Assign a model to a task type."""
    from app.services import lookup_service
    if not await lookup_service.validate_task_type(db, task_type):
        return False
    await cfg.set_task_mapping(db, task_type, provider_id, model_id)
    return True


async def remove_task_mapping(db: AsyncSession, task_type: str) -> bool:
    """Remove a task-to-model mapping."""
    from app.services import lookup_service
    if not await lookup_service.validate_task_type(db, task_type):
        return False
    return await cfg.delete_task_mapping(db, task_type)


# ═══════════════════════════════════════════════════════════════════════════════
#  INTELLIGENT MODEL SELECTION (Layer 12)
# ═══════════════════════════════════════════════════════════════════════════════

async def is_automatic_routing_enabled(db: AsyncSession) -> bool:
    """Check if automatic routing is enabled (stored in SystemConfig)."""
    val = await cfg.get_config_bool("routing.automatic", db, default=True)
    return val


async def set_automatic_routing(db: AsyncSession, enabled: bool) -> None:
    """Enable or disable automatic model routing."""
    await cfg.set_config("routing.automatic", enabled, db,
                          description="Automatic model routing enabled/disabled")


async def select_best_model_for_task(
    db: AsyncSession,
    task_type: str,
    user_role: str = "general_user",
    user_department: str = "",
) -> Optional[Dict[str, Any]]:
    """Select the best model for a given task using routing rules.
    
    STATUS-DRIVEN SELECTION:
    - Only ACTIVE models are eligible for auto routing
    - INACTIVE, MAINTENANCE, and RETIRED models are excluded
    """
    # 1. Check explicit task mapping - only if model is ACTIVE
    mapping = await cfg.get_task_mapping_for(task_type, db)
    if mapping and mapping.get("isActive"):
        provider_id = mapping["providerId"]
        model_id = mapping["modelId"]
        model_obj = await _get_model_orm(provider_id, model_id, db)
        # Model must be ACTIVE to be used (not just enabled)
        if model_obj and model_obj.state in [ModelStatus.ACTIVE, ModelStatus.INSTALLED, ModelStatus.AVAILABLE]:
            # Check role/dept restrictions
            allowed = json.loads(model_obj.allowed_roles) if model_obj.allowed_roles else []
            dept_restr = json.loads(model_obj.department_restrictions) if model_obj.department_restrictions else []
            if (not allowed or user_role in allowed) and (not dept_restr or user_department in dept_restr):
                # Get provider name
                provider = await _get_provider_orm(provider_id, db)
                return {
                    "providerId": provider_id,
                    "providerName": provider.name if provider else provider_id,
                    "modelId": model_id,
                    "modelName": model_obj.display_name,
                    "source": "task_mapping",
                }

    # 2. Automatic routing: find best model by priority capabilities
    # Note: routing rules are now managed via DB task_mapping table
    rules = {}
    priority_caps = rules.get("priority_capabilities", [])
    preferred_family = rules.get("preferred_family")

    # Query for selectable models (active, installed, available — not inactive/retired)
    query = select(AIModel).where(
        AIModel.state.in_([ModelStatus.ACTIVE, ModelStatus.INSTALLED, ModelStatus.AVAILABLE]),
    )

    res = await db.execute(query)
    candidates: List[AIModel] = list(res.scalars().all())

    # Score each candidate
    def _score(m: AIModel) -> int:
        score = 0
        for cap in priority_caps:
            col = getattr(m, f"supports_{cap}", None)
            if col:
                score += 2 if col else 0
        # Bonus for preferred family
        if preferred_family:
            prov = None
            # Need to check provider name for family matching
            for c in candidates:
                if c.id == m.id:
                    # We already have the model, need provider
                    pass
        return score

    scored = []
    for m in candidates:
        # Check role/dept
        allowed = json.loads(m.allowed_roles) if m.allowed_roles else []
        dept_restr = json.loads(m.department_restrictions) if m.department_restrictions else []
        if allowed and user_role not in allowed:
            continue
        if dept_restr and user_department not in dept_restr:
            continue
        score = _score(m)
        # Bonus for preferred family
        if preferred_family:
            prov = await _get_provider_orm_by_pk(m.provider_id, db)
            if prov and preferred_family in prov.provider_id.lower():
                score += 1
        scored.append((score, m))

    if not scored:
        return None

    scored.sort(key=lambda x: -x[0])
    best = scored[0][1]
    prov = await _get_provider_orm_by_pk(best.provider_id, db)

    return {
        "providerId": prov.provider_id if prov else str(best.provider_id),
        "providerName": prov.name if prov else "",
        "modelId": best.model_id,
        "modelName": best.display_name,
        "source": "automatic_routing",
    }


async def _get_provider_orm_by_pk(pk: int, db: AsyncSession) -> Optional[AIProvider]:
    """Get provider ORM instance by primary key."""
    res = await db.execute(select(AIProvider).where(AIProvider.id == pk))
    return res.scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════════════════════
#  HEALTH MONITORING (Layer 13)
# ═══════════════════════════════════════════════════════════════════════════════

async def record_health_ping(
    db: AsyncSession,
    provider_id: str,
    model_id: Optional[str] = None,
    latency_ms: Optional[float] = None,
    success: bool = True,
    tokens_used: int = 0,
) -> None:
    """Record a health ping."""
    await cfg.add_health_record(
        db=db,
        provider_id=provider_id,
        model_id=model_id,
        latency_ms=latency_ms,
        success=success,
        tokens_used=tokens_used,
    )


async def compute_health_summary(
    db: AsyncSession,
    provider_id: Optional[str] = None,
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute health summary for a provider or model."""
    records = await cfg.get_health_history(db, provider_id=provider_id, limit=20)
    if model_id:
        records = [r for r in records if r.model_id == model_id]

    if not records:
        return {
            "status": "unknown",
            "totalPings": 0,
            "successRate": 0,
            "avgLatencyMs": None,
            "lastChecked": None,
        }

    successes = sum(1 for r in records if r.success)
    latencies = [r.latency_ms for r in records if r.latency_ms is not None]

    return {
        "status": "healthy" if successes == len(records) else "degraded" if successes > 0 else "unhealthy",
        "totalPings": len(records),
        "successRate": round(successes / len(records), 2),
        "avgLatencyMs": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "lastChecked": records[0].checked_at.isoformat() if records[0].checked_at else None,
    }


async def compute_all_health_summaries(db: AsyncSession) -> Dict[str, Any]:
    """Compute health summaries for all providers and models."""
    providers = await cfg.get_all_providers(db)
    result = {}
    for prov in providers:
        prov_summary = await compute_health_summary(db, provider_id=prov.provider_id)
        models_list = []
        for model in (prov.models or []):
            m_summary = await compute_health_summary(db, provider_id=prov.provider_id,
                                                      model_id=model.model_id)
            models_list.append({
                "modelId": model.model_id,
                "modelName": model.display_name,
                **m_summary,
            })
        result[prov.provider_id] = {
            **prov_summary,
            "models": models_list,
        }
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  MODEL MARKETPLACE (Layer 9)
# ═══════════════════════════════════════════════════════════════════════════════

def _model_capabilities_list(model_dict: dict) -> List[str]:
    """Extract list of capability names from a model dict."""
    caps = []
    cap_map = {
        "supportsChat": "chat", "supportsVision": "vision", "supportsTools": "tools",
        "supportsCode": "code", "supportsEmbedding": "embedding",
        "supportsReasoning": "reasoning", "supportsRag": "rag",
        "supportsClassification": "classification", "supportsSummary": "summary",
        "supportsExtraction": "extraction", "supportsAudio": "audio",
        "supportsComparison": "comparison",
    }
    for key, name in cap_map.items():
        if model_dict.get(key, False):
            caps.append(name)
    return caps


async def get_marketplace_catalog(db: AsyncSession) -> List[Dict[str, Any]]:
    """Get available models from the marketplace catalog.

    Note: Hardcoded marketplace data has been removed.
    All provider and model data is now managed through the database.
    Returns an empty list; providers add models directly via the DB.
    """
    _ = db  # DB session kept for future extensibility
    return []


def _validate_provider_url(base_url: str) -> tuple[bool, str]:
    """Validate that a provider URL is properly formatted.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not base_url or not base_url.strip():
        return False, "Provider URL is required"
    
    url = base_url.strip()
    
    # Check for protocol
    if not url.startswith(("http://", "https://")):
        return False, "Provider URL must begin with http:// or https://"
    
    # Basic URL format check
    if "://" not in url:
        return False, "Invalid URL format"
    
    return True, ""


async def test_provider_connection(
    base_url: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    models_endpoint: Optional[str] = None,
    chat_endpoint: Optional[str] = None,
    messages_endpoint: Optional[str] = None,
) -> Dict[str, Any]:
    """Test connectivity to an AI provider endpoint(s).

    Makes lightweight API calls to validate the configured endpoints.
    Tests multiple endpoints if configured (models, chat, messages).
    Returns a dict with success status, latency_ms, and endpoint test results.
    """
    import time
    import httpx

    # Use specific endpoints if provided, otherwise fall back to base_url
    test_urls = []
    endpoint_results = {}
    
    if models_endpoint:
        test_urls.append(("models", models_endpoint))
    elif base_url:
        test_urls.append(("models", f"{base_url.rstrip('/')}/models"))
    
    if chat_endpoint:
        test_urls.append(("chat", chat_endpoint))
    
    if messages_endpoint:
        test_urls.append(("messages", messages_endpoint))

    if not test_urls:
        return {
            "success": False,
            "latencyMs": 0,
            "message": "No endpoints configured to test",
            "endpoints": {},
        }

    # Only add Authorization header if api_key is provided
    # Ollama and local providers don't require API keys
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    all_success = True
    total_latency = 0

    for endpoint_name, url in test_urls:
        # Validate URL
        is_valid, error_msg = _validate_provider_url(url)
        if not is_valid:
            endpoint_results[endpoint_name] = {
                "success": False,
                "message": error_msg,
            }
            all_success = False
            continue

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # For chat/messages endpoints, just do a HEAD request or OPTIONS
                if endpoint_name in ("chat", "messages"):
                    resp = await client.options(url, headers=headers)
                else:
                    resp = await client.get(url, headers=headers)

            elapsed_ms = int((time.monotonic() - start) * 1000)
            total_latency += elapsed_ms

            if resp.status_code < 500:
                endpoint_results[endpoint_name] = {
                    "success": True,
                    "statusCode": resp.status_code,
                    "latencyMs": elapsed_ms,
                    "message": "Connected",
                }
            else:
                endpoint_results[endpoint_name] = {
                    "success": False,
                    "statusCode": resp.status_code,
                    "latencyMs": elapsed_ms,
                    "message": f"Server error: {resp.status_code}",
                }
                all_success = False

        except httpx.ConnectError:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            endpoint_results[endpoint_name] = {
                "success": False,
                "latencyMs": elapsed_ms,
                "message": f"Connection refused",
            }
            all_success = False
        except httpx.TimeoutException:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            endpoint_results[endpoint_name] = {
                "success": False,
                "latencyMs": elapsed_ms,
                "message": "Connection timed out",
            }
            all_success = False
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            endpoint_results[endpoint_name] = {
                "success": False,
                "latencyMs": elapsed_ms,
                "message": str(e),
            }
            all_success = False

    return {
        "success": all_success,
        "latencyMs": total_latency // len(test_urls) if test_urls else 0,
        "message": "All endpoints connected" if all_success else "Some endpoints failed",
        "endpoints": endpoint_results,
    }


async def fetch_provider_models(
    base_url: str,
    api_key: Optional[str] = None,
    db: Optional[AsyncSession] = None,
    provider_id: Optional[str] = None,
    models_endpoint: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch available models from a provider's API and synchronize with database.

    Calls the configured models endpoint (or /v1/models fallback), fetches the model list,
    and synchronizes the results with the database:
    - New models are added
    - Existing models are updated
    - Removed models are marked as retired
    
    Args:
        base_url: Provider base URL (fallback if models_endpoint not provided)
        api_key: Optional API key
        db: Database session for synchronization
        provider_id: Provider ID for database synchronization
        models_endpoint: Specific models endpoint URL (takes precedence over base_url)
        
    Returns:
        Dict with success status, synchronization results, and any errors.
    """
    import time
    import httpx

    # Use models_endpoint if provided, otherwise construct from base_url
    url_to_fetch = models_endpoint if models_endpoint else f"{base_url.rstrip('/')}/models"
    
    # Validate URL
    is_valid, error_msg = _validate_provider_url(url_to_fetch)
    if not is_valid:
        return {
            "success": False,
            "latencyMs": 0,
            "message": error_msg,
            "newModels": 0,
            "updatedModels": 0,
            "retiredModels": 0,
        }

    start = time.monotonic()

    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url_to_fetch, headers=headers)

        elapsed_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code == 200:
            data = resp.json()
            models = data.get("data", data.get("models", []))
            
            # Synchronize with database if provider_id is provided
            sync_stats = {"new": 0, "updated": 0, "retired": 0}
            if db and provider_id and models:
                try:
                    sync_stats = await _sync_provider_models(db, provider_id, models)
                except Exception as sync_error:
                    logger.warning(f"Model sync failed for {provider_id}: {sync_error}")
            
            return {
                "success": True,
                "latencyMs": elapsed_ms,
                "models": models,
                "count": len(models),
                "added": sync_stats.get("added", 0),
                "updated": sync_stats.get("updated", 0),
                "removed": sync_stats.get("removed", 0),
                "unchanged": sync_stats.get("unchanged", 0),
                "preserved": sync_stats.get("preserved", 0),
                "providerId": provider_id,
            }
        else:
            return {
                "success": False,
                "latencyMs": elapsed_ms,
                "statusCode": resp.status_code,
                "message": f"API error: {resp.status_code} — {resp.text[:200]}",
            }

    except httpx.ConnectError:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "latencyMs": elapsed_ms,
            "message": f"Connection refused — is the service running at {url}?",
        }
    except httpx.TimeoutException:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "latencyMs": elapsed_ms,
            "message": "Connection timed out after 15s",
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "latencyMs": elapsed_ms,
            "message": str(e),
            "newModels": 0,
            "updatedModels": 0,
            "retiredModels": 0,
        }


async def _sync_provider_models(
    db: AsyncSession,
    provider_id: str,
    fetched_models: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Full provider-to-database synchronization.
    
    Performs a complete refresh where the provider catalog becomes the source of truth:
    - Preserves admin settings for existing models
    - Removes or retires models no longer in provider catalog
    - Adds new models from provider
    - Updates metadata for existing models
    
    Args:
        db: Database session
        provider_id: Provider string ID
        fetched_models: List of models from provider API
        
    Returns:
        Dict with counts of added, updated, removed, and unchanged models
    """
    from app.services import config_service as cfg
    import json
    
    stats = {"added": 0, "updated": 0, "removed": 0, "unchanged": 0, "preserved": 0}
    
    # Get existing models from database for this provider
    existing_models = await cfg.get_models_by_provider_id(provider_id, db)
    existing_by_id = {m.model_id: m for m in existing_models}
    
    # Build lookup of fetched models by ID
    fetched_by_id = {}
    for model_data in fetched_models:
        model_id = model_data.get("id") or model_data.get("modelId") or model_data.get("name", "").lower().replace(" ", "-")
        if model_id:
            fetched_by_id[model_id] = model_data
    
    fetched_ids = set(fetched_by_id.keys())
    existing_ids = set(existing_by_id.keys())
    
    # Determine what needs to change
    ids_to_add = fetched_ids - existing_ids          # New models
    ids_to_update = fetched_ids & existing_ids        # Existing models (check for changes)
    ids_to_remove = existing_ids - fetched_ids        # Obsolete models
    
    # STEP 1: Preserve admin settings before making changes
    preserved_settings = {}
    for model_id in ids_to_update:
        existing = existing_by_id[model_id]
        preserved_settings[model_id] = {
            "state": existing.state,
            "is_default": existing.is_default,
            "endpoint_type": existing.endpoint_type,
            "pricing_tier": existing.pricing_tier,
            "allowed_roles": existing.allowed_roles,
            "department_restrictions": existing.department_restrictions,
            "for_tasks": existing.for_tasks,
        }
    
    # STEP 2: Remove obsolete models (mark as retired to preserve history)
    for model_id in ids_to_remove:
        existing = existing_by_id[model_id]
        # Only mark as retired if currently active or available
        if existing.state in ("active", "available", "installed"):
            await cfg.update_model(db, provider_id, model_id, {"state": "retired"})
            stats["removed"] += 1
            logger.info(f"Model {model_id} retired (no longer in {provider_id} catalog)")
    
    # STEP 3: Add new models
    for model_id in ids_to_add:
        model_data = fetched_by_id[model_id]
        
        # Extract model info
        model_name = model_data.get("name") or model_data.get("id") or model_id
        context_window = model_data.get("context_window", 4096)
        if isinstance(context_window, str):
            try:
                context_window = int(context_window)
            except:
                context_window = 4096
        
        # Determine capabilities from provider data
        capabilities = model_data.get("capabilities", [])
        supports_chat = model_data.get("supports_chat", "chat" in capabilities or True)
        supports_vision = model_data.get("supports_vision", "vision" in capabilities or False)
        supports_code = model_data.get("supports_code", "code" in capabilities or False)
        supports_embedding = model_data.get("supports_embedding", "embedding" in capabilities or False)
        supports_reasoning = model_data.get("supports_reasoning", "reasoning" in capabilities or False)
        
        # Determine endpoint type based on provider type
        endpoint_type = "chat"  # default
        
        await cfg.add_model(
            db=db,
            provider_id_str=provider_id,
            model_id=model_id,
            display_name=model_name,
            context_window=context_window,
            capabilities={
                "chat": supports_chat,
                "vision": supports_vision,
                "code": supports_code,
                "embedding": supports_embedding,
                "reasoning": supports_reasoning,
            },
            state="active",
            pricing_tier=model_data.get("pricing_tier", "free"),
        )
        stats["added"] += 1
        logger.info(f"Model {model_id} added from {provider_id}")
    
    # STEP 4: Update existing models (preserve admin settings)
    for model_id in ids_to_update:
        model_data = fetched_by_id[model_id]
        existing = existing_by_id[model_id]
        preserved = preserved_settings[model_id]
        
        # Extract model info
        model_name = model_data.get("name") or model_data.get("id") or model_id
        context_window = model_data.get("context_window", 4096)
        if isinstance(context_window, str):
            try:
                context_window = int(context_window)
            except:
                context_window = 4096
        
        # Check what needs updating
        updates = {}
        
        # Update metadata if changed
        if existing.display_name != model_name:
            updates["display_name"] = model_name
        if existing.context_window != context_window:
            updates["context_window"] = context_window
        
        # Update capabilities if provider reports different
        capabilities = model_data.get("capabilities", [])
        supports_chat = model_data.get("supports_chat", "chat" in capabilities or True)
        supports_vision = model_data.get("supports_vision", "vision" in capabilities or False)
        supports_code = model_data.get("supports_code", "code" in capabilities or False)
        
        if existing.supports_chat != supports_chat:
            updates["supports_chat"] = supports_chat
        if existing.supports_vision != supports_vision:
            updates["supports_vision"] = supports_vision
        if existing.supports_code != supports_code:
            updates["supports_code"] = supports_code
        
        # Preserve admin settings - don't overwrite state, is_default, etc.
        # Admin settings are intentionally NOT in the updates dict
        
        if updates:
            await cfg.update_model(db, provider_id, model_id, updates)
            stats["updated"] += 1
            logger.info(f"Model {model_id} updated from {provider_id}")
        else:
            stats["unchanged"] += 1
        
        # Count preserved settings
        stats["preserved"] += 1
    
    logger.info(
        f"Provider {provider_id} sync complete: "
        f"{stats['added']} added, {stats['updated']} updated, "
        f"{stats['removed']} removed, {stats['unchanged']} unchanged"
    )
    
    return stats


async def fetch_gemini_models(
    provider: Dict[str, Any],
    db: AsyncSession,
) -> Dict[str, Any]:
    """Fetch models from Google Gemini API using correct query-param auth.

    Gemini API does NOT accept ``Authorization: Bearer`` — it requires
    ``?key={API_KEY}`` as a query parameter on every request.

    Handles:
    - Correct auth mechanism (``?key=`` query param, no Bearer header)
    - Gemini-specific response format (``response["models"]`` array)
    - ``models/`` prefix stripping from the ``name`` field
    - Model name → capability mapping (embedding, chat, vision, reasoning)
    - Sync to DB via ``_sync_provider_models`` (reuses the standard sync logic)

    Args:
        provider: Provider dict from ``get_provider()`` (must include
                  ``base_url``, ``api_key_value``, ``provider_id``, ``vendor``, etc.).
        db: Active database session.

    Returns:
        Dict with same shape as ``fetch_provider_models``.
    """
    import time
    import httpx

    base_url = (provider.get("base_url") or "").rstrip("/")
    api_key = (provider.get("api_key_value") or "").strip()
    provider_id = provider.get("provider_id") or provider.get("id") or ""

    if not base_url:
        logger.warning("[GEMINI] No base_url configured")
        return {
            "success": False,
            "latencyMs": 0,
            "message": "No base_url configured for Gemini provider",
            "count": 0,
        }
    if not api_key:
        logger.warning("[GEMINI] No API key configured")
        return {
            "success": False,
            "latencyMs": 0,
            "message": "No API key configured for Gemini provider",
            "count": 0,
        }

    # Use models_endpoint if explicitly set, otherwise base_url/models
    models_endpoint = (provider.get("models_endpoint") or "").strip()
    url = f"{models_endpoint}?key={api_key}" if models_endpoint else f"{base_url}/models?key={api_key}"

    logger.info(f"[GEMINI] Fetching models from {base_url}/models (provider={provider_id})")

    start = time.monotonic()

    try:
        headers = {"Content-Type": "application/json"}
        # NOTE: No Authorization header — Gemini API uses ?key= query param exclusively

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers)

        elapsed_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code == 200:
            data = resp.json()
            raw_models = data.get("models", [])
            logger.info(f"[GEMINI] API returned {len(raw_models)} models")

            if not raw_models:
                return {
                    "success": True,
                    "latencyMs": elapsed_ms,
                    "models": [],
                    "count": 0,
                    "message": "Gemini API returned empty models list",
                    "providerId": provider_id,
                }

            # ── Normalise Gemini models into _sync_provider_models format ──
            normalized: list[Dict[str, Any]] = []
            for m in raw_models:
                name: str = m.get("name") or ""
                display_name: str = m.get("displayName") or ""

                # Strip "models/" prefix → "gemini-2.0-flash"
                model_id = name
                if name.startswith("models/"):
                    model_id = name[len("models/"):]
                if not model_id:
                    continue

                # Friendly display name
                if not display_name:
                    display_name = model_id.replace("-", " ").title()

                # ── Capability detection by model-name pattern ──
                mlower = model_id.lower()

                if "embedding" in mlower:
                    # gemini-embedding-*, text-embedding-*
                    supports_embedding = True
                    supports_chat = False
                    supports_vision = False
                    supports_reasoning = False
                elif mlower.startswith("gemini-"):
                    supports_chat = True
                    supports_vision = True
                    supports_embedding = False
                    # Reasoning from 1.5 onward
                    supports_reasoning = any(
                        v in mlower for v in ("2.5", "2.0", "1.5")
                    )
                else:
                    supports_chat = True
                    supports_vision = True
                    supports_embedding = False
                    supports_reasoning = False

                context_window = m.get("inputTokenLimit", 8192) or 8192
                if isinstance(context_window, str):
                    try:
                        context_window = int(context_window)
                    except (ValueError, TypeError):
                        context_window = 8192

                normalized.append({
                    "id": model_id,
                    "name": display_name,
                    "context_window": context_window,
                    "supports_chat": supports_chat,
                    "supports_vision": supports_vision,
                    "supports_embedding": supports_embedding,
                    "supports_reasoning": supports_reasoning,
                })

            logger.info(
                f"[GEMINI] Normalised {len(normalized)} models — "
                f"chat={sum(1 for m in normalized if m['supports_chat'])}, "
                f"vision={sum(1 for m in normalized if m['supports_vision'])}, "
                f"embedding={sum(1 for m in normalized if m['supports_embedding'])}, "
                f"reasoning={sum(1 for m in normalized if m['supports_reasoning'])}"
            )

            # ── Sync to database via the standard sync engine ──
            sync_stats: Dict[str, int] = {
                "added": 0, "updated": 0, "removed": 0,
                "unchanged": 0, "preserved": 0,
            }
            if db and provider_id and normalized:
                try:
                    sync_stats = await _sync_provider_models(db, provider_id, normalized)
                    logger.info(
                        f"[GEMINI] Sync complete: +{sync_stats.get('added', 0)} added, "
                        f"~{sync_stats.get('updated', 0)} updated, "
                        f"-{sync_stats.get('removed', 0)} removed"
                    )
                except Exception as exc:
                    logger.warning(f"[GEMINI] Sync failed for {provider_id}: {exc}")

            return {
                "success": True,
                "latencyMs": elapsed_ms,
                "models": normalized,
                "count": len(normalized),
                "added": sync_stats.get("added", 0),
                "updated": sync_stats.get("updated", 0),
                "removed": sync_stats.get("removed", 0),
                "unchanged": sync_stats.get("unchanged", 0),
                "preserved": sync_stats.get("preserved", 0),
                "providerId": provider_id,
            }

        # ── Non-200 response ──
        try:
            error_detail = resp.text[:300]
        except Exception:
            error_detail = f"HTTP {resp.status_code}"
        logger.error(f"[GEMINI] API error: {resp.status_code} — {error_detail}")
        return {
            "success": False,
            "latencyMs": elapsed_ms,
            "statusCode": resp.status_code,
            "message": f"Gemini API error: {resp.status_code} — {error_detail}",
        }

    except httpx.ConnectError:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.error(f"[GEMINI] Connection refused — {base_url}")
        return {
            "success": False,
            "latencyMs": elapsed_ms,
            "message": f"Connection refused — check base_url: {base_url}",
        }
    except httpx.TimeoutException:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.error("[GEMINI] Connection timed out after 30s")
        return {
            "success": False,
            "latencyMs": elapsed_ms,
            "message": "Connection timed out after 30s",
        }
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.exception(f"[GEMINI] Unexpected error: {exc}")
        return {
            "success": False,
            "latencyMs": elapsed_ms,
            "message": f"Gemini fetch error: {str(exc)}",
        }


async def get_full_catalog(db: AsyncSession) -> Dict[str, Any]:
    """Get full catalog including providers, models, task mapping, and marketplace."""
    from app.services import lookup_service
    
    providers = await get_all_providers(db)
    task_mapping = await get_task_mapping(db)
    routing = await is_automatic_routing_enabled(db)
    marketplace = await get_marketplace_catalog(db)
    
    # Load database-driven configuration
    task_types = await lookup_service.get_task_type_codes(db, include_inactive=False)
    valid_roles = await lookup_service.get_role_codes(db, include_inactive=False)
    valid_departments = await lookup_service.get_department_codes(db, include_inactive=False)

    # Enrich providers with health
    enriched_providers = []
    for p in providers:
        health = await compute_health_summary(db, provider_id=p["id"])
        enriched_providers.append({**p, "health": health})

    return {
        "providers": enriched_providers,
        "taskMapping": task_mapping,
        "automaticRouting": routing,
        "taskTypes": task_types,
        "validRoles": valid_roles,
        "validDepartments": valid_departments,
        "validCapabilities": VALID_CAPABILITIES,
        "automaticRoutingRules": {},
        "marketplace": marketplace,
    }
