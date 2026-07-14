"""
model_availability_service.py — Centralized Model Availability Service

This is the single source of truth for model visibility and availability
across the entire DocTel platform.

Status-Driven Model Availability:
- ACTIVE: Model is visible and selectable everywhere
- INACTIVE: Model is hidden from all user-facing selectors
- MAINTENANCE: Model is visible but disabled (cannot be selected)
- RETIRED: Model is completely hidden from all selectors

All model selectors throughout the platform must use this service to ensure
consistent behavior.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config_models import AIModel, AIProvider

logger = logging.getLogger(__name__)


class ModelStatus(str, Enum):
    """Model status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"
    INSTALLED = "installed"  # Legacy/compatibility
    AVAILABLE = "available"  # Legacy/compatibility


class ModelAvailability:
    """Represents the availability state of a model."""
    
    def __init__(
        self,
        model_id: str,
        provider_id: str,
        status: str,
        name: str = "",
        capabilities: Optional[List[str]] = None,
        context_window: int = 4096,
        is_default: bool = False,
        allowed_roles: Optional[List[str]] = None,
        department_restrictions: Optional[List[str]] = None,
        pricing_tier: str = "free",
        license: str = "Proprietary",
    ):
        self.model_id = model_id
        self.provider_id = provider_id
        self.status = status
        self.name = name
        self.capabilities = capabilities or []
        self.context_window = context_window
        self.is_default = is_default
        self.allowed_roles = allowed_roles or []
        self.department_restrictions = department_restrictions or []
        self.pricing_tier = pricing_tier
        self.license = license
    
    @property
    def is_visible(self) -> bool:
        """Whether the model should appear in selectors."""
        return self.status in (ModelStatus.ACTIVE, ModelStatus.INSTALLED, ModelStatus.AVAILABLE, ModelStatus.MAINTENANCE)
    
    @property
    def is_selectable(self) -> bool:
        """Whether the model can be selected/used."""
        return self.status in (ModelStatus.ACTIVE, ModelStatus.INSTALLED, ModelStatus.AVAILABLE)
    
    @property
    def is_available_for_routing(self) -> bool:
        """Whether the model can be used by Auto Routing."""
        return self.status in (ModelStatus.ACTIVE, ModelStatus.INSTALLED, ModelStatus.AVAILABLE)
    
    @property
    def is_disabled(self) -> bool:
        """Whether the model should appear as disabled in UI."""
        return self.status == ModelStatus.MAINTENANCE
    
    @property
    def disabled_reason(self) -> Optional[str]:
        """Reason why the model is disabled (for UI display)."""
        if self.status == ModelStatus.MAINTENANCE:
            return "Under Maintenance"
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.model_id,
            "name": self.name or self.model_id,
            "providerId": self.provider_id,
            "status": self.status,
            "isVisible": self.is_visible,
            "isSelectable": self.is_selectable,
            "isDisabled": self.is_disabled,
            "disabledReason": self.disabled_reason,
            "capabilities": self.capabilities,
            "contextWindow": self.context_window,
            "isDefault": self.is_default,
            "pricingTier": self.pricing_tier,
            "license": self.license,
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE AVAILABILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

