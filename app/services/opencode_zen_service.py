"""
opencode_zen_service.py – OpenCode Zen/Go API integration for DocTel.

Models are loaded from ``app/data/providers.json`` instead of being hardcoded.
Each model entry includes its own API endpoint URL so requests are routed to
the correct vendor endpoint (chat/completions, messages, responses, etc.).

To update the model catalogue, replace ``app/data/providers.json`` with an
up-to-date export — no Python code changes needed.

Environment variables:
  OPENCODE_GO_API_KEY   – primary API key (used by both Go and Zen providers)
  OPENCODE_ZEN_API_KEY  – fallback if Go key is absent
  OPENCODE_GO_BASE_URL  – override for Go API base URL
  OPENCODE_ZEN_BASE_URL – override for Zen API base URL
"""

import logging
import os
import json
import asyncio
import httpx
from pathlib import Path
from typing import Optional, List, Dict, AsyncGenerator

from app.config import settings

logger = logging.getLogger(__name__)

ZEN_MODEL_ID = "opencode-zen"

_DEFAULT_BASE_URL = "https://opencode.ai/zen/v1"
_TIMEOUT = 120.0

# ── JSON-backed model catalogue ───────────────────────────────────────────

_PROVIDERS_PATH = Path(__file__).resolve().parent.parent / "data" / "providers.json"

# In-memory cache of parsed models: list[dict] with keys id, name, url,
# toolCalling, vision, maxInputTokens, maxOutputTokens, and a derived
# ``provider_group`` field (the provider name).
_models_cache: Optional[List[Dict]] = None


def _load_providers() -> List[Dict]:
    """Read and cache the full provider list from providers.json."""
    global _models_cache
    if _models_cache is not None:
        return _models_cache
    try:
        raw = _PROVIDERS_PATH.read_text(encoding="utf-8")
        providers = json.loads(raw)
    except Exception as exc:
        logger.warning("Failed to load %s: %s — using empty model list", _PROVIDERS_PATH, exc)
        _models_cache = []
        return []

    flat: List[Dict] = []
    for prov in providers:
        vendor = (prov.get("vendor") or "").strip()
        prefix = "go/" if vendor == "customendpoint" and "go" in (prov.get("name") or "").lower() else "zen/"
        for m in (prov.get("models") or []):
            mid = m.get("id", "").strip()
            if not mid:
                continue
            flat.append({
                "id": f"{prefix}{mid}",
                "name": m.get("name", mid),
                "url": (m.get("url") or "").rstrip("/"),
                "toolCalling": bool(m.get("toolCalling", False)),
                "vision": bool(m.get("vision", False)),
                "maxInputTokens": int(m.get("maxInputTokens", 128000)),
                "maxOutputTokens": int(m.get("maxOutputTokens", 16000)),
                "provider_group": prov.get("name", vendor),
            })
    _models_cache = flat
    return flat


def _get_model_entry(model_id: str) -> Optional[Dict]:
    """Look up a single model by its prefixed ID (e.g. ``go/deepseek-v4-pro``)."""
    for m in _load_providers():
        if m["id"] == model_id:
            return m
    return None


def _get_url_for_model(model_id: str) -> str:
    """Return the full API endpoint URL for a model, falling back to
    ``{_base_url()}/chat/completions``."""
    entry = _get_model_entry(model_id)
    if entry and entry.get("url"):
        return entry["url"]
    return f"{_base_url()}/chat/completions"


def _url_to_api_base(url: str) -> str:
    """Strip the endpoint path (``/chat/completions``, ``/messages``,
    ``/responses``, ``/models/*``) to get the API base URL."""
    u = url.rstrip("/")
    for suffix in ("/chat/completions", "/messages", "/responses"):
        if u.endswith(suffix):
            return u[: -len(suffix)]
    # Handle /models/<name> paths — strip to the API version root
    if "/models/" in u:
        parts = u.split("/models/", 1)
        return parts[0]
    return u


def _get_endpoint_path(url: str) -> str:
    """Determine the relative endpoint path after the API base.

    Returns e.g. ``chat/completions``, ``messages``, or ``responses``.
    """
    base = _url_to_api_base(url)
    rest = url[len(base):].lstrip("/")
    return rest or "chat/completions"


# ── Helpers ────────────────────────────────────────────────────────────────


