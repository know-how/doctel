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
from app.services.provider_credential_resolver import resolve_api_key, resolve_base_url

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
    return resolve_api_key(vendor="opencode")


def _base_url() -> str:
    # Check Pydantic Settings first
    go_base = settings.opencode_go_base_url.strip()
    if go_base:
        return _normalize_base_url(go_base)
    zen_base = settings.opencode_zen_base_url.strip()
    if zen_base:
        return _normalize_base_url(zen_base)
    # Try DB
    db_url = resolve_base_url(vendor="opencode")
    if db_url:
        return _normalize_base_url(db_url)
    # Fallback to os.getenv
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


# ── Robust response extraction helpers ──────────────────────────────────────


def _robust_extract_content(data: dict) -> str:
    """Extract content text from any chat/completions response format.
    
    Handles:
    - Standard: choices[0].message.content (string)
    - Array content: choices[0].message.content = [{"type":"text","text":"..."}]
    - reasoning_content as content: only reasoning_content is present, no content
    - Non-standard keys: output, text, response
    - Fallback: iterate all dict keys for first string value
    """
    # Strategy 1: Standard choices path
    if "choices" in data:
        choices = data["choices"]
        if choices and isinstance(choices, list) and len(choices) > 0:
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if content is not None and isinstance(content, str):
                return content.strip()
            # Handle content as array of {type, text} objects (OpenAI structured format)
            if content is not None and isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append(item.get("text", ""))
                        elif item.get("text"):
                            parts.append(item["text"])
                joined = " ".join(parts)
                if joined.strip():
                    return joined.strip()
            # Handle content being a number, bool, etc.
            if content is not None and not isinstance(content, (list, dict)):
                return str(content).strip()

    # Strategy 2: Direct content key on response root
    if "content" in data:
        c = data["content"]
        if isinstance(c, str):
            return c.strip()
        if isinstance(c, list):
            parts = [item.get("text", "") for item in c if isinstance(item, dict)]
            return " ".join(parts).strip()
        if not isinstance(c, (list, dict)):
            return str(c).strip()

    # Strategy 3: reasoning_content as fallback content
    if "choices" in data:
        choices = data["choices"]
        if choices and isinstance(choices, list) and len(choices) > 0:
            msg = choices[0].get("message") or {}
            rc = msg.get("reasoning_content")
            if rc and isinstance(rc, str):
                return rc.strip()

    # Strategy 4: Non-standard response keys
    for key in ("output", "text", "response", "result", "generated_text", "completion"):
        if key in data:
            val = data[key]
            if isinstance(val, str):
                return val.strip()
            if isinstance(val, list):
                parts = [item.get("text", "") for item in val if isinstance(item, dict)]
                joined = " ".join(parts)
                if joined.strip():
                    return joined.strip()

    # Strategy 5: Deep fallback — iterate all keys for first string value
    for key, val in data.items():
        if isinstance(val, str) and len(val) > 10:
            return val.strip()
        # Check nested message-like structures
        if isinstance(val, dict):
            for sub_key in ("content", "text", "output", "message", "response"):
                if sub_key in val and isinstance(val[sub_key], str):
                    return val[sub_key].strip()

    return ""


