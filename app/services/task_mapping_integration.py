"""
task_mapping_integration.py — Task Mapping Integration Guide

This module provides decorators and helpers for ensuring all features
use the centralized Task Mapping system from Model Management.

Usage:
    from app.services.task_mapping_integration import use_task_mapping
    
    @use_task_mapping("chat")
    async def chat_endpoint(..., resolved_model: str):
        # resolved_model is automatically set based on task mapping
        ...
"""

import functools
import logging
from typing import Optional, Callable, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.routers.deps import get_db, get_current_user
from app.services.model_management_service import get_task_mapping
from app.services.model_resolver_service import resolve_model

logger = logging.getLogger(__name__)


def use_task_mapping(task_type: str):
    """
    Decorator that automatically resolves models based on task mapping.
    
    Injects 'resolved_model' and 'model_source' kwargs into the decorated function.
    
    Example:
        @router.post("/api/chat")
        @use_task_mapping("chat")
        async def chat_endpoint(..., resolved_model: str, model_source: str):
            # resolved_model is the model ID to use
            # model_source explains how it was selected
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get db from kwargs if available
            db = kwargs.get('db')
            if not db and 'db' in kwargs:
                # Try to get from Depends
                from app.routers.deps import get_db
                db = await get_db().__anext__()
            
            if db:
                try:
                    # Check task mapping first
                    mapping = await get_task_mapping(db, task_type)
                    if mapping and mapping.get("modelId"):
                        kwargs['resolved_model'] = mapping["modelId"]
                        kwargs['model_source'] = f"task_mapping:{task_type}"
                        kwargs['task_mapping'] = mapping
                        logger.debug(f"Using task mapping for {task_type}: {mapping['modelId']}")
                        return await func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Failed to get task mapping for {task_type}: {e}")
                
                # Fall back to model resolver
                try:
                    resolved = await resolve_model(
                        db,
                        task_type=task_type,
                        user_role=kwargs.get('user_role'),
                        user_department=kwargs.get('user_department'),
                    )
                    kwargs['resolved_model'] = resolved['model_id']
                    kwargs['model_source'] = resolved['source']
                    kwargs['task_mapping'] = None
                    logger.debug(f"Using resolved model for {task_type}: {resolved['model_id']}")
                except Exception as e:
                    logger.warning(f"Failed to resolve model for {task_type}: {e}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def get_model_for_task(
    db: AsyncSession,
    task_type: str,
    user_role: Optional[str] = None,
    user_department: Optional[str] = None,
    preferred_model: Optional[str] = None,
) -> dict:
    """
    Get the appropriate model for a task, checking task mapping first.
    
    This is the recommended way to get a model in any feature endpoint.
    
    Args:
        db: Database session
        task_type: The task type (e.g., 'chat', 'summary', 'vision')
        user_role: User's role for RBAC
        user_department: User's department
        preferred_model: User-preferred model (overrides task mapping)
        
    Returns:
        Dict with model_id, provider_id, source, and capabilities
    """
    # Priority 1: User preferred model
    if preferred_model:
        return {
            "model_id": preferred_model,
            "provider_id": _get_provider_for_model(preferred_model),
            "source": "user_preference",
            "capabilities": [],
            "task_mapping": None,
        }
    
    # Priority 2: Task mapping from Model Management
    try:
        mapping = await get_task_mapping(db, task_type)
        if mapping and mapping.get("modelId"):
            return {
                "model_id": mapping["modelId"],
                "provider_id": mapping.get("providerId", "ollama"),
                "source": f"task_mapping:{task_type}",
                "capabilities": mapping.get("capabilities", []),
                "task_mapping": mapping,
            }
    except Exception as e:
        logger.warning(f"Failed to get task mapping for {task_type}: {e}")
    
    # Priority 3: Auto-resolve based on task and user
    try:
        resolved = await resolve_model(
            db,
            task_type=task_type,
            user_role=user_role,
            user_department=user_department,
        )
        return {
            "model_id": resolved["model_id"],
            "provider_id": resolved["provider_id"],
            "source": resolved["source"],
            "capabilities": resolved.get("capabilities", []),
            "task_mapping": None,
        }
    except Exception as e:
        logger.error(f"Failed to resolve model for {task_type}: {e}")
    
    # Ultimate fallback
    return {
        "model_id": "qwen3:4b",
        "provider_id": "ollama",
        "source": "hardcoded_fallback",
        "capabilities": ["chat"],
        "task_mapping": None,
    }


def _get_provider_for_model(model_id: str) -> str:
    """Get provider ID from model ID."""
    from app.services.gemini_service import GEMINI_MODEL_ID
    from app.services.deepseek_service import DEEPSEEK_MODEL_ID
    
    if model_id == GEMINI_MODEL_ID:
        return "gemini"
    if model_id == DEEPSEEK_MODEL_ID:
        return "deepseek"
    if model_id.startswith("zen/") or model_id.startswith("go/"):
        return "opencode"
    if model_id.startswith("huggingface/"):
        return "huggingface"
    return "ollama"


# ═══════════════════════════════════════════════════════════════════════════════
#  TASK TYPE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

TASK_TYPES = {
    "chat": "General chat/conversation",
    "summary": "Document/text summarization",
    "extraction": "Information extraction",
    "classification": "Text classification",
    "comparison": "Document comparison",
    "vision": "Image/vision analysis",
    "embedding": "Text embedding generation",
    "rag": "RAG (Retrieval Augmented Generation)",
    "code_generation": "Code generation",
    "flowchart": "Flowchart/diagram generation",
    "image_generation": "Image/logo/diagram generation from text descriptions",
    "analysis": "Document analysis",
    "transcription": "Audio transcription",
}


def get_task_type_description(task_type: str) -> str:
    """Get human-readable description of a task type."""
    return TASK_TYPES.get(task_type, "Unknown task type")


def list_task_types() -> list:
    """List all supported task types."""
    return [{"id": k, "description": v} for k, v in TASK_TYPES.items()]
