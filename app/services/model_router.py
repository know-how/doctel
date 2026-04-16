"""
model_router.py – Intelligent 4-tier model router for Doctel.

Tier 1 – Local LoRA adapter   (fastest, fully private, self-improving)
Tier 2 – Ollama               (current primary, unchanged behaviour)
Tier 3 – Cloud teacher model  (DeepSeek / Gemini / GPT – optional)
Tier 4 – Web search fallback  (DuckDuckGo – last resort)

The legacy select_text_model() function is kept intact so existing call-sites
continue to work without modification.
"""
import asyncio
import logging
import os
import psutil
from pathlib import Path
from typing import Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

_force_model: Optional[str] = None
_last_selection: Tuple[str, str, int] = ("", "", 0)  # (model, reason, free_ram_mb)


# ── helpers ───────────────────────────────────────────────────────────────────

def _free_ram_mb() -> int:
    try:
        vm = psutil.virtual_memory()
        return int(vm.available / (1024 * 1024))
    except Exception:
        return 0


def force_select(model: Optional[str]) -> None:
    global _force_model
    _force_model = model


def active() -> dict:
    model, reason, free_ram = _last_selection
    return {"selected_model": model, "reason": reason, "free_ram_mb": free_ram}


# ── legacy 2-tier selector (backward-compatible) ──────────────────────────────

def select_text_model(task_type: str = "rag") -> str:
    """
    Legacy selector – used by RAG and ingest paths that only need an Ollama
    model name.  The full 4-tier fallback is in select_model_with_fallback().
    task_type: 'summary_long' | 'rag' | 'short_qa'
    """
    global _last_selection
    if _force_model:
        m = _force_model
        _last_selection = (m, "forced", _free_ram_mb())
        return m

    free_mb = _free_ram_mb()
    allow = settings.available_models or []
    base_default = settings.default_model or settings.text_model

    if settings.automatic_switching:
        if settings.enable_qwen_9b and task_type in ("summary_long", "rag"):
            if free_mb >= settings.min_free_ram_for_qwen9b_mb:
                m = settings.qwen_9b_model
                _last_selection = (m, f"qwen9b_enabled_free_mb_{free_mb}", free_mb)
                return m if (not allow or m in allow) else base_default
        if free_mb >= settings.min_free_ram_for_8b_mb:
            m = settings.text_model
            _last_selection = (m, f"llama8b_free_mb_{free_mb}", free_mb)
            return m if (not allow or m in allow) else base_default
        m = settings.fallback_text_model
        _last_selection = (m, f"fallback_3b_free_mb_{free_mb}", free_mb)
        return m if (not allow or m in allow) else base_default

    m = base_default
    _last_selection = (m, "static", free_mb)
    return m


# ── 4-tier async router ───────────────────────────────────────────────────────

def _get_training_paths() -> Optional[dict]:
    """Return training room paths or None if not configured."""
    try:
        from app.training.training_config import get_training_paths, TrainingSettings
        return get_training_paths(settings.base_dir, TrainingSettings())
    except Exception:
        return None


def _has_local_adapter() -> bool:
    """Check if a trained LoRA adapter is present and active."""
    try:
        paths = _get_training_paths()
        if not paths:
            return False
        from app.training.checkpoint_manager import get_active_adapter_path
        ap = get_active_adapter_path(paths["model_state"])
        return ap is not None and ap.exists()
    except Exception:
        return False


async def _query_local_adapter(prompt: str) -> Optional[str]:
    """
    Query the active LoRA adapter using HuggingFace PEFT + Transformers.
    The training pipeline produces safetensors adapters (PEFT format), so we
    load the base model with PeftModel rather than using llama-cpp lora_path
    (which expects a GGUF-format adapter and is incompatible).
    Returns answer text or None.
    """
    if not _has_local_adapter():
        return None

    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
        from peft import PeftModel
    except ImportError:
        logger.debug("transformers/peft not installed – skipping local adapter inference")
        return None

    def _run_local_adapter() -> Optional[str]:
        paths = _get_training_paths()
        if not paths:
            return None
        from app.training.checkpoint_manager import get_active_adapter_path
        from app.training.training_config import TrainingSettings
        adapter_path = get_active_adapter_path(paths["model_state"])
        if adapter_path is None:
            return None

        base_model_id = TrainingSettings().hf_base_model
        tokenizer = AutoTokenizer.from_pretrained(base_model_id, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_id,
            torch_dtype=torch.float32,
            device_map="cpu",
            trust_remote_code=True,
        )
        model = PeftModel.from_pretrained(base_model, str(adapter_path))
        model.eval()

        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=256,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
        output = pipe(prompt)
        generated = output[0]["generated_text"]
        # Strip the echoed prompt from the output
        answer = generated[len(prompt):].strip()
        return answer if answer else None

    try:
        return await asyncio.to_thread(_run_local_adapter)
    except Exception as e:
        logger.debug("Local adapter (HF) query failed: %s", e)
        return None


