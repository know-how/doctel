"""
model_management.py — DocTel Enterprise Model Management API (DB-Backed)

GitHub Copilot-style model management routes covering all 14 layers.
All data is now stored in MySQL via async SQLAlchemy sessions.
"""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends
from fastapi import Path as FAPath
from sqlalchemy.ext.asyncio import AsyncSession

from app.routers.deps import (
    HTTPException,
    JSONResponse,
    Query,
    User,
    get_current_user,
    get_db,
    require_role,
    logger,
)
from app.services.model_management_service import (
    # Provider
    get_all_providers,
    get_provider,
    add_provider,
    update_provider,
    delete_provider,
    reorder_providers,
    # Models
    get_models_by_provider,
    get_model,
    add_model_to_provider,
    update_model,
    remove_model_from_provider,
    # Activation & Visibility
    set_model_state,
    set_model_enabled,
    set_model_visibility,
    get_visible_chat_models,
    # RBAC
    set_model_allowed_roles,
    set_model_department_restrictions,
    # Task Mapping
    get_task_mapping,
    set_task_mapping,
    remove_task_mapping,
    # Auto Routing
    is_automatic_routing_enabled,
    set_automatic_routing,
    select_best_model_for_task,
    # Health
    record_health_ping,
    compute_health_summary,
    compute_all_health_summaries,
    # Marketplace
    get_marketplace_catalog,
    # Audit
    get_audit_log,
    # Full catalog
    get_full_catalog,
    # Connection testing
    test_provider_connection,
    fetch_provider_models,
    TASK_TYPES,
    VALID_ROLES,
    ZETDC_DEPARTMENTS,
    MODEL_STATES,
)

router = APIRouter(prefix="/api/models/v2", tags=["model-management"])


