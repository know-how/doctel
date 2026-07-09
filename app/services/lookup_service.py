"""
lookup_service.py — Database-driven configuration lookup service

Replaces hardcoded enums (VALID_ROLES, ZETDC_DEPARTMENTS, TASK_TYPES, MODEL_STATES)
with database-driven lookups that can be managed through administration screens.

This service provides:
- Dynamic loading of lookup values from database
- Intelligent caching with automatic refresh
- Validation helpers for business logic
- Admin management functions
"""

from __future__ import annotations

import functools
import logging
from typing import Dict, List, Optional, Any

from sqlalchemy import select, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config_models import Role, Department, TaskType, ModelStatus

logger = logging.getLogger(__name__)

# Cache storage (simple in-memory cache)
_cache: Dict[str, Any] = {
    "roles": None,
    "departments": None,
    "task_types": None,
    "model_statuses": None,
    "_last_refresh": {},
}

CACHE_TTL_SECONDS = 60  # Refresh cache after 60 seconds


# =============================================================================
# CACHE MANAGEMENT
# =============================================================================

def _invalidate_cache(key: str) -> None:
    """Invalidate a specific cache entry."""
    _cache[key] = None
    if key in _cache["_last_refresh"]:
        del _cache["_last_refresh"][key]
    logger.debug(f"Cache invalidated: {key}")


def _invalidate_all_cache() -> None:
    """Invalidate all lookup caches."""
    for key in ["roles", "departments", "task_types", "model_statuses"]:
        _cache[key] = None
    _cache["_last_refresh"] = {}
    logger.debug("All lookup caches invalidated")


# =============================================================================
# ROLES
# =============================================================================

