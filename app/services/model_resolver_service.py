"""
model_resolver_service.py — Centralized Model Resolution Service

Provides unified model resolution for all application components.
Ensures all pages/features use the centralized Model Management system
instead of hardcoded settings.

Resolution priority:
  1. Explicitly requested model (from user/session) - if ACTIVE
  2. Task-mapped model (from DB task_mapping table) - if ACTIVE
  3. DB-configured default model (from SystemConfig) - if ACTIVE
  4. Role/department based selection (via select_best_model_for_task) - ACTIVE only
  5. Fallback to first available healthy ACTIVE model

This replaces scattered settings.default_model references throughout the codebase.

STATUS-DRIVEN RESOLUTION:
- ACTIVE: Model can be resolved and used
- INACTIVE: Model cannot be resolved (treated as unavailable)
- MAINTENANCE: Model cannot be resolved (treated as unavailable)
- RETIRED: Model cannot be resolved (treated as unavailable)
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import app_config_service as app_cfg
from app.services.model_management_service import (
    select_best_model_for_task,
    get_all_providers,
)
from app.services.config_service import get_task_mapping as cfg_get_task_mapping
from app.services.config_service import get_task_mapping_for
from app.services import lookup_service
from app.services.model_availability_service import (
    get_available_models,
    get_selectable_models,
    is_model_selectable,
    get_model_availability,
    ModelStatus,
)
from app.db.config_models import AIModel, AIProvider

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#  MODEL RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════════

async def resolve_model(
    db: AsyncSession,
    requested_model: Optional[str] = None,
    task_type: Optional[str] = None,
    user_role: Optional[str] = None,
    user_department: Optional[str] = None,
    session_model: Optional[str] = None,
    prefer_cloud: bool = False,
    require_vision: bool = False,
) -> Dict[str, Any]:
    """
    Resolve the best model to use based on all available information.
    
    This is the single entry point for model selection across the application.
    All routers should use this instead of reading settings directly.
    
    Args:
        db: Database session
        requested_model: Explicitly requested model ID (highest priority)
        task_type: Task type for mapping (e.g., 'chat', 'summary', 'vision')
        user_role: User's role for RBAC filtering
        user_department: User's department for restrictions
        session_model: Model from session state
        prefer_cloud: Prefer cloud providers over local
        require_vision: Require vision capability
        
    Returns:
        Dict with:
        - model_id: The resolved model identifier
        - provider_id: Provider identifier
        - provider_type: 'ollama', 'gemini', 'deepseek', 'zen', etc.
        - source: How the model was selected ('requested', 'task_mapping', 
                  'auto_select', 'default', 'fallback')
        - capabilities: List of model capabilities
    - api_key: Provider API key (from DB, if available)
    - base_url: Provider base URL (from DB, if available)
    """
    
    # 1. Use explicitly requested model (highest priority) - only if ACTIVE
    if requested_model:
        availability = await get_model_availability(db, requested_model)
        if availability and availability.is_selectable:
            provider_type = await _resolve_provider_type(db, requested_model)
            return {
                "model_id": requested_model,
                "provider_id": _get_provider_id(requested_model, provider_type),
                "provider_type": provider_type,
                "source": "requested",
                "capabilities": await _get_capabilities(db, requested_model),
            }
        else:
            logger.warning(f"Requested model {requested_model} is not selectable (status: {availability.status if availability else 'unknown'})")
    
    # 2. Use session model if available - only if ACTIVE
    if session_model:
        availability = await get_model_availability(db, session_model)
        if availability and availability.is_selectable:
            provider_type = await _resolve_provider_type(db, session_model)
            return {
                "model_id": session_model,
                "provider_id": _get_provider_id(session_model, provider_type),
                "provider_type": provider_type,
                "source": "session",
                "capabilities": await _get_capabilities(db, session_model),
            }
        else:
            logger.warning(f"Session model {session_model} is not selectable (status: {availability.status if availability else 'unknown'})")
    
    # 3. Check task mapping for the specific task type - via DB lookup
    is_valid_task = await lookup_service.validate_task_type(db, task_type) if task_type else False
    if is_valid_task:
        try:
            mapping = await get_task_mapping_for(task_type, db)
            if mapping and mapping.get("modelId"):
                model_id = mapping["modelId"]
                provider_id = mapping.get("providerId", "")
                if await is_model_selectable(db, model_id, provider_id):
                    provider_type = await _resolve_provider_type(db, model_id)
                    return {
                        "model_id": model_id,
                        "provider_id": provider_id or _get_provider_id(model_id, provider_type),
                        "provider_type": provider_type,
                        "source": "task_mapping",
                        "capabilities": await _get_capabilities(db, model_id),
                    }
                else:
                    logger.warning(f"Task mapping model {model_id} is not ACTIVE, skipping")
        except Exception as e:
            logger.warning(f"Failed to get task mapping for {task_type}: {e}")
    
    # 4. Use intelligent model selection if task type provided
    if task_type:
        try:
            selected = await select_best_model_for_task(
                db, 
                task_type, 
                user_role=user_role, 
                user_department=user_department
            )
            if selected and selected.get("modelId"):
                model_id = selected["modelId"]
                provider_type = await _resolve_provider_type(db, model_id)
                return {
                    "model_id": model_id,
                    "provider_id": selected.get("providerId", _get_provider_id(model_id, provider_type)),
                    "provider_type": provider_type,
                    "source": "auto_select",
                    "capabilities": await _get_capabilities(db, model_id),
                }
        except Exception as e:
            logger.warning(f"Failed to auto-select model for {task_type}: {e}")
    
    # 5. Check DB-configured default model
    try:
        db_default = await app_cfg.get_setting_str(db, "routing.default_model", "")
        if db_default:
            provider_type = await _resolve_provider_type(db, db_default)
            return {
                "model_id": db_default,
                "provider_id": _get_provider_id(db_default, provider_type),
                "provider_type": provider_type,
                "source": "db_default",
                "capabilities": await _get_capabilities(db, db_default),
            }
    except Exception as e:
        logger.warning(f"Failed to get DB default model: {e}")
    
    # 6. Fall back to Ollama text model from DB config
    try:
        ollama_model = await app_cfg.get_setting_str(db, "ollama.text_model", "qwen3:4b")
        if ollama_model:
            return {
                "model_id": ollama_model,
                "provider_id": "ollama",
                "provider_type": "ollama",
                "source": "ollama_default",
                "capabilities": ["chat", "text"],
            }
    except Exception as e:
        logger.warning(f"Failed to get Ollama default: {e}")
    
    # 7. Final fallback — query DB for any active provider as a cloud fallback
    if prefer_cloud or require_vision:
        try:
            from sqlalchemy import select as sa_sel
            active_providers = await db.execute(
                sa_sel(AIProvider).where(
                    AIProvider.is_active == True,
                    AIProvider.api_key_value.isnot(None),
                    AIProvider.api_key_value != "",
                ).order_by(AIProvider.priority).limit(1)
            )
            active_provider = active_providers.scalar_one_or_none()
            if active_provider:
                # Find the first active model for this provider
                active_models = await db.execute(
                    sa_sel(AIModel).where(
                        AIModel.provider_id == active_provider.id,
                        AIModel.state == "active",
                    ).limit(1)
                )
                active_model = active_models.scalar_one_or_none()
                if active_model:
                    return {
                        "model_id": active_model.model_id,
                        "provider_id": active_provider.provider_id,
                        "provider_type": active_provider.provider_type or "openai",
                        "source": "fallback_cloud",
                        "capabilities": await _get_capabilities(db, active_model.model_id),
                    }
        except Exception as e:
            logger.warning(f"Failed to query active provider fallback: {e}")
    
    # 8. Ultimate fallback
    return {
        "model_id": "qwen3:4b",
        "provider_id": "ollama",
        "provider_type": "ollama",
        "source": "hardcoded_fallback",
        "capabilities": ["chat", "text"],
    }


async def resolve_provider_credentials(db: AsyncSession, model_id: str, provider_id_hint: str = None) -> dict:
    """
    Resolve provider API key and base_url by following:
    model_id → ai_models → provider_id → ai_providers → api_key_value / base_url

    This is the SINGLE SOURCE OF TRUTH for provider credentials.
    
    Args:
        db: Database session
        model_id: The model identifier to resolve
        provider_id_hint: Optional provider_id from resolve_model() to ensure we use the correct provider
    
    Returns {"api_key": "", "base_url": "", "provider_id": "", "provider_name": ""}
    """
    from sqlalchemy import select as sa_sel
    logger.info("[CREDENTIALS] Resolving for model_id=%s, provider_id_hint=%s", model_id, provider_id_hint)
    try:
        # If we have a provider_id_hint from resolve_model(), use it directly
        if provider_id_hint:
            logger.info("[CREDENTIALS] Using provider_id_hint=%s", provider_id_hint)
            # Try matching by provider_id first
            result = await db.execute(sa_sel(AIProvider).where(AIProvider.provider_id == provider_id_hint).limit(1))
            provider = result.scalars().first()
            if provider:
                logger.info("[CREDENTIALS] Found provider by hint: name=%s, provider_id=%s, has_api_key=%s, base_url=%s",
                           provider.name, provider.provider_id, bool(provider.api_key_value), provider.base_url)
                return {
                    "api_key": (provider.api_key_value or "").strip(),
                    "base_url": (provider.base_url or "").strip(),
                    "provider_id": provider.provider_id or "",
                    "provider_name": provider.name or "",
                }
            # Try matching by id (in case provider_id_hint is the internal id)
            result = await db.execute(sa_sel(AIProvider).where(AIProvider.id == provider_id_hint).limit(1))
            provider = result.scalars().first()
            if provider:
                logger.info("[CREDENTIALS] Found provider by id: name=%s, provider_id=%s, has_api_key=%s, base_url=%s",
                           provider.name, provider.provider_id, bool(provider.api_key_value), provider.base_url)
                return {
                    "api_key": (provider.api_key_value or "").strip(),
                    "base_url": (provider.base_url or "").strip(),
                    "provider_id": provider.provider_id or "",
                    "provider_name": provider.name or "",
                }
            logger.warning("[CREDENTIALS] Provider hint %s not found, falling back to model lookup", provider_id_hint)
        
        # Match by exact model_id, then by LIKE
        result = await db.execute(sa_sel(AIModel).where(AIModel.model_id == model_id).limit(1))
        model = result.scalars().first()
        logger.info("[CREDENTIALS] Exact match for model_id=%s: found=%s", model_id, model is not None)
        if not model:
            bare = model_id.split("/")[-1] if "/" in model_id else model_id
            result = await db.execute(sa_sel(AIModel).where(AIModel.model_id.ilike(f"%{bare}%")).limit(1))
            model = result.scalars().first()
            logger.info("[CREDENTIALS] Fuzzy match for bare=%s: found=%s", bare, model is not None)
        if model:
            logger.info("[CREDENTIALS] Found model: id=%s, provider_id=%s", model.id, model.provider_id)
            result = await db.execute(sa_sel(AIProvider).where(AIProvider.id == model.provider_id).limit(1))
            provider = result.scalars().first()
            logger.info("[CREDENTIALS] Provider lookup: provider_id=%s, found=%s", model.provider_id, provider is not None)
            if provider:
                logger.info("[CREDENTIALS] Provider details: name=%s, provider_id=%s, has_api_key=%s, base_url=%s",
                           provider.name, provider.provider_id, bool(provider.api_key_value), provider.base_url)
                return {
                    "api_key": (provider.api_key_value or "").strip(),
                    "base_url": (provider.base_url or "").strip(),
                    "provider_id": provider.provider_id or "",
                    "provider_name": provider.name or "",
                }
        # Fallback: any provider with a key
        logger.info("[CREDENTIALS] Falling back to any provider with API key")
        result = await db.execute(sa_sel(AIProvider).where(AIProvider.api_key_value.isnot(None), AIProvider.api_key_value != "").limit(1))
        provider = result.scalars().first()
        if provider:
            logger.info("[CREDENTIALS] Fallback provider: name=%s, provider_id=%s", provider.name, provider.provider_id)
            return {
                "api_key": provider.api_key_value.strip(),
                "base_url": (provider.base_url or "").strip(),
                "provider_id": provider.provider_id or "",
                "provider_name": provider.name or "",
            }
    except Exception as e:
        logger.error("[CREDENTIALS] Exception: %s", e, exc_info=True)
    logger.info("[CREDENTIALS] Returning empty credentials")
    return {"api_key": "", "base_url": "", "provider_id": "", "provider_name": ""}


async def get_available_models_for_user(
    db: AsyncSession,
    user_role: Optional[str] = None,
    user_department: Optional[str] = None,
    include_maintenance: bool = True,
) -> List[Dict[str, Any]]:
    """
    Get all models available to a specific user based on status and RBAC.
    
    STATUS-DRIVEN FILTERING:
    - ACTIVE: Visible and selectable
    - MAINTENANCE: Visible but disabled (if include_maintenance=True)
    - INACTIVE: Hidden
    - RETIRED: Hidden
    
    Args:
        db: Database session
        user_role: User's role for RBAC filtering
        user_department: User's department for restrictions
        include_maintenance: Whether to include maintenance models (visible but disabled)
    
    Returns:
        List of model dictionaries with availability info
    """
    # Use centralized availability service
    available_models = await get_available_models(
        db, user_role, user_department, include_maintenance
    )
    
    # Convert to the expected dictionary format
    models = []
    for m in available_models:
        model_dict = {
            "id": m.model_id,
            "name": m.name,
            "provider_id": m.provider_id,
            "provider_name": m.provider_id,  # Will be populated by caller if needed
            "capabilities": m.capabilities,
            "context_window": m.context_window,
            "is_default": m.is_default,
            "status": m.status,
            "is_visible": m.is_visible,
            "is_selectable": m.is_selectable,
            "is_disabled": m.is_disabled,
            "disabled_reason": m.disabled_reason,
        }
        models.append(model_dict)
    
    # Add DB-registered providers that have valid API keys but may not have models loaded
    # These come from the ai_providers table rather than hardcoded checks
    try:
        from sqlalchemy import select as sa_sel
        db_providers = await db.execute(
            sa_sel(AIProvider).where(
                AIProvider.is_active == True,
                AIProvider.api_key_value.isnot(None),
                AIProvider.api_key_value != "",
            )
        )
        for provider in db_providers.scalars().all():
            # Check if any model from this provider is already in the list
            already_present = any(m["provider_id"] == provider.provider_id for m in models)
            if not already_present and provider.models:
                # Use the first model from this provider as the representative entry
                rep_model = provider.models[0]
                models.append({
                    "id": rep_model.model_id,
                    "name": rep_model.display_name or rep_model.model_id,
                    "provider_id": provider.provider_id,
                    "provider_name": provider.name,
                    "capabilities": await _get_capabilities(db, rep_model.model_id),
                    "context_window": rep_model.context_window or 4096,
                    "is_default": False,
                    "status": ModelStatus.ACTIVE,
                    "is_visible": True,
                    "is_selectable": True,
                    "is_disabled": False,
                    "disabled_reason": None,
                })
    except Exception as e:
        logger.warning(f"Failed to load DB providers for user availability: {e}")
    
    return models


async def get_task_recommendations(
    db: AsyncSession,
    task_type: str,
) -> List[Dict[str, Any]]:
    """
    Get recommended models for a specific task type.
    Checks task mapping and returns suitable models.
    """
    mapping = await get_task_mapping(db, task_type)
    recommendations = []
    
    if mapping:
        recommendations.append({
            "model_id": mapping.get("modelId"),
            "provider_id": mapping.get("providerId"),
            "confidence": "high",
            "source": "task_mapping",
            "reason": f"Explicitly mapped for {task_type} tasks",
        })
    
    # Get all models that support this task
    all_models = await get_available_models_for_user(db)
    for model in all_models:
        if task_type in model.get("capabilities", []):
            if not any(r["model_id"] == model["id"] for r in recommendations):
                recommendations.append({
                    "model_id": model["id"],
                    "provider_id": model["provider_id"],
                    "confidence": "medium",
                    "source": "capability_match",
                    "reason": f"Supports {task_type} capability",
                })
    
    return recommendations


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_provider_type(model_id: str) -> str:
    """Determine provider type from model ID using hardcoded patterns. Use _resolve_provider_type for DB lookups."""
    mid = model_id.lower()
    if mid.startswith("gemini-"):
        return "gemini"
    if mid.startswith("deepseek-"):
        return "deepseek"
    if mid.startswith("zen/") or mid.startswith("go/") or mid.startswith("kimi"):
        return "opencode"
    if model_id.startswith("huggingface/") or model_id.startswith("hf-"):
        return "huggingface"
    return "ollama"


async def _resolve_provider_type(db: AsyncSession, model_id: str) -> str:
    """Resolve provider type by checking DB-managed models first, then falling back to name patterns."""
    # 1) Check DB-managed models
    try:
        result = await db.execute(
            select(AIModel).where(AIModel.model_id == model_id)
        )
        model = result.scalar_one_or_none()
        if model and model.provider_id:
            prov_result = await db.execute(
                select(AIProvider).where(AIProvider.id == model.provider_id)
            )
            provider = prov_result.scalar_one_or_none()
            if provider:
                provider_type = (provider.provider_type or "").strip().lower()
                vendor = (provider.vendor or "").lower()
                if "gemini" in vendor or "google" in vendor:
                    return "gemini"
                if "deepseek" in vendor:
                    return "deepseek"
                if "opencode" in vendor:
                    return "opencode"
                if "huggingface" in vendor:
                    return "huggingface"
                if "openai" in vendor:
                    return "opencode"  # OpenAI-compatible → treat as opencode router
                if "anthropic" in vendor:
                    return "opencode"  # Anthropic → opencode router
                # Use the provider_type field if vendor is unknown but provider_type is set
                if provider_type and provider_type in ("ollama", "gemini", "deepseek", "opencode", "huggingface"):
                    return provider_type
                # Fallback to pattern matching on model_id for unknown vendors
                return _get_provider_type(model_id)
    except Exception:
        pass
    # 2) Fallback to name patterns
    return _get_provider_type(model_id)


def _get_provider_id(model_id: str, provider_type: str) -> str:
    """Get provider ID from model ID and type."""
    if provider_type == "gemini":
        return "gemini"
    if provider_type == "deepseek":
        return "deepseek"
    if provider_type == "opencode":
        return "opencode"
    if provider_type == "huggingface":
        return "huggingface"
    return "ollama"


async def _get_capabilities(db: AsyncSession, model_id: str) -> List[str]:
    """Get capabilities for a model — queries DB first, then falls back to name patterns."""
    # 1) Check DB-managed model capabilities
    try:
        result = await db.execute(
            select(AIModel).where(AIModel.model_id == model_id)
        )
        model = result.scalar_one_or_none()
        if model:
            caps = ["chat", "text"]
            if model.supports_vision:
                caps.append("vision")
            if model.supports_code:
                caps.append("code")
            if model.supports_embedding:
                caps.append("embedding")
            if model.supports_reasoning:
                caps.append("reasoning")
            if model.supports_tools:
                caps.append("tools")
            if model.supports_rag:
                caps.append("rag")
            if model.supports_summary:
                caps.append("summary")
            return caps
    except Exception:
        pass
    
    # 2) Fallback to name patterns
    caps = ["chat", "text"]
    if "vision" in model_id.lower() or "llava" in model_id.lower():
        caps.append("vision")
    if "code" in model_id.lower() or "coder" in model_id.lower():
        caps.append("code")
    if "embed" in model_id.lower():
        caps.append("embedding")
    
    return caps
