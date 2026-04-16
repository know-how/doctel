"""
gemini_service.py – Google Gemini API integration for Doctel.

Environment variables (add to your .env file):
  GEMINI_API_KEY   – free-tier key from https://aistudio.google.com/apikey
    GEMINI_MODEL     – model to use (default: gemini-2.5-flash)

The sentinel model ID "gemini-api" is used throughout Doctel to identify
this backend.  When the backend sees that model ID it routes the generation
request here instead of to Ollama.  RAG embedding still uses Ollama/nomic if
it is available; generation always uses Gemini when this model is selected.
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── public constant ───────────────────────────────────────────────────────────
GEMINI_MODEL_ID = "gemini-api"          # Doctel-internal sentinel used everywhere
GEMINI_DISPLAY_NAME = "Gemini 2.5 Flash (API)"

_DEFAULT_MODEL = "gemini-2.5-flash"
_LEGACY_MODEL_ALIASES = {
    "gemini-1.5-flash": _DEFAULT_MODEL,
    "gemini-1.5-flash-latest": _DEFAULT_MODEL,
}

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_TIMEOUT = 60.0


# ── helpers ───────────────────────────────────────────────────────────────────

def _api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip()


def _model_name() -> str:
    configured = os.getenv("GEMINI_MODEL", _DEFAULT_MODEL).strip()
    return _LEGACY_MODEL_ALIASES.get(configured, configured)


def is_configured() -> bool:
    """Return True if a GEMINI_API_KEY is present in the environment."""
    return bool(_api_key())


# ── generation ────────────────────────────────────────────────────────────────

async def generate(prompt: str, system: Optional[str] = None) -> str:
    """
    Call the Gemini generateContent REST endpoint and return the text response.

    The system prompt is injected as an initial user+model exchange because
    Gemini v1beta does not expose a dedicated system_instruction field in its
    basic generate endpoint.

    Raises RuntimeError with a user-readable message on configuration or API
    errors so callers can surface them gracefully.
    """
    api_key = _api_key()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. "
            "Add GEMINI_API_KEY=<your_key> to your .env file and restart the server."
        )

    model = _model_name()
    url = f"{_BASE_URL}/models/{model}:generateContent?key={api_key}"

    # Build conversation turns
    contents: list[dict] = []
    if system:
        # Simulate system prompt via a user→model preamble turn
        contents.append({"role": "user", "parts": [{"text": system}]})
        contents.append({"role": "model", "parts": [{"text": "Understood. I will follow those instructions."}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    body = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        },
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                detail = exc.response.json().get("error", {}).get("message", "")
            except Exception:
                pass
            status = exc.response.status_code
            if status == 400:
                raise RuntimeError(f"Gemini API bad request: {detail or str(exc)}")
            if status == 404:
                raise RuntimeError(
                    f"Gemini model '{model}' is not available for generateContent. "
                    f"Use a supported model such as '{_DEFAULT_MODEL}' or 'gemini-flash-latest'."
                )
            if status == 403:
                raise RuntimeError(
                    "Gemini API key is invalid or has exceeded its quota. "
                    "Check your key at https://aistudio.google.com/apikey"
                )
            if status == 429:
                raise RuntimeError(
                    "Gemini API rate limit exceeded. "
                    "Wait a moment and try again, or upgrade your quota."
                )
            raise RuntimeError(f"Gemini API error {status}: {detail or str(exc)}")
        except httpx.TimeoutException:
            raise RuntimeError("Gemini API request timed out. Check your network and retry.")
        except Exception as exc:
            raise RuntimeError(f"Gemini API request failed: {exc}")

    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        # Safety-filter or empty response
        finish = ""
        try:
            finish = data["candidates"][0].get("finishReason", "")
        except Exception:
            pass
        if finish in ("SAFETY", "RECITATION"):
            raise RuntimeError(
                f"Gemini refused to answer (finish reason: {finish}). "
                "Try rephrasing the question."
            )
        raise RuntimeError(f"Unexpected Gemini response format: {data}")
