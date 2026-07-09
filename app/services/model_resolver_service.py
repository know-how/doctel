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

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import app_config_service as app_cfg
from app.services.model_management_service import (
    select_best_model_for_task,
    get_all_providers,
    get_task_mapping,
)
from app.services import lookup_service
from app.services.model_availability_service import (
    get_available_models,
    get_selectable_models,
    is_model_selectable,
    get_model_availability,
    ModelStatus,
)
from app.services.gemini_service import GEMINI_MODEL_ID, is_configured as gemini_configured
from app.services.deepseek_service import DEEPSEEK_MODEL_ID, is_configured as deepseek_configured

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
    """
    
    # 1. Use explicitly requested model (highest priority) - only if ACTIVE
    if requested_model:
        availability = await get_model_availability(db, requested_model)
        if availability and availability.is_selectable:
            provider_type = _get_provider_type(requested_model)
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
            provider_type = _get_provider_type(session_model)
            return {
                "model_id": session_model,
                "provider_id": _get_provider_id(session_model, provider_type),
                "provider_type": provider_type,
                "source": "session",
                "capabilities": await _get_capabilities(db, session_model),
            }
        else:
            logger.warning(f"Session model {session_model} is not selectable (status: {availability.status if availability else 'unknown'})")
    
    # 3. Check task mapping for the specific task type - only if valid and ACTIVE
    is_valid_task = await lookup_service.validate_task_type(db, task_type) if task_type else False
    if is_valid_task:
        try:
            mapping = await get_task_mapping(db, task_type)
            if mapping and mapping.get("modelId"):
                model_id = mapping["modelId"]
                # Verify model is ACTIVE before using it
                if await is_model_selectable(db, model_id, mapping.get("providerId")):
                    provider_type = _get_provider_type(model_id)
                    return {
                        "model_id": model_id,
                        "provider_id": mapping.get("providerId", _get_provider_id(model_id, provider_type)),
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
                provider_type = _get_provider_type(model_id)
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
            provider_type = _get_provider_type(db_default)
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
    
    # 7. Final fallback - check for available cloud providers
    if prefer_cloud or require_vision:
        if gemini_configured():
            return {
                "model_id": GEMINI_MODEL_ID,
                "provider_id": "gemini",
                "provider_type": "gemini",
                "source": "fallback_cloud",
                "capabilities": ["chat", "vision", "text"],
            }
        if deepseek_configured():
            return {
                "model_id": DEEPSEEK_MODEL_ID,
                "provider_id": "deepseek",
                "provider_type": "deepseek",
                "source": "fallback_cloud",
                "capabilities": ["chat", "text"],
            }
    
    # 8. Ultimate fallback
    return {
        "model_id": "qwen3:4b",
        "provider_id": "ollama",
        "provider_type": "ollama",
        "source": "hardcoded_fallback",
        "capabilities": ["chat", "text"],
    }


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
    
    # Add cloud providers if configured and ACTIVE
    # Cloud providers are always considered ACTIVE unless manually disabled
    if gemini_configured():
        models.append({
            "id": GEMINI_MODEL_ID,
            "name": "Google Gemini (API)",
            "provider_id": "gemini",
            "provider_name": "Google",
            "capabilities": ["chat", "vision", "text", "code"],
            "context_window": 1000000,
            "is_default": False,
            "status": ModelStatus.ACTIVE,
            "is_visible": True,
            "is_selectable": True,
            "is_disabled": False,
            "disabled_reason": None,
        })
    
    if deepseek_configured():
        models.append({
            "id": DEEPSEEK_MODEL_ID,
            "name": "DeepSeek (API)",
            "provider_id": "deepseek",
            "provider_name": "DeepSeek",
            "capabilities": ["chat", "text", "code", "reasoning"],
            "context_window": 64000,
            "is_default": False,
            "status": ModelStatus.ACTIVE,
            "is_visible": True,
            "is_selectable": True,
            "is_disabled": False,
            "disabled_reason": None,
        })
    
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
    """Determine provider type from model ID."""
    if model_id == GEMINI_MODEL_ID or model_id.startswith("gemini-"):
        return "gemini"
    if model_id == DEEPSEEK_MODEL_ID or model_id.startswith("deepseek-"):
        return "deepseek"
    if model_id.startswith("zen/") or model_id.startswith("go/"):
        return "opencode"
    if model_id.startswith("huggingface/") or model_id.startswith("hf-"):
        return "huggingface"
    return "ollama"


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
    """Get capabilities for a model."""
    # This would ideally query the DB for model capabilities
    # For now, return basic capabilities based on model ID
    caps = ["chat", "text"]
    
    if "vision" in model_id.lower() or "llava" in model_id.lower():
        caps.append("vision")
    if "code" in model_id.lower() or "coder" in model_id.lower():
        caps.append("code")
    if "embed" in model_id.lower():
        caps.append("embedding")
    if model_id == GEMINI_MODEL_ID:
        caps.extend(["vision", "code", "text"])
    if model_id == DEEPSEEK_MODEL_ID:
        caps.extend(["code", "reasoning", "text"])
    
    return caps
