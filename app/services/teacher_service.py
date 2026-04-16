"""
teacher_service.py – Queries a cloud LLM (teacher) when the local model
is unable to answer with sufficient confidence.

Supports providers: deepseek, gemini, openai
Configuration via environment variables:
  DOCTEL_TEACHER_PROVIDER   = deepseek | gemini | openai  (default: deepseek)
  DOCTEL_TEACHER_API_KEY    = <your API key>
  DOCTEL_TEACHER_MODEL      = <model name, provider-specific default if blank>
  DOCTEL_CONFIDENCE_THRESHOLD = 0.5  (0-1 float; below this = call teacher)

Teacher samples are written to:
  training_room/teacher_samples/sample_<timestamp>.jsonl
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── provider defaults ──────────────────────────────────────────────────────────
_PROVIDER_DEFAULTS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "chat_endpoint": "/chat/completions",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-2.5-flash",
        "chat_endpoint": None,  # uses special URL
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "chat_endpoint": "/chat/completions",
    },
}

_DEFAULT_TIMEOUT = 30.0
_CONFIDENCE_THRESHOLD = float(os.getenv("DOCTEL_CONFIDENCE_THRESHOLD", "0.5"))
_GEMINI_MODEL_ALIASES = {
    "gemini-1.5-flash": "gemini-2.5-flash",
    "gemini-1.5-flash-latest": "gemini-2.5-flash",
}


def _get_config() -> dict:
    provider = os.getenv("DOCTEL_TEACHER_PROVIDER", "deepseek").lower()
    if provider not in _PROVIDER_DEFAULTS:
        provider = "deepseek"
    cfg = dict(_PROVIDER_DEFAULTS[provider])
    cfg["provider"] = provider
    cfg["api_key"] = os.getenv("DOCTEL_TEACHER_API_KEY", "")
    override_model = os.getenv("DOCTEL_TEACHER_MODEL", "").strip()
    if override_model:
        cfg["model"] = override_model
    if provider == "gemini":
        cfg["model"] = _GEMINI_MODEL_ALIASES.get(cfg["model"], cfg["model"])
    return cfg


def is_configured() -> bool:
    return bool(os.getenv("DOCTEL_TEACHER_API_KEY", "").strip())


async def _query_deepseek_openai(cfg: dict, prompt: str) -> str:
    """Shared handler for DeepSeek and OpenAI (both use OpenAI-compatible API)."""
    url = cfg["base_url"].rstrip("/") + cfg["chat_endpoint"]
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    body = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.3,
    }
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _query_gemini(cfg: dict, prompt: str) -> str:
    """Gemini Flash via the generateContent endpoint."""
    api_key = cfg["api_key"]
    model = cfg["model"]
    url = f"{cfg['base_url']}/models/{model}:generateContent?key={api_key}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def query_teacher(prompt: str) -> Optional[str]:
    """
    Query the configured cloud teacher model.
    Returns the answer text or None if not configured / failed.
    """
    if not is_configured():
        logger.debug("Teacher model not configured – skipping cloud query")
        return None

    cfg = _get_config()
    try:
        provider = cfg["provider"]
        if provider == "gemini":
            answer = await _query_gemini(cfg, prompt)
        else:
            answer = await _query_deepseek_openai(cfg, prompt)
        logger.info("Teacher (%s/%s) answered successfully", provider, cfg["model"])
        return answer
    except Exception as e:
        logger.warning("Teacher query failed: %s", e)
        return None


async def capture_teacher_sample(
    prompt: str,
    answer: str,
    teacher_samples_dir: Path,
    source: str = "teacher",
) -> None:
    """
    Append a teacher answer to the teacher_samples JSONL file.
    Used later for fine-tuning cycles.
    """
    teacher_samples_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    sample_file = teacher_samples_dir / f"samples_{ts}.jsonl"
    record = {
        "prompt": prompt,
        "completion": answer,
        "source": source,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(sample_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("Failed to save teacher sample: %s", e)


async def query_and_capture(
    prompt: str,
    teacher_samples_dir: Optional[Path] = None,
) -> Optional[str]:
    """
    Query the teacher model and save the sample for future training.
    Returns the answer or None.
    """
    answer = await query_teacher(prompt)
    if answer and teacher_samples_dir:
        cfg = _get_config()
        await capture_teacher_sample(
            prompt, answer, teacher_samples_dir,
            source=f"{cfg.get('provider', 'teacher')}/{cfg.get('model', 'unknown')}",
        )
    return answer
