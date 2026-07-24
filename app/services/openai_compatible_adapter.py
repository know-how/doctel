"""
openai_compatible_adapter.py — OpenAI-compatible chat/completions API adapter.

Handles any provider speaking the standard /chat/completions protocol:
OpenCode, DeepSeek, OpenAI, Mistral, Groq, Together, OpenRouter,
LM Studio, vLLM, Ollama, HuggingFace (TGI/text-generation-inference), etc.
"""

from __future__ import annotations

import json
import logging
import httpx
import asyncio
from typing import Optional, AsyncGenerator

logger = logging.getLogger(__name__)

_TIMEOUT = 120.0

_client: Optional[httpx.AsyncClient] = None


class ProviderError(RuntimeError):
    """Base class for provider errors with structured info."""
    def __init__(self, message: str, *, provider_name: str = "", status_code: int = 0, raw_error: str = ""):
        super().__init__(message)
        self.provider_name = provider_name
        self.status_code = status_code
        self.raw_error = raw_error


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _client


# ═══════════════════════════════════════════════════════════════════════════════
# Robust response extraction helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _extract_content(data: dict) -> str:
    """Extract content text from any /chat/completions response format."""
    # Strategy 1: Standard choices path
    if "choices" in data:
        choices = data["choices"]
        if choices and isinstance(choices, list) and len(choices) > 0:
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if isinstance(content, str):
                return content.strip()
            # Array of {type, text} objects (OpenAI structured)
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append(item.get("text", ""))
                        elif item.get("text"):
                            parts.append(item["text"])
                joined = " ".join(parts).strip()
                if joined:
                    return joined
            # Non-string content (number, bool, etc.)
            if content is not None and not isinstance(content, (list, dict)):
                return str(content).strip()

    # Strategy 2: Direct content key
    if "content" in data:
        c = data["content"]
        if isinstance(c, str):
            return c.strip()
        if isinstance(c, list):
            parts = [item.get("text", "") for item in c if isinstance(item, dict)]
            return " ".join(parts).strip()

    # Strategy 3: Non-standard keys
    for key in ("output", "text", "response", "result", "generated_text", "completion"):
        if key in data and isinstance(data[key], str):
            return data[key].strip()

    # Strategy 5: Deep fallback
    for key, val in data.items():
        if isinstance(val, str) and len(val) > 10:
            return val.strip()
        if isinstance(val, dict):
            for sub_key in ("content", "text", "output", "message", "response"):
                if sub_key in val and isinstance(val[sub_key], str):
                    return val[sub_key].strip()

    return ""


def _extract_reasoning(data: dict) -> str:
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
    for key in ("reasoning_content", "reasoning", "thinking", "thought"):
        if key in data and isinstance(data[key], str):
            return data[key].strip()
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# NON-STREAMING
# ═══════════════════════════════════════════════════════════════════════════════

