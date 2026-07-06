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
    User,
    DbSession,
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
async def api_models_available():
    from app.utils.ollama_client import ollama
    installed: list[str] = []
    ollama_details: list[dict] = []
    offline = False
    try:
        installed = await ollama.list_models()
        update_installed_models(installed)
        ollama_details = await ollama.list_models_detailed()
    except Exception:
        cache = load_model_cache()
        installed = list(cache.get("installed") or [])
        offline = True
    available = list(settings.available_models or [])
    installed_set = set(installed)
    available_set = set(available)
    merged = list(dict.fromkeys(available + installed))
    filtered_installed = [m for m in merged if m in installed_set]
    filtered_available = [m for m in merged if m in available_set or m in installed_set]
    filtered_installed = [m for m in filtered_installed if _is_generation_model(m)]
    filtered_available = [m for m in filtered_available if _is_generation_model(m)]

    # Inject Gemini API entry when a key is configured so it appears in the UI
    from app.services.gemini_service import GEMINI_MODEL_ID, is_configured as gemini_configured
    if gemini_configured():
        if GEMINI_MODEL_ID not in filtered_installed:
            filtered_installed.append(GEMINI_MODEL_ID)
        if GEMINI_MODEL_ID not in filtered_available:
            filtered_available.append(GEMINI_MODEL_ID)

    # Inject DeepSeek API entry when a key is configured
    from app.services.deepseek_service import DEEPSEEK_MODEL_ID, is_configured as deepseek_configured
    if deepseek_configured():
        if DEEPSEEK_MODEL_ID not in filtered_installed:
            filtered_installed.append(DEEPSEEK_MODEL_ID)
        if DEEPSEEK_MODEL_ID not in filtered_available:
            filtered_available.append(DEEPSEEK_MODEL_ID)

    # Inject OpenCode Zen models when API key is configured
    from app.services.opencode_zen_service import is_configured as zen_configured, get_available_models as zen_models
    if zen_configured():
        for zm in zen_models():
            mid = zm["id"]
            if mid not in filtered_installed:
                filtered_installed.append(mid)
            if mid not in filtered_available:
                filtered_available.append(mid)

    # Inject HuggingFace models when API key is configured
    from app.services.huggingface_service import is_configured as hf_configured, get_available_models as hf_models
    if hf_configured():
        for hm in hf_models():
            mid = hm["id"]
            if mid not in filtered_installed:
                filtered_installed.append(mid)
            if mid not in filtered_available:
                filtered_available.append(mid)

    # Build cloud model detail entries
    from app.services.model_capabilities import (
        get_model_capabilities,
        get_display_category,
    )

    cloud_details = []
    if gemini_configured():
        from app.services.gemini_service import get_display_name as gemini_display
        cloud_details.append({
            "name": GEMINI_MODEL_ID,
            "size": 0,
            "size_human": "Cloud",
            "family": "Google Gemini",
            "parameter_size": settings.gemini_model,
            "quantization_level": "API",
            "modified_at": "",
            "digest": "",
            "ready": True,
            "capabilities": get_model_capabilities(GEMINI_MODEL_ID),
            "display_category": get_display_category(GEMINI_MODEL_ID),
        })

    if deepseek_configured():
        from app.services.deepseek_service import get_display_name as deepseek_display
        cloud_details.append({
            "name": DEEPSEEK_MODEL_ID,
            "size": 0,
            "size_human": "Cloud",
            "family": "DeepSeek",
            "parameter_size": settings.deepseek_model,
            "quantization_level": "API",
            "modified_at": "",
            "digest": "",
            "ready": True,
            "capabilities": get_model_capabilities(DEEPSEEK_MODEL_ID),
            "display_category": get_display_category(DEEPSEEK_MODEL_ID),
        })

    if zen_configured():
        for zm in zen_models():
            mid = zm["id"]
            cloud_details.append({
                "name": mid,
                "size": 0,
                "size_human": "Cloud",
                "family": zm.get("provider", "OpenCode"),
                "parameter_size": zm.get("name", ""),
                "quantization_level": zm.get("tier", ""),
                "modified_at": "",
                "digest": "",
                "ready": True,
                "capabilities": get_model_capabilities(mid),
                "display_category": get_display_category(mid),
                "max_input_tokens": zm.get("maxInputTokens", 128000),
                "max_output_tokens": zm.get("maxOutputTokens", 16000),
                "vision": zm.get("vision", False),
                "tool_calling": zm.get("toolCalling", False),
            })

    if hf_configured():
        for hm in hf_models():
            mid = hm["id"]
            cloud_details.append({
                "name": mid,
                "size": 0,
                "size_human": "Cloud",
                "family": hm.get("provider", "HuggingFace"),
                "parameter_size": hm.get("name", ""),
                "quantization_level": hm.get("tier", ""),
                "modified_at": "",
                "digest": "",
                "ready": True,
                "capabilities": get_model_capabilities(mid),
                "display_category": get_display_category(mid),
            })

    all_details = ollama_details + cloud_details

    # Inject capabilities into Ollama model details
    for d in all_details:
        if "capabilities" not in d or not d["capabilities"]:
            d["capabilities"] = get_model_capabilities(d["name"])
        if "display_category" not in d or not d["display_category"]:
            d["display_category"] = get_display_category(d["name"])

    # Mark available-but-not-installed Ollama models as not ready
    installed_names = {d["name"] for d in ollama_details}
    available_not_installed = [m for m in filtered_available if m not in installed_names]

    # Load task mapping defaults from V2 if available
    task_defaults = {}
    _mgmt_path = Path(settings.base_dir) / "data" / "model_management.json"
    if _mgmt_path.exists():
        try:
            _raw = _mgmt_path.read_text(encoding="utf-8")
            _data = json.loads(_raw)
            _raw_mapping = _data.get("taskMapping", {})
            for task_type, mapping in _raw_mapping.items():
                if isinstance(mapping, dict) and mapping.get("modelId"):
                    task_defaults[task_type] = mapping["modelId"]
        except Exception as e:
            logger.warning("Failed to load task mapping from %s: %s", _mgmt_path, e)
    else:
        logger.info("V2 management file not found at %s", _mgmt_path)

    return {
        "installed": filtered_installed,
        "available": filtered_available,
        "offline": offline,
        "default_model": (settings.default_model or settings.text_model),
        "embed_model": settings.embed_model,
        "vision_model": settings.vision_model,
        "models": all_details,
        "ollama_healthy": not offline,
        "defaults": task_defaults,
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
