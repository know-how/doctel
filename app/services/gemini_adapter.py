"""
gemini_adapter.py — Google Gemini API adapter.

Handles Gemini's native generateContent / streamGenerateContent protocol.
"""

from __future__ import annotations

import json
import logging
import httpx
import asyncio
from typing import Optional, AsyncGenerator

logger = logging.getLogger(__name__)

_TIMEOUT = 120.0
_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

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
    api_key: str,
    model: str,
    prompt: str,
    system: Optional[str] = None,
) -> str:
    """Call Gemini's generateContent API."""
    client = _get_client()

    # Gemini uses model name directly, strip any prefix
    model_name = model.split("/")[-1] if "/" in model else model
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"

    url = f"{_DEFAULT_BASE_URL}/{model_name}:generateContent?key={api_key}"

    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": f"System: {system}\n\nUser: {prompt}"}]})
    else:
        contents.append({"role": "user", "parts": [{"text": prompt}]})

    body = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        },
    }

    print(f"[Gemini-Adapter] POST model={model_name}", flush=True)

    resp = await client.post(url, json=body, headers={"Content-Type": "application/json"})
    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise RuntimeError(f"Gemini API error {resp.status_code}: {detail}")

    data = resp.json()
    candidates = data.get("candidates") or []
    if candidates and candidates[0].get("content", {}).get("parts"):
        return candidates[0]["content"]["parts"][0].get("text", "").strip()
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# STREAMING
# ═══════════════════════════════════════════════════════════════════════════════

async def chat_completion_stream(
    *,
    api_key: str,
    model: str,
    prompt: str,
    system: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Call Gemini's streamGenerateContent API."""
    client = _get_client()

    model_name = model.split("/")[-1] if "/" in model else model
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"

    url = f"{_DEFAULT_BASE_URL}/{model_name}:streamGenerateContent?alt=sse&key={api_key}"

    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": f"System: {system}\n\nUser: {prompt}"}]})
    else:
        contents.append({"role": "user", "parts": [{"text": prompt}]})

    body = {
        "contents": contents,
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
    }

    print(f"[Gemini-Adapter] STREAM model={model_name}", flush=True)

    try:
        async with asyncio.timeout(60.0):
            async with client.stream("POST", url, json=body, headers={"Content-Type": "application/json"}) as resp:
                if resp.status_code >= 400:
                    detail = await resp.aread()
                    raise RuntimeError(f"Gemini stream error {resp.status_code}: {detail[:500]}")
                prefix = "data: "
                async for line in resp.aiter_lines():
                    if not line or not line.startswith(prefix):
                        continue
                    payload = line[len(prefix):].strip()
                    if not payload:
                        continue
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    candidates = chunk.get("candidates") or []
                    for c in candidates:
                        parts = c.get("content", {}).get("parts") or []
                        for p in parts:
                            text = p.get("text") or ""
                            if text:
                                yield text
    except asyncio.TimeoutError:
        raise RuntimeError("Gemini streaming timed out after 60 seconds")


# ═══════════════════════════════════════════════════════════════════════════════
# EMBEDDING
# ═══════════════════════════════════════════════════════════════════════════════

async def embed_text(
    *,
    api_key: str,
    model: str,
    input_text: str,
) -> list[float]:
    """Generate an embedding vector via Gemini's ``embedContent`` API.

    Gemini embedding endpoint: ``POST {base_url}/models/{model}:embedContent``

    Args:
        api_key: Gemini API key.
        model: Embedding model name (e.g. ``text-embedding-004``, ``models/text-embedding-004``).
        input_text: The text string to embed.

    Returns:
        A single list of floats representing the embedding vector.

    Raises:
        RuntimeError: If the Gemini API returns an error.
    """
    client = _get_client()

    model_name = model.split("/")[-1] if "/" in model else model
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"

    url = f"{_DEFAULT_BASE_URL}/{model_name}:embedContent?key={api_key}"

    body = {
        "model": model_name,
        "content": {
            "parts": [{"text": input_text}]
        },
    }

    print(f"[Gemini-Adapter] embed model={model_name} input_len={len(input_text)}", flush=True)

    resp = await client.post(url, json=body, headers={"Content-Type": "application/json"})
    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise RuntimeError(f"Gemini embedding error {resp.status_code}: {detail}")

    data = resp.json()
    embedding = data.get("embedding", {}).get("values")
    if not embedding:
        raise RuntimeError(f"Gemini embedding response missing 'embedding.values': {json.dumps(data)[:300]}")

    result = [float(v) for v in embedding]
    print(f"[Gemini-Adapter] Embedding dim={len(result)} model={model}", flush=True)
    return result