async def get_all_roles(db: AsyncSession, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Get all roles from database."""
    query = select(Role).order_by(asc(Role.code))
    if not include_inactive:
        query = query.where(Role.is_active == True)
    
    result = await db.execute(query)
    roles = result.scalars().all()
    return [role.to_dict() for role in roles]


async def get_role_by_code(db: AsyncSession, code: str) -> Optional[Dict[str, Any]]:
    """Get a role by its code."""
    result = await db.execute(
        select(Role).where(Role.code == code, Role.is_active == True)
    )
    role = result.scalar_one_or_none()
    return role.to_dict() if role else None


async def get_role_codes(db: AsyncSession, include_inactive: bool = False) -> List[str]:
    """Get list of role codes for validation."""
    roles = await get_all_roles(db, include_inactive)
    return [role["code"] for role in roles]


async def validate_role(db: AsyncSession, role_code: str) -> bool:
    """Validate if a role code exists and is active."""
    if not role_code:
        return False
    result = await db.execute(
        select(Role).where(Role.code == role_code, Role.is_active == True)
    )
    return result.scalar_one_or_none() is not None


async def add_role(
    db: AsyncSession,
    code: str,
    name: str,
    description: str = "",
    is_system: bool = False,
) -> Dict[str, Any]:
    """Add a new role."""
    # Check for duplicate code
    existing = await db.execute(select(Role).where(Role.code == code))
    if existing.scalar_one_or_none():
        raise ValueError(f"Role with code '{code}' already exists")
    
    role = Role(
        code=code,
        name=name,
        description=description,
        is_system=is_system,
        is_active=True,
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    _invalidate_cache("roles")
    logger.info(f"Role created: {code}")
    return role.to_dict()


async def update_role(
    db: AsyncSession,
    role_id: int,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update a role. System roles can only have name/description changed."""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        return None
    
    # System roles protection
    if role.is_system:
        allowed_updates = {k: v for k, v in updates.items() if k in ("name", "description")}
        if len(allowed_updates) != len(updates):
            logger.warning(f"Attempted to modify system role {role.code} - restricted fields ignored")
    else:
        allowed_updates = updates
    
    for key, value in allowed_updates.items():
        if hasattr(role, key):
            setattr(role, key, value)
    
    await db.commit()
    await db.refresh(role)
    
    _invalidate_cache("roles")
    logger.info(f"Role updated: {role.code}")
    return role.to_dict()


async def delete_role(db: AsyncSession, role_id: int) -> bool:
    """Delete a role (soft delete by deactivating). Cannot delete system roles."""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        return False
    
    if role.is_system:
        logger.warning(f"Cannot delete system role: {role.code}")
        return False
    
    role.is_active = False
    await db.commit()
    
    _invalidate_cache("roles")
    logger.info(f"Role deactivated: {role.code}")
    return True


# =============================================================================
# DEPARTMENTS
# =============================================================================

async def get_all_departments(db: AsyncSession, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Get all departments from database."""
    query = select(Department).order_by(asc(Department.name))
    if not include_inactive:
        query = query.where(Department.is_active == True)
    
    result = await db.execute(query)
    depts = result.scalars().all()
    return [dept.to_dict() for dept in depts]


async def get_department_by_code(db: AsyncSession, code: str) -> Optional[Dict[str, Any]]:
    """Get a department by its code."""
    result = await db.execute(
        select(Department).where(Department.code == code, Department.is_active == True)
    )
    dept = result.scalar_one_or_none()
    return dept.to_dict() if dept else None


async def get_department_codes(db: AsyncSession, include_inactive: bool = False) -> List[str]:
    """Get list of department codes for validation."""
    depts = await get_all_departments(db, include_inactive)
    return [dept["code"] for dept in depts]


async def validate_department(db: AsyncSession, dept_code: str) -> bool:
    """Validate if a department code exists and is active."""
    if not dept_code:
        return False
    result = await db.execute(
        select(Department).where(Department.code == dept_code, Department.is_active == True)
    )
    return result.scalar_one_or_none() is not None


async def add_department(
    db: AsyncSession,
    code: str,
    name: str,
    description: str = "",
) -> Dict[str, Any]:
    """Add a new department."""
    existing = await db.execute(select(Department).where(Department.code == code))
    if existing.scalar_one_or_none():
        raise ValueError(f"Department with code '{code}' already exists")
    
    dept = Department(
        code=code,
        name=name,
        description=description,
        is_active=True,
    )
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    
    _invalidate_cache("departments")
    logger.info(f"Department created: {code}")
    return dept.to_dict()


async def update_department(
    db: AsyncSession,
    dept_id: int,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update a department."""
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if not dept:
        return None
    
    for key, value in updates.items():
        if hasattr(dept, key):
            setattr(dept, key, value)
    
    await db.commit()
    await db.refresh(dept)
    
    _invalidate_cache("departments")
    logger.info(f"Department updated: {dept.code}")
    return dept.to_dict()


async def delete_department(db: AsyncSession, dept_id: int) -> bool:
    """Delete a department (soft delete by deactivating)."""
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if not dept:
        return False
    
    dept.is_active = False
    await db.commit()
    
    _invalidate_cache("departments")
    logger.info(f"Department deactivated: {dept.code}")
    return True


# =============================================================================
# TASK TYPES
# =============================================================================

async def get_all_task_types(db: AsyncSession, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Get all task types from database."""
    query = select(TaskType).order_by(asc(TaskType.display_order), asc(TaskType.name))
    if not include_inactive:
        query = query.where(TaskType.is_active == True)
    
    result = await db.execute(query)
    types = result.scalars().all()
    return [t.to_dict() for t in types]


async def get_task_type_by_code(db: AsyncSession, code: str) -> Optional[Dict[str, Any]]:
    """Get a task type by its code."""
    result = await db.execute(
        select(TaskType).where(TaskType.code == code, TaskType.is_active == True)
    )
    t = result.scalar_one_or_none()
    return t.to_dict() if t else None


async def get_task_type_codes(db: AsyncSession, include_inactive: bool = False) -> List[str]:
    """Get list of task type codes for validation."""
    types = await get_all_task_types(db, include_inactive)
    return [t["code"] for t in types]


async def validate_task_type(db: AsyncSession, code: str) -> bool:
    """Validate if a task type code exists and is active."""
    if not code:
        return False
    result = await db.execute(
        select(TaskType).where(TaskType.code == code, TaskType.is_active == True)
    )
    return result.scalar_one_or_none() is not None


async def add_task_type(
    db: AsyncSession,
    code: str,
    name: str,
    description: str = "",
    display_order: int = 0,
) -> Dict[str, Any]:
    """Add a new task type."""
    existing = await db.execute(select(TaskType).where(TaskType.code == code))
    if existing.scalar_one_or_none():
        raise ValueError(f"Task type with code '{code}' already exists")
    
    tt = TaskType(
        code=code,
        name=name,
        description=description,
        display_order=display_order,
        is_active=True,
    )
    db.add(tt)
    await db.commit()
    await db.refresh(tt)
    
    _invalidate_cache("task_types")
    logger.info(f"Task type created: {code}")
    return tt.to_dict()


async def update_task_type(
    db: AsyncSession,
    type_id: int,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update a task type."""
    result = await db.execute(select(TaskType).where(TaskType.id == type_id))
    tt = result.scalar_one_or_none()
    if not tt:
        return None
    
    for key, value in updates.items():
        if hasattr(tt, key):
            setattr(tt, key, value)
    
    await db.commit()
    await db.refresh(tt)
    
    _invalidate_cache("task_types")
    logger.info(f"Task type updated: {tt.code}")
    return tt.to_dict()


async def delete_task_type(db: AsyncSession, type_id: int) -> bool:
    """Delete a task type (soft delete by deactivating)."""
    result = await db.execute(select(TaskType).where(TaskType.id == type_id))
    tt = result.scalar_one_or_none()
    if not tt:
        return False
    
    tt.is_active = False
    await db.commit()
    
    _invalidate_cache("task_types")
    logger.info(f"Task type deactivated: {tt.code}")
    return True


# =============================================================================
# MODEL STATUSES
# =============================================================================

async def get_all_model_statuses(db: AsyncSession, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Get all model statuses from database."""
    query = select(ModelStatus).order_by(asc(ModelStatus.display_order))
    if not include_inactive:
        query = query.where(ModelStatus.is_visible == True)
    
    result = await db.execute(query)
    statuses = result.scalars().all()
    return [s.to_dict() for s in statuses]


async def get_model_status_by_code(db: AsyncSession, code: str) -> Optional[Dict[str, Any]]:
    """Get a model status by its code."""
    result = await db.execute(
        select(ModelStatus).where(ModelStatus.code == code)
    )
    s = result.scalar_one_or_none()
    return s.to_dict() if s else None


async def get_model_status_codes(db: AsyncSession, include_inactive: bool = False) -> List[str]:
    """Get list of model status codes for validation."""
    statuses = await get_all_model_statuses(db, include_inactive)
    return [s["code"] for s in statuses]


async def get_selectable_model_statuses(db: AsyncSession) -> List[Dict[str, Any]]:
    """Get model statuses that allow model selection."""
    result = await db.execute(
        select(ModelStatus)
        .where(ModelStatus.is_selectable == True, ModelStatus.is_visible == True)
        .order_by(asc(ModelStatus.display_order))
    )
    statuses = result.scalars().all()
    return [s.to_dict() for s in statuses]


async def get_visible_model_statuses(db: AsyncSession) -> List[Dict[str, Any]]:
    """Get model statuses that are visible in dropdowns."""
    result = await db.execute(
        select(ModelStatus)
        .where(ModelStatus.is_visible == True)
        .order_by(asc(ModelStatus.display_order))
    )
    statuses = result.scalars().all()
    return [s.to_dict() for s in statuses]


async def validate_model_status(db: AsyncSession, code: str) -> bool:
    """Validate if a model status code exists."""
    if not code:
        return False
    result = await db.execute(select(ModelStatus).where(ModelStatus.code == code))
    return result.scalar_one_or_none() is not None


async def is_model_status_selectable(db: AsyncSession, code: str) -> bool:
    """Check if a model status allows model selection."""
    result = await db.execute(
        select(ModelStatus).where(ModelStatus.code == code, ModelStatus.is_selectable == True)
    )
    return result.scalar_one_or_none() is not None


async def add_model_status(
    db: AsyncSession,
    code: str,
    name: str,
    description: str = "",
    is_selectable: bool = True,
    is_visible: bool = True,
    display_order: int = 0,
) -> Dict[str, Any]:
    """Add a new model status."""
    existing = await db.execute(select(ModelStatus).where(ModelStatus.code == code))
    if existing.scalar_one_or_none():
        raise ValueError(f"Model status with code '{code}' already exists")
    
    status = ModelStatus(
        code=code,
        name=name,
        description=description,
        is_selectable=is_selectable,
        is_visible=is_visible,
        display_order=display_order,
    )
    db.add(status)
    await db.commit()
    await db.refresh(status)
    
    _invalidate_cache("model_statuses")
    logger.info(f"Model status created: {code}")
    return status.to_dict()


async def update_model_status(
    db: AsyncSession,
    status_id: int,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update a model status."""
    result = await db.execute(select(ModelStatus).where(ModelStatus.id == status_id))
    status = result.scalar_one_or_none()
    if not status:
        return None
    
    for key, value in updates.items():
        if hasattr(status, key):
            setattr(status, key, value)
    
    await db.commit()
    await db.refresh(status)
    
    _invalidate_cache("model_statuses")
    logger.info(f"Model status updated: {status.code}")
    return status.to_dict()


async def delete_model_status(db: AsyncSession, status_id: int) -> bool:
    """Delete a model status (hard delete - use with caution)."""
    result = await db.execute(select(ModelStatus).where(ModelStatus.id == status_id))
    status = result.scalar_one_or_none()
    if not status:
        return False
    
    await db.delete(status)
    await db.commit()
    
    _invalidate_cache("model_statuses")
    logger.info(f"Model status deleted: {status.code}")
    return True


# =============================================================================
# BULK OPERATIONS
# =============================================================================

async def get_all_configuration(db: AsyncSession) -> Dict[str, List[Dict[str, Any]]]:
    """Get all configuration lookups in a single call."""
    return {
        "roles": await get_all_roles(db),
        "departments": await get_all_departments(db),
        "task_types": await get_all_task_types(db),
        "model_statuses": await get_all_model_statuses(db),
    }


# =============================================================================
# BACKWARD COMPATIBILITY HELPERS
# =============================================================================

async def get_valid_roles(db: AsyncSession) -> List[str]:
    """Backward compatibility: Get role codes as list (like old VALID_ROLES)."""
    return await get_role_codes(db, include_inactive=False)


async def get_zetdc_departments(db: AsyncSession) -> List[str]:
    """Backward compatibility: Get department codes as list (like old ZETDC_DEPARTMENTS)."""
    return await get_department_codes(db, include_inactive=False)


async def get_task_types_list(db: AsyncSession) -> List[str]:
    """Backward compatibility: Get task type codes as list (like old TASK_TYPES)."""
    return await get_task_type_codes(db, include_inactive=False)


async def get_model_states_list(db: AsyncSession) -> List[str]:
    """Backward compatibility: Get model status codes as list (like old MODEL_STATES)."""
    return await get_model_status_codes(db, include_inactive=True)
