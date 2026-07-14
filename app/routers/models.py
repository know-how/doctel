"""
DocTel model management router.

Endpoints for listing available / installed models, querying capabilities,
resolving display labels, and pulling new models.
"""

from app.routers.deps import (
    Body,
    Depends,
    JSONResponse,
    get_current_user,
    get_db,
    User,
    DbSession,
    AsyncSession,
    settings,
    ollama,
    load_model_cache,
    update_installed_models,
    ModelsAvailableResponse,
    ModelLabelsResponse,
    logger,
)

from fastapi import APIRouter
import json
import os
from pathlib import Path

router = APIRouter(tags=["models"])


# ── Internal helpers ────────────────────────────────────────────────────────


def _is_embedding_model(model: str) -> bool:
    m = (model or "").strip().lower()
    if not m:
        return False
    embed = (settings.embed_model or "").strip().lower()
    if embed and (m == embed or m.startswith(embed + ":")):
        return True
    if "embed" in m:
        return True
    return False


def _is_generation_model(model: str) -> bool:
    if not model:
        return False
    from app.services.gemini_service import GEMINI_MODEL_ID
    from app.services.deepseek_service import DEEPSEEK_MODEL_ID
    if model == GEMINI_MODEL_ID:
        return True
    if model == DEEPSEEK_MODEL_ID:
        return True
    if model.startswith("zen/") or model.startswith("go/") or model.startswith("huggingface/"):
        return True
    return not _is_embedding_model(model)


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/api/models/available", response_model=ModelsAvailableResponse)
async def api_models_available(db: AsyncSession = Depends(get_db)):
    """
    Get available models from centralized Model Management system.
    
    SOURCE OF TRUTH: Database-managed models ONLY.
    
    A model becomes available only when:
    1. It exists on a provider
    2. It has been fetched from that provider
    3. It has been saved in the database
    4. Administrator has assigned an eligible status (ACTIVE or MAINTENANCE)
    
    This endpoint does NOT include hardcoded cloud models.
    Cloud models must be configured through the Provider system and fetched
    into the database to appear in this list.
    """
    from app.services.model_availability_service import get_available_models, ModelStatus
    from app.services.model_management_service import get_all_providers, get_task_mapping
    from app.services import app_config_service as app_cfg
    from app.services.model_capabilities import get_model_capabilities, get_display_category
    from app.utils.ollama_client import ollama
    
    # Get Ollama models (these are still considered "installed" locally)
    ollama_installed: list[str] = []
    ollama_details: list[dict] = []
    offline = False
    try:
        ollama_installed = await ollama.list_models()
        update_installed_models(ollama_installed)
        ollama_details = await ollama.list_models_detailed()
    except Exception:
        cache = load_model_cache()
        ollama_installed = list(cache.get("installed") or [])
        offline = True
    
    # ═══════════════════════════════════════════════════════════════════════
    # SOURCE OF TRUTH: Database-managed models ONLY
    # ═══════════════════════════════════════════════════════════════════════
    
    # Get all providers with their models from database
    v2_providers = await get_all_providers(db)
    
    # Get all models with visibility (ACTIVE and MAINTENANCE)
    db_models = await get_available_models(db, include_maintenance=True)
    
    # DEBUG: Log model list construction
    logger.info("[MODEL LIST DEBUG] === /api/models/installed START ===")
    logger.info("[MODEL LIST DEBUG] v2_providers count: %d", len(v2_providers))
    for p in v2_providers:
        logger.info("[MODEL LIST DEBUG] Provider: id=%s, name=%s, provider_id=%s", 
                   p.get('id'), p.get('name'), p.get('provider_id'))
    logger.info("[MODEL LIST DEBUG] ollama_installed: %s", ollama_installed)
    logger.info("[MODEL LIST DEBUG] db_models count: %d", len(db_models))
    for m in db_models:
        logger.info("[MODEL LIST DEBUG] DB Model: model_id=%s, provider_id=%s, status=%s", 
                   m.model_id, m.provider_id, m.status)
    
    # Build provider-grouped model structure
    # Only include models where status is ACTIVE or MAINTENANCE
    selectable_models = []  # ACTIVE only - can be selected/used
    visible_models = []     # ACTIVE + MAINTENANCE - visible in dropdowns
    all_model_details = []
    
    for model in db_models:
        model_dict = model.to_dict()
        visible_models.append(model_dict)
        if model.is_selectable:
            selectable_models.append(model_dict)
        
        # Build model detail entry
        detail = {
            "name": model.model_id,
            "provider_id": model.provider_id,
            "size": 0,
            "size_human": model.pricing_tier or "Cloud",
            "family": model.provider_id,
            "parameter_size": model.name,
            "quantization_level": "API" if model.pricing_tier != "local" else "Local",
            "modified_at": "",
            "digest": "",
            "ready": model.is_selectable,  # Only ACTIVE models are "ready"
            "capabilities": model.capabilities or get_model_capabilities(model.model_id),
            "display_category": get_display_category(model.model_id),
            "status": model.status,
            "is_selectable": model.is_selectable,
            "is_visible": model.is_visible,
            "is_disabled": model.is_disabled,
            "disabled_reason": model.disabled_reason,
        }
        all_model_details.append(detail)
    
    # Get selectable model IDs for the flat lists (for backward compatibility)
    selectable_model_ids = [m["id"] for m in selectable_models]
    visible_model_ids = [m["id"] for m in visible_models]
    
    # Combine with Ollama models that are locally installed
    # Only include Ollama models that are also in the database as ACTIVE/MAINTENANCE
    # OR Ollama models that haven't been imported yet (backward compatibility)
    installed_set = set(ollama_installed)
    
    # For backward compatibility: include Ollama models not yet in DB
    # These will be imported when admin fetches models
    ollama_only_models = [m for m in ollama_installed if m not in visible_model_ids]
    
    # Final lists:
    # - "installed": All selectable (ACTIVE) models + locally installed Ollama models
    # - "available": All visible (ACTIVE + MAINTENANCE) models + all Ollama models
    filtered_installed = list(dict.fromkeys(selectable_model_ids + ollama_installed))
    filtered_available = list(dict.fromkeys(visible_model_ids + ollama_installed))
    
    # Filter out embedding models
    filtered_installed = [m for m in filtered_installed if _is_generation_model(m)]
    filtered_available = [m for m in filtered_available if _is_generation_model(m)]
    
    # Add Ollama model details
    for d in ollama_details:
        if "capabilities" not in d or not d["capabilities"]:
            d["capabilities"] = get_model_capabilities(d["name"])
        if "display_category" not in d or not d["display_category"]:
            d["display_category"] = get_display_category(d["name"])
        d["provider_id"] = "ollama"
        d["status"] = "active"  # Local Ollama models are always active
        d["is_selectable"] = True
        d["is_visible"] = True
        d["is_disabled"] = False
    
    # Combine all model details
    all_details = ollama_details + all_model_details
    
    # ═══════════════════════════════════════════════════════════════════════
    # Task defaults and routing configuration
    # ═══════════════════════════════════════════════════════════════════════
    
    task_defaults = {}
    v2_auto_routing = True
    try:
        v2_auto_routing = await app_cfg.get_setting_bool(db, "routing.automatic", True)
        
        # Get task mappings - only include mappings to ACTIVE models
        task_mappings = await get_task_mapping(db)
        for task_type, mapping in task_mappings.items():
            if mapping and mapping.get("modelId"):
                model_id = mapping["modelId"]
                # Only include if model is ACTIVE (selectable)
                if any(m["id"] == model_id for m in selectable_models):
                    task_defaults[task_type] = model_id
    except Exception as e:
        logger.warning("Failed to load task mappings: %s", e)
    
    # Determine default model from database configuration or first selectable
    default_model = await app_cfg.get_setting(db, "models.default", None)
    if not default_model and selectable_model_ids:
        default_model = selectable_model_ids[0]
    
    # DEBUG: Log final response
    logger.info("[MODEL LIST DEBUG] === /api/models/installed END ===")
    logger.info("[MODEL LIST DEBUG] filtered_installed: %s", filtered_installed)
    logger.info("[MODEL LIST DEBUG] filtered_available: %s", filtered_available)
    logger.info("[MODEL LIST DEBUG] v2_providers count in response: %d", len(v2_providers))
    for p in v2_providers:
        logger.info("[MODEL LIST DEBUG] v2_provider in response: id=%s, name=%s", 
                   p.get('id'), p.get('name'))
    
    return {
        "installed": filtered_installed,
        "available": filtered_available,
        "offline": offline,
        "default_model": default_model or settings.default_model or settings.text_model,
        "embed_model": settings.embed_model,
        "vision_model": settings.vision_model,
        "models": all_details,
        "ollama_healthy": not offline,
        "defaults": task_defaults,
        "v2_providers": v2_providers,
        "v2_auto_routing": v2_auto_routing,
    }