async def get_available_models(
    db: AsyncSession,
    user_role: Optional[str] = None,
    user_department: Optional[str] = None,
    include_maintenance: bool = True,
) -> List[ModelAvailability]:
    """
    Get all models available to a user based on status and RBAC.
    
    Args:
        db: Database session
        user_role: User's role for RBAC filtering
        user_department: User's department for restrictions
        include_maintenance: Whether to include maintenance models (visible but disabled)
    
    Returns:
        List of ModelAvailability objects for models that should be visible
    """
    # Query for models that are NOT inactive or retired
    visible_statuses = [ModelStatus.ACTIVE, ModelStatus.INSTALLED, ModelStatus.AVAILABLE, ModelStatus.MAINTENANCE]
    if not include_maintenance:
        visible_statuses = [ModelStatus.ACTIVE, ModelStatus.INSTALLED, ModelStatus.AVAILABLE]
    
    query = select(AIModel).join(AIProvider).where(
        AIModel.state.in_(visible_statuses),
        AIModel.visible_to_users == True,
        AIProvider.status == "active",
        AIProvider.visible_to_users == True,
    )
    
    result = await db.execute(query)
    models: List[AIModel] = list(result.scalars().all())
    
    available_models = []
    for model in models:
        # Check role restrictions
        import json
        allowed_roles = json.loads(model.allowed_roles) if model.allowed_roles else []
        if allowed_roles and user_role not in allowed_roles:
            continue
        
        # Check department restrictions
        dept_restrictions = json.loads(model.department_restrictions) if model.department_restrictions else []
        if dept_restrictions and user_department not in dept_restrictions:
            continue
        
        # Get provider info
        provider = await db.get(AIProvider, model.provider_id)
        provider_id = provider.provider_id if provider else "unknown"
        
        # Build capabilities list
        capabilities = []
        if model.supports_chat:
            capabilities.append("chat")
        if model.supports_vision:
            capabilities.append("vision")
        if model.supports_tools:
            capabilities.append("tools")
        if model.supports_code:
            capabilities.append("code")
        if model.supports_embedding:
            capabilities.append("embedding")
        if model.supports_reasoning:
            capabilities.append("reasoning")
        if model.supports_rag:
            capabilities.append("rag")
        if model.supports_classification:
            capabilities.append("classification")
        if model.supports_summary:
            capabilities.append("summary")
        if model.supports_extraction:
            capabilities.append("extraction")
        if model.supports_audio:
            capabilities.append("audio")
        if model.supports_comparison:
            capabilities.append("comparison")
        
        availability = ModelAvailability(
            model_id=model.model_id,
            provider_id=provider_id,
            status=model.state,
            name=model.display_name,
            capabilities=capabilities,
            context_window=model.context_window,
            is_default=model.is_default,
            allowed_roles=allowed_roles,
            department_restrictions=dept_restrictions,
            pricing_tier=model.pricing_tier,
            license=model.license,
        )
        available_models.append(availability)
    
    return available_models


async def get_selectable_models(
    db: AsyncSession,
    user_role: Optional[str] = None,
    user_department: Optional[str] = None,
) -> List[ModelAvailability]:
    """
    Get only ACTIVE models that can be selected and used.
    Used for Auto Routing and task assignments.
    
    Args:
        db: Database session
        user_role: User's role for RBAC filtering
        user_department: User's department for restrictions
    
    Returns:
        List of ModelAvailability objects for selectable models
    """
    all_available = await get_available_models(
        db, user_role, user_department, include_maintenance=True
    )
    return [m for m in all_available if m.is_selectable]


async def is_model_available(
    db: AsyncSession,
    model_id: str,
    provider_id: Optional[str] = None,
) -> bool:
    """
    Check if a model is available (visible in selectors).
    
    Args:
        db: Database session
        model_id: The model ID to check
        provider_id: Optional provider ID to narrow search
    
    Returns:
        True if the model is available (Active or Maintenance)
    """
    query = select(AIModel).join(AIProvider).where(
        AIModel.model_id == model_id,
        AIModel.state.in_([ModelStatus.ACTIVE, ModelStatus.MAINTENANCE]),
        AIProvider.status == "active",
    )
    
    if provider_id:
        query = query.where(AIProvider.provider_id == provider_id)
    
    result = await db.execute(query)
    # Use .first() instead of scalar_one_or_none() because the same model_id
    # can exist in multiple providers (e.g., deepseek-v4-flash-free in both
    # OpenCodeGO and DeepSeek providers)
    return result.first() is not None


async def is_model_selectable(
    db: AsyncSession,
    model_id: str,
    provider_id: Optional[str] = None,
) -> bool:
    """
    Check if a model can be selected and used.
    
    Args:
        db: Database session
        model_id: The model ID to check
        provider_id: Optional provider ID to narrow search
    
    Returns:
        True if the model is Active (can be used)
    """
    query = select(AIModel).join(AIProvider).where(
        AIModel.model_id == model_id,
        AIModel.state.in_([ModelStatus.ACTIVE, ModelStatus.INSTALLED, ModelStatus.AVAILABLE]),
        AIProvider.status == "active",
    )
    
    if provider_id:
        query = query.where(AIProvider.provider_id == provider_id)
    
    result = await db.execute(query)
    # Use .first() instead of scalar_one_or_none() because the same model_id
    # can exist in multiple providers (e.g., deepseek-v4-flash-free in both
    # OpenCodeGO and DeepSeek providers)
    return result.first() is not None


