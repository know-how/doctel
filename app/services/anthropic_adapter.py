"""
anthropic_adapter.py — Anthropic Messages API adapter.

Handles Anthropic's native /v1/messages protocol.
"""

from __future__ import annotations

import json
import logging
import httpx
import asyncio
from typing import Optional, AsyncGenerator

logger = logging.getLogger(__name__)

_TIMEOUT = 120.0
_DEFAULT_BASE_URL = "https://api.anthropic.com/v1"

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _client


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
) -> str:
    """POST to Anthropic /v1/messages, return text response."""
    client = _get_client()

    # Use provided URL or default
    req_url = url if url and "/messages" in url else f"{_DEFAULT_BASE_URL}/messages"

    messages: list = [{"role": "user", "content": prompt}]
    body: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
    }
    if system:
        body["system"] = system

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    print(f"[Anthropic-Adapter] POST model={model}", flush=True)

    resp = await client.post(req_url, json=body, headers=headers)
    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise RuntimeError(f"Anthropic API error {resp.status_code}: {detail}")

    data = resp.json()
    content = data.get("content") or []
    if isinstance(content, list) and content:
        return "".join(block.get("text", "") for block in content if block.get("type") == "text").strip()
    return ""


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
) -> AsyncGenerator[str, None]:
    """Streaming POST to Anthropic /v1/messages."""
    client = _get_client()

    req_url = url if url and "/messages" in url else f"{_DEFAULT_BASE_URL}/messages"

    messages: list = [{"role": "user", "content": prompt}]
    body: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
        "stream": True,
    }
    if system:
        body["system"] = system

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    print(f"[Anthropic-Adapter] STREAM model={model}", flush=True)

    try:
        async with asyncio.timeout(60.0):
            async with client.stream("POST", req_url, json=body, headers=headers) as resp:
                if resp.status_code >= 400:
                    detail = await resp.aread()
                    raise RuntimeError(f"Anthropic stream error {resp.status_code}: {detail[:500]}")
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        text = delta.get("text", "")
                        if text:
                            yield text
    except asyncio.TimeoutError:
        raise RuntimeError("Anthropic streaming timed out after 60 seconds")


# ═══════════════════════════════════════════════════════════════════════════════
# EMBEDDING
# ═══════════════════════════════════════════════════════════════════════════════

async def embed_text(
    *,
    api_key: str,
    model: str,
    input_text: str,
) -> list[float]:
    """Embedding via Anthropic is not currently supported.

    Anthropic does not expose a public embedding API at this time.
    This stub raises a clear error so callers can fall back gracefully.

    Raises:
        RuntimeError: Always — Anthropic has no embedding endpoint.
    """
    raise RuntimeError(
        f"Anthropic does not provide an embedding API. "
        f"Cannot embed text with model '{model}'. "
        f"Please configure a different provider (e.g. Ollama, OpenAI) for embedding tasks."
    )