@router.get("/api/models/capabilities")
async def api_models_capabilities():
    """Return the full model capability registry (model_id → capabilities list)."""
    from app.services.model_capabilities import get_all_capabilities
    registry = get_all_capabilities()
    return {
        "capabilities": registry,
        "labels": {
            "text": "Text Generation",
            "vision": "Vision / Image Understanding",
            "audio": "Audio / Speech",
            "code": "Code Generation",
            "reasoning": "Deep Reasoning",
            "embedding": "Text Embeddings",
            "fast": "Fast Response",
            "large": "Large Context",
        },
    }


@router.get("/api/models/{model_id}/capabilities")
async def api_model_capabilities(model_id: str):
    """Return capabilities for a specific model ID."""
    from app.services.model_capabilities import (
        get_model_capabilities,
        get_display_category,
    )
    caps = get_model_capabilities(model_id)
    cat = get_display_category(model_id)
    return {
        "model_id": model_id,
        "capabilities": caps,
        "display_category": cat,
    }


@router.get("/api/models/labels", response_model=ModelLabelsResponse)
async def api_models_labels():
    """Return display labels for all available models."""
    from app.services.gemini_service import GEMINI_MODEL_ID, is_configured as gemini_configured, get_display_name

    labels = {}

    # Add Gemini label if configured
    if gemini_configured():
        labels[GEMINI_MODEL_ID] = get_display_name()

    # Add OpenCode Zen labels if configured
    from app.services.opencode_zen_service import is_configured as zen_configured, get_available_models as zen_models_list, get_display_name as zen_display_name
    if zen_configured():
        for zm in zen_models_list():
            labels[zm["id"]] = zen_display_name(zm["id"])

    # Add HuggingFace labels if configured
    from app.services.huggingface_service import is_configured as hf_configured, get_available_models as hf_models_list, get_display_name as hf_display_name
    if hf_configured():
        for hm in hf_models_list():
            labels[hm["id"]] = hf_display_name(hm["id"])

    # Add Ollama model labels - merge static defaults with dynamic info
    ollama_labels = {
        "qwen3:4b": "Qwen 3 — 4B",
        "qwen3:8b": "Qwen 3 — 8B",
        "llama3.2": "Llama 3.2 (3B)",
        "llava:7b": "LLaVA 7B (vision)",
    }

    from app.utils.ollama_client import ollama
    try:
        details = await ollama.list_models_detailed()
        for d in details:
            name = d.get("name", "")
            if name and name not in labels:
                family = d.get("family", "")
                param = d.get("parameter_size", "")
                quant = d.get("quantization_level", "")
                if param:
                    ollama_labels[name] = f"{family} {param}" if family else param
                elif family:
                    ollama_labels[name] = family
    except Exception:
        pass

    labels.update(ollama_labels)

    return {"labels": labels}


@router.post("/api/models/pull")
async def api_models_pull(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
):
    model = (payload.get("model") or "").strip()
    resume = bool(payload.get("resume", True))
    if not model:
        return JSONResponse(status_code=400, content={"ok": False, "error": "missing_model"})
    if settings.available_models and model not in set(settings.available_models):
        return JSONResponse(status_code=400, content={"ok": False, "error": "model_not_allowed", "model": model})
    from app.services.model_pull_service import start_pull, get_status_payload

    await start_pull(model, resume=resume)
    return await get_status_payload(model)


@router.get("/api/models/pull/status/{model}")
async def api_models_pull_status(model: str, user: User = Depends(get_current_user)):
    from app.services.model_pull_service import get_status_payload

    m = (model or "").strip()
    if not m:
        return JSONResponse(status_code=400, content={"ok": False, "error": "missing_model"})
    return await get_status_payload(m)
