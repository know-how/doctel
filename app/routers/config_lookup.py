"""
config_lookup.py — Configuration Lookup API Router

Provides REST endpoints for database-driven configuration:
- Roles
- Departments
- Task Types
- Model Statuses

All endpoints are admin-protected for write operations.
Read operations are available to authenticated users.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.routers.deps import (
    get_current_user,
    get_db,
    require_role,
    User,
    HTTPException,
    JSONResponse,
)
from app.services import lookup_service

router = APIRouter(prefix="/api/config", tags=["configuration"])


# =============================================================================
# ROLES
# =============================================================================

@router.get("/roles", response_model=List[Dict[str, Any]])
async def list_roles(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all roles."""
    return await lookup_service.get_all_roles(db, include_inactive=include_inactive)


@router.get("/roles/codes", response_model=List[str])
async def list_role_codes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all role codes (for validation)."""
    return await lookup_service.get_role_codes(db, include_inactive=False)


@router.get("/roles/{role_code}", response_model=Optional[Dict[str, Any]])
async def get_role(
    role_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specific role by code."""
    role = await lookup_service.get_role_by_code(db, role_code)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.post("/roles", response_model=Dict[str, Any])
async def create_role(
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "super_admin"])),
):
    """Create a new role (admin only)."""
    try:
        return await lookup_service.add_role(
            db,
            code=payload["code"],
            name=payload["name"],
            description=payload.get("description", ""),
            is_system=payload.get("is_system", False),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/roles/{role_id}", response_model=Optional[Dict[str, Any]])
async def update_role(
    role_id: int,
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "super_admin"])),
):
    """Update a role (admin only)."""
    role = await lookup_service.update_role(db, role_id, payload)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "super_admin"])),
):
    """Delete (deactivate) a role (admin only). Cannot delete system roles."""
    success = await lookup_service.delete_role(db, role_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete role (may be a system role)")
    return {"ok": True}


# =============================================================================
# DEPARTMENTS
# =============================================================================

@router.get("/departments", response_model=List[Dict[str, Any]])
async def list_departments(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all departments."""
    return await lookup_service.get_all_departments(db, include_inactive=include_inactive)


@router.get("/departments/codes", response_model=List[str])
async def list_department_codes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all department codes (for validation)."""
    return await lookup_service.get_department_codes(db, include_inactive=False)


@router.get("/departments/{dept_code}", response_model=Optional[Dict[str, Any]])
async def get_department(
    dept_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specific department by code."""
    dept = await lookup_service.get_department_by_code(db, dept_code)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return dept


@router.post("/departments", response_model=Dict[str, Any])
async def create_department(
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "super_admin"])),
):
    """Create a new department (admin only)."""
    try:
        return await lookup_service.add_department(
            db,
            code=payload["code"],
            name=payload["name"],
            description=payload.get("description", ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/departments/{dept_id}", response_model=Optional[Dict[str, Any]])
async def update_department(
    dept_id: int,
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "super_admin"])),
):
    """Update a department (admin only)."""
    dept = await lookup_service.update_department(db, dept_id, payload)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return dept


@router.delete("/departments/{dept_id}")
async def delete_department(
    dept_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "super_admin"])),
):
    """Delete (deactivate) a department (admin only)."""
    success = await lookup_service.delete_department(db, dept_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete department")
    return {"ok": True}


# =============================================================================
# TASK TYPES
# =============================================================================

@router.get("/task-types", response_model=List[Dict[str, Any]])
async def list_task_types(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all task types."""
    return await lookup_service.get_all_task_types(db, include_inactive=include_inactive)


@router.get("/task-types/codes", response_model=List[str])
async def list_task_type_codes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all task type codes (for validation)."""
    return await lookup_service.get_task_type_codes(db, include_inactive=False)


@router.get("/task-types/{type_code}", response_model=Optional[Dict[str, Any]])
async def get_task_type(
    type_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specific task type by code."""
    tt = await lookup_service.get_task_type_by_code(db, type_code)
    if not tt:
        raise HTTPException(status_code=404, detail="Task type not found")
    return tt


@router.post("/task-types", response_model=Dict[str, Any])
async def create_task_type(
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "super_admin"])),
):
    """Create a new task type (admin only)."""
    try:
        return await lookup_service.add_task_type(
            db,
            code=payload["code"],
            name=payload["name"],
            description=payload.get("description", ""),
            display_order=payload.get("display_order", 0),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/task-types/{type_id}", response_model=Optional[Dict[str, Any]])
async def update_task_type(
    type_id: int,
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "super_admin"])),
):
    """Update a task type (admin only)."""
    tt = await lookup_service.update_task_type(db, type_id, payload)
    if not tt:
        raise HTTPException(status_code=404, detail="Task type not found")
    return tt


@router.delete("/task-types/{type_id}")
async def delete_task_type(
    type_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "super_admin"])),
):
    """Delete (deactivate) a task type (admin only)."""
    success = await lookup_service.delete_task_type(db, type_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete task type")
    return {"ok": True}


# =============================================================================
# MODEL STATUSES
# =============================================================================

@router.get("/model-statuses", response_model=List[Dict[str, Any]])
async def list_model_statuses(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all model statuses."""
    return await lookup_service.get_all_model_statuses(db, include_inactive=include_inactive)


@router.get("/model-statuses/selectable", response_model=List[Dict[str, Any]])
async def list_selectable_model_statuses(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List model statuses that allow model selection."""
    return await lookup_service.get_selectable_model_statuses(db)


@router.get("/model-statuses/codes", response_model=List[str])
async def list_model_status_codes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all model status codes (for validation)."""
    return await lookup_service.get_model_status_codes(db, include_inactive=True)


@router.get("/model-statuses/{status_code}", response_model=Optional[Dict[str, Any]])
async def get_model_status(
    status_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specific model status by code."""
    status = await lookup_service.get_model_status_by_code(db, status_code)
    if not status:
        raise HTTPException(status_code=404, detail="Model status not found")
    return status


@router.post("/model-statuses", response_model=Dict[str, Any])
async def create_model_status(
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "super_admin"])),
):
    """Create a new model status (admin only)."""
    try:
        return await lookup_service.add_model_status(
            db,
            code=payload["code"],
            name=payload["name"],
            description=payload.get("description", ""),
            is_selectable=payload.get("is_selectable", True),
            is_visible=payload.get("is_visible", True),
            display_order=payload.get("display_order", 0),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/model-statuses/{status_id}", response_model=Optional[Dict[str, Any]])
async def update_model_status(
    status_id: int,
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "super_admin"])),
):
    """Update a model status (admin only)."""
    status = await lookup_service.update_model_status(db, status_id, payload)
    if not status:
        raise HTTPException(status_code=404, detail="Model status not found")
    return status


@router.delete("/model-statuses/{status_id}")
async def delete_model_status(
    status_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "super_admin"])),
):
    """Delete a model status (admin only). Use with caution."""
    success = await lookup_service.delete_model_status(db, status_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete model status")
    return {"ok": True}


# =============================================================================
# BULK CONFIGURATION
# =============================================================================

@router.get("/all", response_model=Dict[str, List[Dict[str, Any]]])
async def get_all_configuration(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all configuration lookups in a single call."""
    return await lookup_service.get_all_configuration(db)