def _normalize_base_url(url: str) -> str:
    url = url.rstrip("/")
    suffix = "/chat/completions"
    if url.endswith(suffix):
        url = url[: -len(suffix)]
    return url


_client_api_key: Optional[str] = None
_client_base_url: Optional[str] = None
_shared_httpx: Optional[httpx.AsyncClient] = None


def _get_httpx_client() -> httpx.AsyncClient:
    global _shared_httpx
    if _shared_httpx is None or _shared_httpx.is_closed:
        _shared_httpx = httpx.AsyncClient(
            timeout=_TIMEOUT,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _shared_httpx


def _api_key() -> str:
    # Check Pydantic Settings first (populated from .env)
    key = settings.opencode_go_api_key.strip()
    if key:
        return key
    key = settings.opencode_zen_api_key.strip()
    if key:
        return key
    # Fallback to os.getenv for backward compatibility
    key = os.getenv("OPENCODE_GO_API_KEY", "").strip()
    if key:
        return key
    key = os.getenv("OPENCODE_ZEN_API_KEY", "").strip()
    return key


def _base_url() -> str:
    # Check Pydantic Settings first
    go_base = settings.opencode_go_base_url.strip()
    if go_base:
        return _normalize_base_url(go_base)
    zen_base = settings.opencode_zen_base_url.strip()
    if zen_base:
        return _normalize_base_url(zen_base)
    # Fallback to os.getenv for backward compatibility
    go_base = os.getenv("OPENCODE_GO_BASE_URL", "").strip()
    if go_base:
        return _normalize_base_url(go_base)
    base = os.getenv("OPENCODE_ZEN_BASE_URL", "").strip()
    if base:
        return _normalize_base_url(base)
    return _DEFAULT_BASE_URL


def is_configured() -> bool:
    return bool(_api_key())


def get_available_models() -> List[Dict]:
    """Return all models from the JSON catalogue (only when API key is set)."""
    if not is_configured():
        return []
    return [{"id": m["id"],
             "name": m["name"],
             "provider": m["provider_group"],
             "tier": "api",
             "input_price": 0,
             "output_price": 0,
             "vision": m["vision"],
             "toolCalling": m["toolCalling"],
             "maxInputTokens": m["maxInputTokens"],
             "maxOutputTokens": m["maxOutputTokens"]}
            for m in _load_providers()]


def get_display_name(model_id: str) -> str:
    entry = _get_model_entry(model_id)
    if entry:
        return f"{entry['name']} (OpenCode)"
    return f"OpenCode ({model_id})"


def get_model_metadata(model_id: str) -> Dict:
    """Return the full metadata dict for a model (used by cloud_details)."""
    entry = _get_model_entry(model_id)
    if entry:
        return {
            "provider": entry["provider_group"],
            "name": entry["name"],
            "tier": "api",
            "vision": entry["vision"],
            "toolCalling": entry["toolCalling"],
        }
    return {"provider": "OpenCode", "name": model_id, "tier": "api",
            "vision": False, "toolCalling": False}


def _resolve_model_id(model_id: str) -> str:
    """Strip DocTel prefixes to get the bare model name the API expects."""
    if model_id.startswith("zen/"):
        return model_id[4:]
    if model_id.startswith("go/"):
        return model_id[3:]
    return model_id


# ── Low-level HTTP helpers ────────────────────────────────────────────────


async def _chat_completion(
    url: str,
    api_key: str,
    model: str,
    messages: list,
    **kwargs,
) -> Dict:
    """POST to any ``chat/completions``-style endpoint.

    Supports both OpenAI-compatible and other vendor schemas.
    """
    client = _get_httpx_client()
    body = {
        "model": model,
        "messages": messages,
        "temperature": kwargs.get("temperature", 0.3),
        "max_tokens": kwargs.get("max_tokens", 2048),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    resp = await client.post(url, json=body, headers=headers)
    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise RuntimeError(f"OpenCode API error {resp.status_code}: {detail}")
    return resp.json()


async def _chat_completion_stream(
    url: str,
    api_key: str,
    model: str,
    messages: list,
    **kwargs,
) -> AsyncGenerator[str, None]:
    """Streaming POST to a chat/completions endpoint (SSE)."""
    client = _get_httpx_client()
    body = {
        "model": model,
        "messages": messages,
        "temperature": kwargs.get("temperature", 0.3),
        "max_tokens": kwargs.get("max_tokens", 2048),
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with asyncio.timeout(60.0):
            async with client.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code >= 400:
                    detail = await resp.aread()
                    raise RuntimeError(f"OpenCode API stream error {resp.status_code}: {detail[:500]}")
                prefix = "data: "
                async for line in resp.aiter_lines():
                    if not line or not line.startswith(prefix):
                        continue
                    payload = line[len(prefix):].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    for c in choices:
                        delta = c.get("delta") or {}
                        text = delta.get("content") or ""
                        if text:
                            yield text
    except asyncio.TimeoutError:
        raise RuntimeError("OpenCode API streaming timed out after 60 seconds.")


# ── Generation (non-streaming) ──────────────────────────────────────────────


async def generate(prompt: str, model: str = "deepseek-v4-flash-free", system: Optional[str] = None) -> str:
    if not _api_key():
        raise RuntimeError(
            "OpenCode API key is not configured. "
            "Get one at https://opencode.ai/go and add OPENCODE_GO_API_KEY to your .env file."
        )

    resolved_model = _resolve_model_id(model)
    url = _get_url_for_model(model)
    api_key = _api_key()

    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    api_key_masked = api_key[:8] + "..." if len(api_key) > 8 else "***"
    print(f"\n=== OPCODE API REQUEST (generate) ===", flush=True)
    print(f"URL: {url}", flush=True)
    print(f"Model: {resolved_model}", flush=True)
    print(f"Messages: {json.dumps(messages, ensure_ascii=False)}", flush=True)
    print(f"Key: {api_key_masked}", flush=True)

    try:
        data = await _chat_completion(url, api_key, resolved_model, messages)
        print(f"=== OPCODE API RESPONSE ===", flush=True)
        content = ""
        if "choices" in data:
            content = (data["choices"][0].get("message") or {}).get("content", "") or ""
        elif "content" in data:
            content = data["content"]
        content = (content or "").strip()

        # Fallback: reasoning-only response → retry without system prompt
        reasoning = ""
        if data.get("choices"):
            reasoning = getattr(data["choices"][0].get("message"), "reasoning_content", None) or ""
        if not content and reasoning:
            print(f"=== FALLBACK: reasoning-only, retrying without system prompt ===", flush=True)
            retry_messages = [{"role": "user", "content": prompt}]
            retry_data = await _chat_completion(url, api_key, resolved_model, retry_messages)
            if "choices" in retry_data:
                content = (retry_data["choices"][0].get("message") or {}).get("content", "") or ""
            elif "content" in retry_data:
                content = retry_data["content"]
            content = (content or "").strip()
        print(f"Status: OK, content: {content[:200]}, reasoning: {bool(reasoning)}", flush=True)
        return content
    except RuntimeError:
        raise
    except Exception as exc:
        print(f"=== OPCODE API ERROR === {exc}", flush=True)
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"OpenCode API error: {exc}")


# ── Generation (streaming) ──────────────────────────────────────────────────


async def generate_stream(prompt: str, model: str = "deepseek-v4-flash-free", system: Optional[str] = None) -> AsyncGenerator[str, None]:
    if not _api_key():
        raise RuntimeError("OpenCode API key is not configured.")

    resolved_model = _resolve_model_id(model)
    url = _get_url_for_model(model)
    api_key = _api_key()

    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    api_key_masked = api_key[:8] + "..." if len(api_key) > 8 else "***"
    print(f"\n=== OPCODE API STREAM REQUEST ===", flush=True)
    print(f"URL: {url}", flush=True)
    print(f"Model: {resolved_model}", flush=True)
    print(f"Key: {api_key_masked}", flush=True)

    try:
        content_yielded = False
        reasoning_text = ""
        async for text in _chat_completion_stream(url, api_key, resolved_model, messages):
            content_yielded = True
            yield text

        # Fallback: reasoning-only → retry without system
        if not content_yielded and reasoning_text.strip():
            print(f"=== FALLBACK: reasoning-only, retrying without system prompt ===", flush=True)
            retry_messages = [{"role": "user", "content": prompt}]
            async for text in _chat_completion_stream(url, api_key, resolved_model, retry_messages):
                yield text
            if not content_yielded:
                yield "I can see you're asking about this. Could you rephrase or be more specific?"

    except RuntimeError:
        raise
    except Exception as exc:
        print(f"=== OPCODE API STREAM ERROR === {exc}", flush=True)
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"OpenCode API streaming failed: {exc}")