# ═════════════════════════════════════════════════════════════════════════════
# Full Catalog
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/catalog")
async def v2_catalog(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Return the full enriched model management catalog."""
    return await get_full_catalog(db=db)


# ═════════════════════════════════════════════════════════════════════════════
# Provider CRUD (Layer 1)
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/providers")
async def v2_list_providers(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List all AI providers with their models and health."""
    providers = await get_all_providers(db)
    return {"providers": providers}


@router.get("/providers/{provider_id}")
async def v2_get_provider(
    provider_id: str = FAPath(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a single provider with its models."""
    provider = await get_provider(db, provider_id)
    if not provider:
        return JSONResponse(status_code=404, content={"error": "provider_not_found"})
    health = await compute_health_summary(db, provider_id=provider_id)
    return {"provider": {**provider, "health": health}}


@router.post("/providers")
async def v2_add_provider(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Register a new AI provider."""
    name = (payload.get("name") or "").strip()
    if not name:
        return JSONResponse(status_code=400, content={"error": "name_required"})
    provider = await add_provider(
        db=db,
        name=name,
        vendor=payload.get("vendor", ""),
        base_url=payload.get("base_url", ""),
        api_key_env=payload.get("api_key_env", ""),
        description=payload.get("description", ""),
        icon=payload.get("icon", "generic"),
    )
    return {"provider": provider}


@router.put("/providers/{provider_id}")
async def v2_update_provider(
    provider_id: str = FAPath(...),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Update a provider's metadata."""
    allowed = {"name", "vendor", "base_url", "api_key_env", "description", "icon", "status"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    result = await update_provider(db, provider_id, updates)
    if not result:
        return JSONResponse(status_code=404, content={"error": "provider_not_found"})
    return {"provider": result}


@router.delete("/providers/{provider_id}")
async def v2_delete_provider(
    provider_id: str = FAPath(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Delete a provider and all its models."""
    if not await delete_provider(db, provider_id):
        return JSONResponse(status_code=404, content={"error": "provider_not_found"})
    return {"ok": True}


@router.post("/providers/reorder")
async def v2_reorder_providers(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Reorder providers."""
    provider_ids = payload.get("providerIds", [])
    await reorder_providers(db, provider_ids)
    return {"ok": True}


# ═════════════════════════════════════════════════════════════════════════════
# Model CRUD (Layers 2, 3, 4)
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/providers/{provider_id}/models")
async def v2_list_models(
    provider_id: str = FAPath(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List all models for a provider."""
    models = await get_models_by_provider(db, provider_id)
    return {"models": models, "providerId": provider_id}


@router.get("/providers/{provider_id}/models/{model_id}")
async def v2_get_model(
    provider_id: str = FAPath(...),
    model_id: str = FAPath(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a specific model with health data."""
    model = await get_model(db, provider_id, model_id)
    if not model:
        return JSONResponse(status_code=404, content={"error": "model_not_found"})
    health = await compute_health_summary(db, provider_id=provider_id, model_id=model_id)
    return {"model": {**model, "health": health}}


@router.post("/providers/{provider_id}/models")
async def v2_add_model(
    provider_id: str = FAPath(...),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Add a model to a provider."""
    model_id = (payload.get("id") or "").strip()
    name = (payload.get("name") or "").strip()
    if not model_id or not name:
        return JSONResponse(status_code=400, content={"error": "id_and_name_required"})
    result = await add_model_to_provider(
        db=db,
        provider_id=provider_id,
        model_id=model_id,
        name=name,
        contextWindow=int(payload.get("contextWindow", 4096)),
        supportsChat=bool(payload.get("supportsChat", True)),
        supportsVision=bool(payload.get("supportsVision", False)),
        supportsTools=bool(payload.get("supportsTools", False)),
        supportsCode=bool(payload.get("supportsCode", False)),
        supportsEmbedding=bool(payload.get("supportsEmbedding", False)),
        supportsReasoning=bool(payload.get("supportsReasoning", False)),
        supportsRag=bool(payload.get("supportsRag", False)),
        supportsClassification=bool(payload.get("supportsClassification", False)),
        supportsSummary=bool(payload.get("supportsSummary", False)),
        supportsExtraction=bool(payload.get("supportsExtraction", False)),
        enabled=bool(payload.get("enabled", True)),
        visibleToUsers=bool(payload.get("visibleToUsers", True)),
        state=payload.get("state", "available"),
        pricingTier=payload.get("pricingTier", "free"),
        license=payload.get("license", "Proprietary"),
        forTasks=payload.get("forTasks"),
    )
    if not result:
        return JSONResponse(status_code=404, content={"error": "provider_not_found"})
    return {"model": result}


@router.put("/providers/{provider_id}/models/{model_id}")
async def v2_update_model(
    provider_id: str = FAPath(...),
    model_id: str = FAPath(...),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Update a model's metadata."""
    result = await update_model(db, provider_id, model_id, payload)
    if not result:
        return JSONResponse(status_code=404, content={"error": "model_not_found"})
    return {"model": result}


@router.delete("/providers/{provider_id}/models/{model_id}")
async def v2_delete_model(
    provider_id: str = FAPath(...),
    model_id: str = FAPath(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Remove a model from a provider."""
    if not await remove_model_from_provider(db, provider_id, model_id):
        return JSONResponse(status_code=404, content={"error": "model_not_found"})
    return {"ok": True}


# ═════════════════════════════════════════════════════════════════════════════
# Model Activation (Layer 5)
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/providers/{provider_id}/models/{model_id}/state")
async def v2_set_model_state(
    provider_id: str = FAPath(...),
    model_id: str = FAPath(...),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Set model activation state."""
    state = (payload.get("state") or "").strip()
    if state not in MODEL_STATES:
        return JSONResponse(status_code=400, content={
            "error": "invalid_state",
            "validStates": MODEL_STATES,
        })
    result = await set_model_state(db, provider_id, model_id, state)
    if not result:
        return JSONResponse(status_code=404, content={"error": "model_not_found"})
    return {"model": result}


@router.post("/providers/{provider_id}/models/{model_id}/toggle")
async def v2_toggle_model(
    provider_id: str = FAPath(...),
    model_id: str = FAPath(...),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Toggle model enabled/disabled."""
    enabled = bool(payload.get("enabled", True))
    result = await set_model_enabled(db, provider_id, model_id, enabled)
    if not result:
        return JSONResponse(status_code=404, content={"error": "model_not_found"})
    return {"model": result, "enabled": enabled}


# ═════════════════════════════════════════════════════════════════════════════
# Chat Visibility (Layer 6)
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/providers/{provider_id}/models/{model_id}/visibility")
async def v2_set_visibility(
    provider_id: str = FAPath(...),
    model_id: str = FAPath(...),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Toggle whether a model is visible to chat users."""
    visible = bool(payload.get("visible", True))
    result = await set_model_visibility(db, provider_id, model_id, visible)
    if not result:
        return JSONResponse(status_code=404, content={"error": "model_not_found"})
    return {"model": result, "visible": visible}


@router.get("/chat/models")
async def v2_visible_chat_models(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get models visible to the current user in chat."""
    role = getattr(user, "role", "general_user") or "general_user"
    dept = getattr(user, "department", "") or ""
    models = await get_visible_chat_models(db, user_role=role, user_department=dept)
    return {"models": models}


# ═════════════════════════════════════════════════════════════════════════════
# Role-Based Access (Layer 7) & Department Restrictions (Layer 8)
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/providers/{provider_id}/models/{model_id}/roles")
async def v2_set_roles(
    provider_id: str = FAPath(...),
    model_id: str = FAPath(...),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Set which roles can access a model."""
    roles = payload.get("roles", [])
    result = await set_model_allowed_roles(db, provider_id, model_id, roles)
    if not result:
        return JSONResponse(status_code=404, content={"error": "model_not_found"})
    return {"model": result}


@router.post("/providers/{provider_id}/models/{model_id}/departments")
async def v2_set_departments(
    provider_id: str = FAPath(...),
    model_id: str = FAPath(...),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Set which departments can access a model."""
    departments = payload.get("departments", [])
    result = await set_model_department_restrictions(db, provider_id, model_id, departments)
    if not result:
        return JSONResponse(status_code=404, content={"error": "model_not_found"})
    return {"model": result}


# ═════════════════════════════════════════════════════════════════════════════
# Task-to-Model Mapping (Layer 11)
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/task-mapping")
async def v2_get_task_mapping(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get the task-to-model mapping."""
    mapping = await get_task_mapping(db)
    return {"taskMapping": mapping, "taskTypes": TASK_TYPES}


@router.put("/task-mapping/{task_type}")
async def v2_set_task_mapping(
    task_type: str = FAPath(...),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Assign a model to a task type."""
    provider_id = (payload.get("providerId") or "").strip()
    model_id = (payload.get("modelId") or "").strip()
    if not provider_id or not model_id:
        return JSONResponse(status_code=400, content={"error": "providerId_and_modelId_required"})
    if not await set_task_mapping(db, task_type, provider_id, model_id):
        return JSONResponse(status_code=400, content={
            "error": "invalid_task_type",
            "validTaskTypes": TASK_TYPES,
        })
    return {"ok": True}


@router.delete("/task-mapping/{task_type}")
async def v2_remove_task_mapping(
    task_type: str = FAPath(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Remove a task-to-model mapping."""
    if not await remove_task_mapping(db, task_type):
        return JSONResponse(status_code=400, content={
            "error": "invalid_task_type",
            "validTaskTypes": TASK_TYPES,
        })
    return {"ok": True}


# ═════════════════════════════════════════════════════════════════════════════
# Intelligent Model Selection (Layer 12)
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/routing/status")
async def v2_routing_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get automatic routing status."""
    return {
        "automaticRouting": await is_automatic_routing_enabled(db),
    }


@router.post("/routing/toggle")
async def v2_toggle_routing(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Enable or disable automatic model routing."""
    enabled = bool(payload.get("enabled", True))
    await set_automatic_routing(db, enabled)
    return {"automaticRouting": enabled}


@router.get("/routing/select/{task_type}")
async def v2_select_model(
    task_type: str = FAPath(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Select the best model for a given task."""
    role = getattr(user, "role", "general_user") or "general_user"
    dept = getattr(user, "department", "") or ""
    model = await select_best_model_for_task(db, task_type, user_role=role, user_department=dept)
    if not model:
        return JSONResponse(status_code=404, content={"error": "no_suitable_model_found"})
    return {"model": model}


# ═════════════════════════════════════════════════════════════════════════════
# Health Monitoring (Layer 13)
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/health")
async def v2_get_health(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get health summaries for all providers and models."""
    return await compute_all_health_summaries(db)


@router.get("/health/{provider_id}")
async def v2_get_provider_health(
    provider_id: str = FAPath(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get health summary for a specific provider."""
    return await compute_health_summary(db, provider_id=provider_id)


@router.get("/health/{provider_id}/{model_id}")
async def v2_get_model_health(
    provider_id: str = FAPath(...),
    model_id: str = FAPath(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get health summary for a specific model."""
    return await compute_health_summary(db, provider_id=provider_id, model_id=model_id)


@router.post("/health/ping")
async def v2_health_ping(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Record a health ping (used by services, no auth required)."""
    provider_id = (payload.get("providerId") or "").strip()
    model_id = payload.get("modelId")
    latency_ms = payload.get("latencyMs")
    success = bool(payload.get("success", True))
    tokens_used = int(payload.get("tokensUsed", 0))
    if not provider_id:
        return JSONResponse(status_code=400, content={"error": "providerId_required"})
    await record_health_ping(db, provider_id, model_id, latency_ms, success, tokens_used)
    return {"ok": True}


# ═════════════════════════════════════════════════════════════════════════════
# Model Marketplace (Layer 9)
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/marketplace")
async def v2_marketplace(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get available models from the marketplace catalog."""
    catalog = await get_marketplace_catalog(db)
    return {"catalog": catalog}


# ═════════════════════════════════════════════════════════════════════════════
# Audit & Governance (Layer 14)
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/audit")
async def v2_audit(
    limit: int = Query(100, description="Number of audit entries"),
    action: str = Query(None, description="Filter by action type"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get the model management audit log."""
    entries = await get_audit_log(db, limit=limit, action=action)
    return {"audit": entries, "total": len(entries)}


# ═════════════════════════════════════════════════════════════════════════════
# Constants/Reference Data
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/ref")
async def v2_reference(
    user: User = Depends(require_role(["admin"])),
):
    """Get reference data (task types, roles, departments, etc.)."""
    return {
        "taskTypes": TASK_TYPES,
        "validRoles": VALID_ROLES,
        "validDepartments": ZETDC_DEPARTMENTS,
        "modelStates": MODEL_STATES,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Test Connection & Fetch Models
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/test-connection")
async def v2_test_connection(
    body: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Test connectivity to an AI provider endpoint.

    Accepts direct credentials or a providerId to look up from DB:
    ```json
    {
      "baseUrl": "http://localhost:11434",
      "apiKey": "optional-api-key",
      "model": "optional-model-name"
    }
    ```
    Or: `{"providerId": "ollama"}` to test an existing provider.
    """
    base_url = body.get("baseUrl") or ""
    api_key = body.get("apiKey") or None
    model = body.get("model") or None
    provider_id = body.get("providerId") or None

    # Resolve from DB if providerId given
    if provider_id and not base_url:
        prov = await get_provider(db, provider_id=provider_id)
        if not prov:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
        base_url = prov.get("base_url", "")
        env_var = prov.get("api_key_env", "")
        if env_var:
            api_key = os.environ.get(env_var) or api_key

    return await test_provider_connection(
        base_url=base_url,
        api_key=api_key,
        model=model,
    )


@router.post("/fetch-models")
async def v2_fetch_models(
    body: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Fetch available models from a provider's API.

    Accepts direct credentials or a providerId to look up from DB:
    ```json
    {
      "baseUrl": "https://api.openai.com/v1",
      "apiKey": "sk-..."
    }
    ```
    Or: `{"providerId": "ollama"}` to use an existing provider's config.
    """
    base_url = body.get("baseUrl") or ""
    api_key = body.get("apiKey") or None
    provider_id = body.get("providerId") or None

    # Resolve from DB if providerId given
    if provider_id and not base_url:
        prov = await get_provider(db, provider_id=provider_id)
        if not prov:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
        base_url = prov.get("base_url", "")
        env_var = prov.get("api_key_env", "")
        if env_var:
            api_key = os.environ.get(env_var) or api_key

    return await fetch_provider_models(
        base_url=base_url,
        api_key=api_key,
    )