async def chat_completion(
    *,
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    system: Optional[str] = None,
) -> tuple[str, str]:
    """POST to /chat/completions, return (response_text, reasoning_text)."""
    client = _get_client()
    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 8192,
    }
    # Only add Authorization header if api_key is provided
    # Ollama and local providers don't require API keys
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    api_key_masked = api_key[:8] + "..." if len(api_key) > 8 else ("(none)" if not api_key else "***")
    print(f"[OpenAI-Adapter] POST {url} model={model} key={api_key_masked}", flush=True)

    provider_name = url.split("/")[2] if "/" in url else "unknown"
    
    try:
        resp = await client.post(url, json=body, headers=headers)
    except asyncio.TimeoutError:
        raise ProviderError(
            f"Provider request timed out. The provider '{provider_name}' is taking too long to respond.",
            provider_name=provider_name,
            status_code=0,
            raw_error="Timeout"
        )
    except httpx.ConnectError as e:
        raise ProviderError(
            f"Connection failed to provider '{provider_name}'. Please check the provider URL and network connectivity.",
            provider_name=provider_name,
            status_code=0,
            raw_error=str(e)
        )
    except httpx.NetworkError as e:
        raise ProviderError(
            f"Network error connecting to provider '{provider_name}'. Please check your internet connection.",
            provider_name=provider_name,
            status_code=0,
            raw_error=str(e)
        )
    
    if resp.status_code >= 400:
        detail = resp.text[:500]
        # Classify error by HTTP status code
        provider_name = url.split("/")[2] if "/" in url else "unknown"
        if resp.status_code == 429:
            raise ProviderError(
                f"Provider rate limit exceeded (429). Please wait and try again.",
                provider_name=provider_name,
                status_code=429,
                raw_error=detail
            )
        elif resp.status_code == 402:
            raise ProviderError(
                f"Provider credits exhausted (402). Please add funds to your account.",
                provider_name=provider_name,
                status_code=402,
                raw_error=detail
            )
        elif resp.status_code == 401:
            raise ProviderError(
                f"Invalid provider API key (401). Please check your API key in Admin > Providers.",
                provider_name=provider_name,
                status_code=401,
                raw_error=detail
            )
        elif resp.status_code == 403:
            raise ProviderError(
                f"Provider access denied (403). Please check your API permissions.",
                provider_name=provider_name,
                status_code=403,
                raw_error=detail
            )
        elif resp.status_code >= 500:
            raise ProviderError(
                f"Provider server error ({resp.status_code}). The provider's servers are experiencing issues.",
                provider_name=provider_name,
                status_code=resp.status_code,
                raw_error=detail
            )
        else:
            raise ProviderError(
                f"Provider API error {resp.status_code}: {detail[:200]}",
                provider_name=provider_name,
                status_code=resp.status_code,
                raw_error=detail
            )

    data = resp.json()
    print(f"[OpenAI-Adapter] RAW RESPONSE:\n{json.dumps(data, ensure_ascii=False, default=str)[:2000]}", flush=True)

    content = _extract_content(data)
    reasoning_text = _extract_reasoning(data)

    # ── Retry logic for incomplete responses ────────────────────────────
    # DeepSeek-style reasoning models may exhaust their output token budget
    # on chain-of-thought (finish_reason="length"), leaving content empty.
    # Retry with a higher max_tokens limit when this happens.
    finish_reason = None
    choices = data.get("choices") or []
    if choices and isinstance(choices, list) and len(choices) > 0:
        finish_reason = choices[0].get("finish_reason")

    should_retry = not content and (
        finish_reason == "length"  # token limit hit
        or (reasoning_text and system)  # reasoning-only (old heuristic)
    )
    if should_retry:
        logger.info(
            "Reasoning-only/incomplete response (finish_reason=%s, reasoning_len=%d), "
            "retrying with higher max_tokens",
            finish_reason, len(reasoning_text),
        )
        # Retry without system prompt to save token budget
        retry_messages = [{"role": "user", "content": prompt}]
        retry_body = {"model": model, "messages": retry_messages, "temperature": 0.3, "max_tokens": 16384}
        resp2 = await client.post(url, json=retry_body, headers=headers)
        if resp2.status_code < 400:
            data2 = resp2.json()
            content = _extract_content(data2)
            if not reasoning_text:
                reasoning_text = _extract_reasoning(data2)

    return content, reasoning_text or ""


# ═══════════════════════════════════════════════════════════════════════════════
# STREAMING
# ═══════════════════════════════════════════════════════════════════════════════