def _robust_extract_reasoning(data: dict) -> str:
    """Extract reasoning/thinking content from any response format."""
    if "choices" in data:
        choices = data["choices"]
        if choices and isinstance(choices, list) and len(choices) > 0:
            msg = choices[0].get("message") or {}
            for key in ("reasoning_content", "reasoning", "thinking", "thought"):
                val = msg.get(key)
                if val and isinstance(val, str):
                    return val.strip()
                if val and isinstance(val, list):
                    parts = [item.get("text", "") for item in val if isinstance(item, dict)]
                    return " ".join(parts).strip()
    # Root-level reasoning keys
    for key in ("reasoning_content", "reasoning", "thinking", "thought"):
        if key in data and isinstance(data[key], str):
            return data[key].strip()
    return ""


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
    # Only add Authorization header if api_key is provided
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
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
) -> AsyncGenerator[dict, None]:
    """Streaming POST to a chat/completions endpoint (SSE).
    Yields dicts: {"type": "content", "content": str} or {"type": "reasoning", "content": str}.
    """
    client = _get_httpx_client()
    body = {
        "model": model,
        "messages": messages,
        "temperature": kwargs.get("temperature", 0.3),
        "max_tokens": kwargs.get("max_tokens", 2048),
        "stream": True,
    }
    # Only add Authorization header if api_key is provided
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
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
                        reasoning = delta.get("reasoning_content") or ""
                        # Yield reasoning FIRST so UI shows thinking before answer
                        if reasoning:
                            yield {"type": "reasoning", "content": reasoning}
                        if text:
                            yield {"type": "content", "content": text}
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
        print(f"=== OPCODE API RESPONSE (raw) ===\n{json.dumps(data, ensure_ascii=False, default=str)[:2000]}", flush=True)
        content = _robust_extract_content(data)

        # Fallback: reasoning-only response → retry without system prompt
        reasoning = _robust_extract_reasoning(data)
        if not content and reasoning:
            print(f"=== FALLBACK: reasoning-only, retrying without system prompt ===", flush=True)
            retry_messages = [{"role": "user", "content": prompt}]
            retry_data = await _chat_completion(url, api_key, resolved_model, retry_messages)
            print(f"=== OPCODE API FALLBACK RESPONSE (raw) ===\n{json.dumps(retry_data, ensure_ascii=False, default=str)[:2000]}", flush=True)
            content = _robust_extract_content(retry_data)
        print(f"Status: OK, content: {content[:200] if content else '(empty)'}, reasoning: {bool(reasoning)}", flush=True)
        return content
    except RuntimeError:
        raise
    except Exception as exc:
        print(f"=== OPCODE API ERROR === {exc}", flush=True)
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"OpenCode API error: {exc}")


# ── Generation (streaming) ──────────────────────────────────────────────────


async def generate_stream(prompt: str, model: str = "deepseek-v4-flash-free", system: Optional[str] = None) -> AsyncGenerator[dict, None]:
    """Stream using the env-configured API key.
    Yields dicts: {"type": "content", "content": str} or {"type": "reasoning", "content": str}.
    """
    key = _api_key()
    url = _base_url()
    async for chunk in _generate_stream_with_key(prompt, model, system, key, url):
        yield chunk


async def generate_stream_with_key(
    prompt: str,
    model: str = "deepseek-v4-flash-free",
    system: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """Stream using an externally-provided API key and base URL (from DB providers).
    Yields dicts: {"type": "content", "content": str} or {"type": "reasoning", "content": str}.
    """
    key = api_key or _api_key()
    url = base_url or _base_url()
    async for chunk in _generate_stream_with_key(prompt, model, system, key, url):
        yield chunk


async def _generate_stream_with_key(
    prompt: str,
    model: str,
    system: Optional[str],
    api_key: str,
    base_url: str,
) -> AsyncGenerator[dict, None]:
    if not api_key:
        raise RuntimeError("OpenCode API key is not configured.")

    resolved_model = _resolve_model_id(model)
    # Build URL: use DB base_url if given, otherwise catalog lookup
    if base_url:
        b = base_url.strip().rstrip("/")
        url = b if b.endswith("/chat/completions") else b + "/chat/completions"
    else:
        url = _get_url_for_model(model)

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
        async for event in _chat_completion_stream(url, api_key, resolved_model, messages):
            if event.get("type") == "content":
                content_yielded = True
            elif event.get("type") == "reasoning":
                reasoning_text += event.get("content", "")
            yield event

        # Fallback: reasoning-only → retry without system
        if not content_yielded and reasoning_text.strip():
            print(f"=== FALLBACK: reasoning-only, retrying without system prompt ===", flush=True)
            retry_messages = [{"role": "user", "content": prompt}]
            async for event in _chat_completion_stream(url, api_key, resolved_model, retry_messages):
                if event.get("type") == "content":
                    content_yielded = True
                yield event
            if not content_yielded:
                yield {"type": "content", "content": "I can see you're asking about this. Could you rephrase or be more specific?"}

    except RuntimeError:
        raise
    except Exception as exc:
        print(f"=== OPCODE API STREAM ERROR === {exc}", flush=True)
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"OpenCode API streaming failed: {exc}")