async def get_model_availability(
    db: AsyncSession,
    model_id: str,
    provider_id: Optional[str] = None,
) -> Optional[ModelAvailability]:
    """
    Get the availability information for a specific model.
    
    Args:
        db: Database session
        model_id: The model ID to look up
        provider_id: Optional provider ID to narrow search
    
    Returns:
        ModelAvailability object or None if not found
    """
    query = select(AIModel).join(AIProvider).where(
        AIModel.model_id == model_id,
    )
    
    if provider_id:
        query = query.where(AIProvider.provider_id == provider_id)
    
    result = await db.execute(query)
    # Use .first() instead of scalar_one_or_none() because the same model_id
    # can exist in multiple providers (e.g., deepseek-v4-flash-free in both
    # OpenCodeGO and DeepSeek providers)
    row = result.first()
    model: Optional[AIModel] = row[0] if row else None
    
    if not model:
        return None
    
    import json
    provider = await db.get(AIProvider, model.provider_id)
    provider_id_val = provider.provider_id if provider else "unknown"
    allowed_roles = json.loads(model.allowed_roles) if model.allowed_roles else []
    dept_restrictions = json.loads(model.department_restrictions) if model.department_restrictions else []
    
    # Build capabilities list
    capabilities = []
    if model.supports_chat:
        capabilities.append("chat")
    if model.supports_vision:
        capabilities.append("vision")
    if model.supports_tools:
        capabilities.append("tools")
    if model.supports_code:
        capabilities.append("code")
    if model.supports_embedding:
        capabilities.append("embedding")
    if model.supports_reasoning:
        capabilities.append("reasoning")
    if model.supports_rag:
        capabilities.append("rag")
    if model.supports_classification:
        capabilities.append("classification")
    if model.supports_summary:
        capabilities.append("summary")
    if model.supports_extraction:
        capabilities.append("extraction")
    if model.supports_audio:
        capabilities.append("audio")
    if model.supports_comparison:
        capabilities.append("comparison")
    
    return ModelAvailability(
        model_id=model.model_id,
        provider_id=provider_id_val,
        status=model.state,
        name=model.display_name,
        capabilities=capabilities,
        context_window=model.context_window,
        is_default=model.is_default,
        allowed_roles=allowed_roles,
        department_restrictions=dept_restrictions,
        pricing_tier=model.pricing_tier,
        license=model.license,
    )


async def filter_models_by_capability(
    db: AsyncSession,
    capability: str,
    user_role: Optional[str] = None,
    user_department: Optional[str] = None,
    only_selectable: bool = True,
) -> List[ModelAvailability]:
    """
    Get models that support a specific capability.
    
    Args:
        db: Database session
        capability: The capability to filter by (e.g., 'chat', 'vision')
        user_role: User's role for RBAC filtering
        user_department: User's department for restrictions
        only_selectable: If True, only return Active models
    
    Returns:
        List of ModelAvailability objects with the specified capability
    """
    if only_selectable:
        models = await get_selectable_models(db, user_role, user_department)
    else:
        models = await get_available_models(db, user_role, user_department, include_maintenance=True)
    
    return [m for m in models if capability in m.capabilities]


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def get_all_models_admin(
    db: AsyncSession,
) -> List[ModelAvailability]:
    """
    Get ALL models for admin view (including Inactive and Retired).
    This is for the Model Catalog admin interface only.
    
    Args:
        db: Database session
    
    Returns:
        List of ModelAvailability objects for all models
    """
    query = select(AIModel).join(AIProvider)
    result = await db.execute(query)
    models: List[AIModel] = list(result.scalars().all())
    
    all_models = []
    import json
    
    for model in models:
        provider = await db.get(AIProvider, model.provider_id)
        provider_id = provider.provider_id if provider else "unknown"
        allowed_roles = json.loads(model.allowed_roles) if model.allowed_roles else []
        dept_restrictions = json.loads(model.department_restrictions) if model.department_restrictions else []
        
        # Build capabilities list
        capabilities = []
        if model.supports_chat:
            capabilities.append("chat")
        if model.supports_vision:
            capabilities.append("vision")
        if model.supports_tools:
            capabilities.append("tools")
        if model.supports_code:
            capabilities.append("code")
        if model.supports_embedding:
            capabilities.append("embedding")
        if model.supports_reasoning:
            capabilities.append("reasoning")
        if model.supports_rag:
            capabilities.append("rag")
        if model.supports_classification:
            capabilities.append("classification")
        if model.supports_summary:
            capabilities.append("summary")
        if model.supports_extraction:
            capabilities.append("extraction")
        if model.supports_audio:
            capabilities.append("audio")
        if model.supports_comparison:
            capabilities.append("comparison")
        
        availability = ModelAvailability(
            model_id=model.model_id,
            provider_id=provider_id,
            status=model.state,
            name=model.display_name,
            capabilities=capabilities,
            context_window=model.context_window,
            is_default=model.is_default,
            allowed_roles=allowed_roles,
            department_restrictions=dept_restrictions,
            pricing_tier=model.pricing_tier,
            license=model.license,
        )
        all_models.append(availability)
    
    return all_models