async def chat_completion_stream(
    *,
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    system: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """Streaming POST to /chat/completions (SSE).
    Yields dicts: {"type": "content", "content": str} or {"type": "reasoning", "content": str}.
    """
    client = _get_client()
    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 8192,
        "stream": True,
    }
    # Only add Authorization header if api_key is provided
    # Ollama and local providers don't require API keys
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    api_key_masked = api_key[:8] + "..." if len(api_key) > 8 else ("(none)" if not api_key else "***")

    provider_name = url.split("/")[2] if "/" in url else "unknown"
    logger = logging.getLogger(__name__)
    logger.info(
        "[REASONING] adapter_stream_start — model=%s | provider=%s | "
        "prompt_len=%d | system_prompt=%s",
        model,
        provider_name,
        len(prompt),
        "present" if system else "absent",
    )
    try:
        async with asyncio.timeout(60.0):
            async with client.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code >= 400:
                    detail = await resp.aread()
                    detail_str = detail.decode('utf-8', errors='ignore')[:500] if isinstance(detail, bytes) else str(detail)[:500]
                    # Classify error by HTTP status code
                    if resp.status_code == 429:
                        raise ProviderError(
                            "Provider rate limit exceeded (429). Please wait and try again.",
                            provider_name=provider_name, status_code=429, raw_error=detail_str
                        )
                    elif resp.status_code == 402:
                        raise ProviderError(
                            "Provider credits exhausted (402). Please add funds to your account.",
                            provider_name=provider_name, status_code=402, raw_error=detail_str
                        )
                    elif resp.status_code == 401:
                        raise ProviderError(
                            "Invalid provider API key (401). Please check your API key in Admin > Providers.",
                            provider_name=provider_name, status_code=401, raw_error=detail_str
                        )
                    elif resp.status_code == 403:
                        raise ProviderError(
                            "Provider access denied (403). Please check your API permissions.",
                            provider_name=provider_name, status_code=403, raw_error=detail_str
                        )
                    elif resp.status_code >= 500:
                        raise ProviderError(
                            f"Provider server error ({resp.status_code}). The provider's servers are experiencing issues.",
                            provider_name=provider_name, status_code=resp.status_code, raw_error=detail_str
                        )
                    else:
                        raise ProviderError(
                            f"Provider API error {resp.status_code}: {detail_str[:200]}",
                            provider_name=provider_name, status_code=resp.status_code, raw_error=detail_str
                        )
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
                        # Yield reasoning FIRST so UI can display thinking before answer
                        if reasoning:
                            yield {"type": "reasoning", "content": reasoning}
                        if text:
                            yield {"type": "content", "content": text}
    except asyncio.TimeoutError:
        raise ProviderError(
            f"Provider streaming timed out after 60 seconds. The provider '{provider_name}' is not responding.",
            provider_name=provider_name,
            status_code=0,
            raw_error="Streaming timeout"
        )
    except httpx.ConnectError as e:
        raise ProviderError(
            f"Connection failed to provider '{provider_name}'. Please check the provider URL and network connectivity.",
            provider_name=provider_name,
            status_code=0,
            raw_error=str(e)
        )
    except httpx.NetworkError as e:
        raise ProviderError(
            f"Network error connecting to provider '{provider_name}'. Please check your internet connection.",
            provider_name=provider_name,
            status_code=0,
            raw_error=str(e)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EMBEDDING
# ═══════════════════════════════════════════════════════════════════════════════

async def embed_text(
    *,
    url: str,
    api_key: str,
    model: str,
    input_text: str,
) -> list[float]:
    """Generate an embedding vector via an OpenAI-compatible ``/embeddings`` endpoint.

    Expected API format (OpenAI-compatible):
    .. code-block:: http

        POST {url}
        Content-Type: application/json
        Authorization: Bearer {api_key}

        {"model": "{model}", "input": "{input_text}"}

    Expected response shape:
    .. code-block:: json

        {"data": [{"embedding": [0.123, ...], "index": 0}], "model": "..."}

    Args:
        url: Full URL of the embeddings endpoint (e.g. ``http://localhost:11434/v1/embeddings``).
        api_key: API key (Bearer token) for the provider.
        model: Embedding model name (e.g. ``nomic-embed-text``, ``text-embedding-ada-002``).
        input_text: The text string to embed.

    Returns:
        A single list of floats representing the embedding vector.

    Raises:
        RuntimeError: If the provider returns an HTTP error or the response
            cannot be parsed.
    """
    client = _get_client()

    body = {
        "model": model,
        "input": input_text,
    }
    # Only add Authorization header if api_key is provided
    # Ollama and local providers don't require API keys
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    api_key_masked = api_key[:8] + "..." if len(api_key) > 8 else ("(none)" if not api_key else "***")
    print(f"[OpenAI-Adapter] POST {url} model={model} key={api_key_masked} input_len={len(input_text)}", flush=True)

    resp = await client.post(url, json=body, headers=headers)
    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise RuntimeError(f"Embedding API error {resp.status_code}: {detail}")

    data = resp.json()

    # OpenAI-compatible response: {"data": [{"embedding": [...], "index": 0}]}
    data_list = data.get("data") or []
    if not data_list:
        raise RuntimeError(f"Embedding response missing 'data' array: {json.dumps(data)[:300]}")

    embedding = data_list[0].get("embedding")
    if not embedding:
        raise RuntimeError(f"Embedding response missing embedding vector: {json.dumps(data)[:300]}")

    # Also handle Ollama's /api/embed response format: {"model": "...", "embeddings": [[...]]}
    if not isinstance(embedding, list):
        # Try Ollama format
        embeddings_alt = data.get("embeddings")
        if embeddings_alt and isinstance(embeddings_alt, list) and len(embeddings_alt) > 0:
            embedding = embeddings_alt[0]

    if not isinstance(embedding, list):
        raise RuntimeError(f"Embedding vector is not a list: {type(embedding).__name__}")

    # Convert to float list
    result = [float(v) for v in embedding]

    print(f"[OpenAI-Adapter] Embedding dim={len(result)} model={model}", flush=True)
    return result
