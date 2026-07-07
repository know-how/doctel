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

logger = logging.getLogger(__name__)

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
            "id": "llama3.2",
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
        "api_key_env": provider.api_key_env,
        "status": provider.status,
        "description": provider.description,
        "icon": provider.icon,
        "order": provider.sort_order,
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
        "enabled": model.enabled,
        "visibleToUsers": model.visible_to_users,
        "state": model.state,
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
    return _provider_to_dict(provider, include_models=True)


async def add_provider(
    db: AsyncSession,
    name: str,
    vendor: str = "",
    base_url: str = "",
    api_key_env: str = "",
    description: str = "",
    icon: str = "generic",
) -> Dict[str, Any]:
    """Register a new AI provider."""
    provider_id = name.lower().replace(" ", "-").replace("_", "-")
    provider = await cfg.add_provider(
        db=db,
        provider_id=provider_id,
        name=name,
        vendor=vendor or name,
        base_url=base_url,
        api_key_env=api_key_env,
        description=description,
        icon=icon,
        sort_order=0,
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
    enabled: bool = True,
    visibleToUsers: bool = True,
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
            enabled=enabled,
            visible_to_users=visibleToUsers,
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
        "visibleToUsers": "visible_to_users",
        "isDefault": "is_default",
        "pricingTier": "pricing_tier",
        "allowedRoles": "allowed_roles",
        "departmentRestrictions": "department_restrictions",
        "forTasks": "for_tasks",
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


async def set_model_enabled(db: AsyncSession, provider_id: str, model_id: str,
                             enabled: bool) -> Optional[Dict[str, Any]]:
    """Set model enabled/disabled."""
    model = await cfg.update_model(db, provider_id, model_id, {"enabled": enabled})
    if not model:
        return None
    return _model_to_dict(model)


# ═══════════════════════════════════════════════════════════════════════════════
#  CHAT VISIBILITY (Layer 6)
# ═══════════════════════════════════════════════════════════════════════════════

async def set_model_visibility(db: AsyncSession, provider_id: str, model_id: str,
                                visible: bool) -> Optional[Dict[str, Any]]:
    """Toggle whether a model is visible to chat users."""
    model = await cfg.update_model(db, provider_id, model_id,
                                    {"visible_to_users": visible})
    if not model:
        return None
    return _model_to_dict(model)


async def get_visible_chat_models(db: AsyncSession, user_role: str = "general_user",
                                   user_department: str = "") -> List[Dict[str, Any]]:
    """Get models visible to chat users, filtered by role and department."""
    visible = await cfg.get_all_visible_chat_models(db)
    result = []
    for m in visible:
        # Check role restrictions
        allowed_roles = m.get("allowedRoles", [])
        if allowed_roles and user_role not in allowed_roles:
            continue
        # Check department restrictions
        dept_restrictions = m.get("departmentRestrictions", [])
        if dept_restrictions and user_department not in dept_restrictions:
            continue
        # Include provider info
        result.append(m)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  ROLE-BASED ACCESS (Layer 7) & DEPARTMENT RESTRICTIONS (Layer 8)
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
    if task_type not in TASK_TYPES:
        return False
    await cfg.set_task_mapping(db, task_type, provider_id, model_id)
    return True


async def remove_task_mapping(db: AsyncSession, task_type: str) -> bool:
    """Remove a task-to-model mapping."""
    if task_type not in TASK_TYPES:
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
    """Select the best model for a given task using routing rules."""
    # 1. Check explicit task mapping
    mapping = await cfg.get_task_mapping_for(task_type, db)
    if mapping and mapping.get("isActive"):
        provider_id = mapping["providerId"]
        model_id = mapping["modelId"]
        model_obj = await _get_model_orm(provider_id, model_id, db)
        if model_obj and model_obj.enabled:
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
    rules = AUTOMATIC_ROUTING_RULES.get(task_type, {})
    priority_caps = rules.get("priority_capabilities", [])
    preferred_family = rules.get("preferred_family")

    # Query for enabled, visible models
    query = select(AIModel).where(
        AIModel.enabled == True,  # noqa: E712
        AIModel.visible_to_users == True,  # noqa: E712
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
    
    The marketplace contains DEFAULT_MODELS_BY_PROVIDER models that are not
    yet installed in the user's DB.
    """
    # Get existing model IDs so we can exclude already-installed models
    existing_providers = await cfg.get_all_providers(db)
    installed_map: Dict[str, set] = {}
    for prov in existing_providers:
        installed_map[prov.provider_id] = set()
        for m in (prov.models or []):
            installed_map[prov.provider_id].add(m.model_id)

    catalog = []
    for prov_id, models_list in DEFAULT_MODELS_BY_PROVIDER.items():
        installed_set = installed_map.get(prov_id, set())
        for m_def in models_list:
            if m_def["id"] not in installed_set:
                entry = dict(m_def)
                entry["providerId"] = prov_id
                entry["capabilities"] = _model_capabilities_list(m_def)
                catalog.append(entry)

    return catalog


async def test_provider_connection(
    base_url: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Test connectivity to an AI provider endpoint.

    Makes a lightweight API call to validate the base_url and optional api_key.
    Returns a dict with success status, latency_ms, and any error message.
    """
    import time
    import httpx

    start = time.monotonic()
    url = base_url.rstrip("/")

    try:
        # Try the OpenAI-compatible /v1/models endpoint as a lightweight check
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{url}/models", headers=headers)

        elapsed_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code < 500:
            return {
                "success": True,
                "statusCode": resp.status_code,
                "latencyMs": elapsed_ms,
                "message": "Connection successful",
            }
        else:
            return {
                "success": False,
                "statusCode": resp.status_code,
                "latencyMs": elapsed_ms,
                "message": f"Server error: {resp.status_code}",
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
            "message": f"Connection timed out after 10s",
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "latencyMs": elapsed_ms,
            "message": str(e),
        }


async def fetch_provider_models(
    base_url: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch available models from a provider's API.

    Calls the OpenAI-compatible /v1/models endpoint and returns the model list.
    Returns a dict with success status and available models or error.
    """
    import time
    import httpx

    start = time.monotonic()
    url = base_url.rstrip("/")

    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{url}/models", headers=headers)

        elapsed_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code == 200:
            data = resp.json()
            models = data.get("data", data.get("models", []))
            return {
                "success": True,
                "latencyMs": elapsed_ms,
                "models": models,
                "count": len(models),
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
        }


async def get_full_catalog(db: AsyncSession) -> Dict[str, Any]:
    """Get full catalog including providers, models, task mapping, and marketplace."""
    providers = await get_all_providers(db)
    task_mapping = await get_task_mapping(db)
    routing = await is_automatic_routing_enabled(db)
    marketplace = await get_marketplace_catalog(db)

    # Enrich providers with health
    enriched_providers = []
    for p in providers:
        health = await compute_health_summary(db, provider_id=p["id"])
        enriched_providers.append({**p, "health": health})

    return {
        "providers": enriched_providers,
        "taskMapping": task_mapping,
        "automaticRouting": routing,
        "taskTypes": TASK_TYPES,
        "validRoles": VALID_ROLES,
        "validDepartments": ZETDC_DEPARTMENTS,
        "validCapabilities": VALID_CAPABILITIES,
        "automaticRoutingRules": AUTOMATIC_ROUTING_RULES,
        "marketplace": marketplace,
    }