async def _query_ollama(prompt: str, model: str) -> Optional[str]:
    """Query the local Ollama endpoint."""
    try:
        from app.utils.ollama_client import ollama
        result = await ollama.generate(model, prompt)
        return result if result else None
    except Exception as e:
        logger.debug("Ollama query failed: %s", e)
        return None


async def _query_teacher(prompt: str, teacher_samples_dir: Optional[Path] = None) -> Optional[str]:
    """Query the configured cloud teacher model."""
    try:
        from app.services.teacher_service import query_and_capture
        return await query_and_capture(prompt, teacher_samples_dir)
    except Exception as e:
        logger.debug("Teacher service failed: %s", e)
        return None


async def _query_web(prompt: str, model: str, web_samples_dir: Optional[Path] = None) -> Optional[str]:
    """Fall back to DuckDuckGo search + local summarisation."""
    try:
        from app.services.web_search_service import search_and_summarise
        return await search_and_summarise(prompt, settings.ollama_base_url, model, web_samples_dir)
    except Exception as e:
        logger.debug("Web search failed: %s", e)
        return None


def _is_confident(text: str) -> bool:
    """Heuristic check for low-confidence or abstention responses."""
    if not text or len(text.strip()) < 5:
        return False
    low_conf_phrases = [
        "i don't know", "i do not know", "i am not sure", "i'm not sure",
        "i cannot answer", "i can't answer", "unable to answer", "i don't have enough information",
        "it is not clear"
    ]
    txt = text.lower()
    return not any(p in txt for p in low_conf_phrases)


async def select_model_with_fallback(
    prompt: str,
    task_type: str = "rag",
) -> dict:
    """
    4-tier decision router.  Returns:
    {
        "answer": str,
        "tier": "local_lora" | "ollama" | "cloud_teacher" | "web_search" | "failed",
        "model": str,
        "confidence": float,
    }
    """
    paths = _get_training_paths()
    teacher_samples_dir = paths["teacher_samples"] if paths else None
    web_samples_dir = paths["web_samples"] if paths else None

    # ── Tier 1: Local LoRA ────────────────────────────────────────────────────
    if _has_local_adapter():
        logger.info("Decision Node: trying Tier 1 – local LoRA adapter")
        answer = await _query_local_adapter(prompt)
        if answer and _is_confident(answer):
            return {"answer": answer, "tier": "local_lora", "model": "local_adapter", "confidence": 0.9}
        else:
            logger.info("Decision Node: Tier 1 uncertain or low-confidence, falling back to Tier 2")

    # ── Tier 2: Ollama ────────────────────────────────────────────────────────
    logger.info("Decision Node: trying Tier 2 – Ollama endpoint")
    ollama_model = select_text_model(task_type)
    answer = await _query_ollama(prompt, ollama_model)
    if answer and _is_confident(answer):
        return {"answer": answer, "tier": "ollama", "model": ollama_model, "confidence": 0.75}

    # ── Tier 3: Cloud teacher ─────────────────────────────────────────────────
    logger.info("Decision Node: Tier 2 uncertain – trying Tier 3 (cloud teacher)")
    answer = await _query_teacher(prompt, teacher_samples_dir)
    if answer:
        return {"answer": answer, "tier": "cloud_teacher", "model": "cloud", "confidence": 0.85}

    # ── Tier 4: Web search ────────────────────────────────────────────────────
    logger.info("Router: Tier 3 failed – trying Tier 4 (web search)")
    answer = await _query_web(prompt, ollama_model, web_samples_dir)
    if answer:
        return {"answer": answer, "tier": "web_search", "model": "duckduckgo", "confidence": 0.55}

    logger.error("Router: all tiers exhausted for prompt: %s", prompt[:60])
    return {
        "answer": "I was unable to find an answer using any available intelligence tier.",
        "tier": "failed",
        "model": "none",
        "confidence": 0.0,
    }


def get_router_status() -> dict:
    """Return a status dict showing which tiers are currently available."""
    from app.services.teacher_service import is_configured as teacher_configured
    from app.services.web_search_service import is_enabled as web_enabled
    return {
        "local_lora": _has_local_adapter(),
        "ollama": True,  # assumed available; actual check handled by call-site
        "cloud_teacher": teacher_configured(),
        "web_search": web_enabled(),
        "active_ollama_model": select_text_model(),
        "free_ram_mb": _free_ram_mb(),
    }

