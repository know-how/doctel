import logging
import os
import json
from typing import Optional, List, Dict, AsyncGenerator
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

HF_MODEL_ID = "huggingface-api"

_DEFAULT_BASE_URL = "https://api-inference.huggingface.co/v1"
_DEFAULT_MODEL = "meta-llama/Llama-4-Maverick-17B-128E-Instruct"
_TIMEOUT = 120.0

MODELS = [
    {"id": "huggingface/llama4-maverick", "name": "Llama 4 Maverick 17B Instruct", "provider": "meta", "tier": "cloud", "input_price": 0, "output_price": 0},
]

_client: Optional[AsyncOpenAI] = None
_client_api_key: Optional[str] = None
_client_base_url: Optional[str] = None


def _get_client() -> AsyncOpenAI:
    global _client, _client_api_key, _client_base_url
    api_key = _api_key()
    base_url = _base_url()
    if _client is None or _client_api_key != api_key or _client_base_url != base_url:
        _client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=_TIMEOUT)
        _client_api_key = api_key
        _client_base_url = base_url
    return _client


def _api_key() -> str:
    return os.getenv("HF_API_KEY", "").strip()


def _base_url() -> str:
    url = os.getenv("HF_BASE_URL", "").strip()
    if url:
        url = url.rstrip("/")
        suffix = "/chat/completions"
        if url.endswith(suffix):
            url = url[: -len(suffix)]
        return url
    return _DEFAULT_BASE_URL


def _model_name() -> str:
    return os.getenv("HF_MODEL", _DEFAULT_MODEL).strip()


def is_configured() -> bool:
    return bool(_api_key())


def get_available_models() -> List[Dict]:
    return MODELS if is_configured() else []


def get_display_name(model_id: str) -> str:
    for m in MODELS:
        if m["id"] == model_id:
            return f"{m['name']} (HuggingFace)"
    return f"HuggingFace ({model_id})"


def _resolve_model_id(model_id: str) -> str:
    if model_id.startswith("huggingface/"):
        return _model_name()
    return model_id


async def generate(prompt: str, model: str = "huggingface/llama4-maverick", system: Optional[str] = None) -> str:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("HF_API_KEY is not configured. Get one at https://huggingface.co/settings/tokens")

    client = _get_client()
    resolved_model = _resolve_model_id(model)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    api_key_masked = api_key[:8] + "..." if len(api_key) > 8 else "***"
    print(f"\n=== HF API REQUEST (generate) ===", flush=True)
    print(f"URL: {_base_url()}/chat/completions", flush=True)
    print(f"Model: {resolved_model}", flush=True)
    print(f"Messages: {json.dumps(messages, ensure_ascii=False)}", flush=True)
    print(f"Key: {api_key_masked}", flush=True)

    try:
        resp = await client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
        )
        print(f"=== HF API RESPONSE ===", flush=True)
        print(f"Status: OK, content: {(resp.choices[0].message.content or '')[:200]}", flush=True)
        return resp.choices[0].message.content or ""
    except Exception as exc:
        status = getattr(exc, "status_code", 0)
        print(f"=== HF API ERROR === status={status} error={exc}", flush=True)
        import traceback
        traceback.print_exc()
        if status == 401:
            raise RuntimeError("HuggingFace API key is invalid. Check your key at https://huggingface.co/settings/tokens")
        if status == 402:
            raise RuntimeError("HuggingFace API payment required. Add a payment method at https://huggingface.co/settings/billing")
        if status == 429:
            raise RuntimeError("HuggingFace API rate limit exceeded. Wait a moment or upgrade to PRO.")
        if status == 404:
            raise RuntimeError(f"Model '{resolved_model}' is not available on HuggingFace Inference API.")
        raise RuntimeError(f"HuggingFace API error: {exc}")


async def generate_stream(prompt: str, model: str = "huggingface/llama4-maverick", system: Optional[str] = None) -> AsyncGenerator[str, None]:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("HF_API_KEY is not configured.")

    client = _get_client()
    resolved_model = _resolve_model_id(model)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    api_key_masked = api_key[:8] + "..." if len(api_key) > 8 else "***"
    print(f"\n=== HF API STREAM REQUEST ===", flush=True)
    print(f"URL: {_base_url()}/chat/completions", flush=True)
    print(f"Model: {resolved_model}", flush=True)
    print(f"Key: {api_key_masked}", flush=True)

    try:
        stream = await client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
            stream=True,
        )
        print(f"=== HF API STREAM STARTED ===", flush=True)
        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
    except Exception as exc:
        status = getattr(exc, "status_code", 0)
        print(f"=== HF API STREAM ERROR === status={status} error={exc}", flush=True)
        if status == 401:
            raise RuntimeError("HuggingFace API key is invalid.")
        if status == 429:
            raise RuntimeError("HuggingFace API rate limit exceeded.")
        raise RuntimeError(f"HuggingFace API streaming failed: {exc}")
