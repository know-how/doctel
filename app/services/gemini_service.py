"""
gemini_service.py – Google Gemini API integration for Doctel.

Environment variables (add to your .env file):
  GEMINI_API_KEY   – free-tier key from https://aistudio.google.com/apikey
  GEMINI_MODEL     – model to use (default: gemini-2.5-flash)

Features:
  - Text generation via generateContent
  - Vision analysis (images, PDFs, DOCX)
  - Document ingestion and analysis
  - Synthetic training data generation

The sentinel model ID "gemini-api" is used throughout Doctel to identify
this backend.  When the backend sees that model ID it routes the generation
request here instead of to Ollama.  RAG embedding still uses Ollama/nomic if
it is available; generation always uses Gemini when this model is selected.
"""
import logging
import os
import base64
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

# ── public constant ───────────────────────────────────────────────────────────
GEMINI_MODEL_ID = "gemini-api"          # Doctel-internal sentinel used everywhere

_DEFAULT_MODEL = "gemini-2.5-flash"
_LEGACY_MODEL_ALIASES = {
    "gemini-1.5-flash": _DEFAULT_MODEL,
    "gemini-1.5-flash-latest": _DEFAULT_MODEL,
}

def get_display_name() -> str:
    """Get the display name for the configured Gemini model from environment."""
    model = _model_name()
    model_lower = model.lower()
    
    # Clean up model name for display
    display_map = {
        "gemini-2.5-flash": "Gemini 2.5 Flash (API)",
        "gemini-3.1-pro": "Gemini 3.1 Pro (API)",
        "gemini-3.1-pro-preview": "Gemini 3.1 Pro Preview (API)",
        "gemini-flash": "Gemini Flash (API)",
        "gemini-pro": "Gemini Pro (API)",
    }
    
    # Exact match
    if model_lower in display_map:
        return display_map[model_lower]
    
    # Partial match
    for key, display in display_map.items():
        if key in model_lower:
            return display
    
    # Fallback: clean up the model name
    return f"Gemini {model.replace('gemini-', '').replace('_', ' ').title()} (API)"

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_TIMEOUT = 90.0

_shared_client: Optional[httpx.AsyncClient] = None


async def _get_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _shared_client


# ── helpers ───────────────────────────────────────────────────────────────────

def _settings() -> "Settings":
    from app.config import settings
    return settings


def _api_key() -> str:
    """Get API key from env, then file settings (DB override supported via settings proxy)."""
    val = os.getenv("GEMINI_API_KEY", "").strip()
    if val:
        return val
    return _settings().gemini_api_key


def _model_name() -> str:
    """Get model name from env, then file settings, then hardcoded default."""
    configured = os.getenv("GEMINI_MODEL", "").strip()
    if configured:
        return _LEGACY_MODEL_ALIASES.get(configured, configured)
    return _settings().gemini_model or _DEFAULT_MODEL


def is_configured() -> bool:
    """Return True if a GEMINI_API_KEY is present in the environment."""
    return bool(_api_key())


# ═══════════════════════════════════════════════════════════════════════════════
#  DB-AWARE ASYNC VERSIONS (for use with database-backed configuration)
# ═══════════════════════════════════════════════════════════════════════════════

async def get_api_key_db(db: "AsyncSession") -> str:
    """Get API key with DB override support. Priority: env > DB > file > empty."""
    val = os.getenv("GEMINI_API_KEY", "").strip()
    if val:
        return val
    
    from app.services import app_config_service as app_cfg
    db_val = await app_cfg.get_setting_str(db, "api.gemini_api_key", "")
    if db_val:
        return db_val
    
    return _settings().gemini_api_key


async def get_model_name_db(db: "AsyncSession") -> str:
    """Get model name with DB override support. Priority: env > DB > file > default."""
    configured = os.getenv("GEMINI_MODEL", "").strip()
    if configured:
        return _LEGACY_MODEL_ALIASES.get(configured, configured)
    
    from app.services import app_config_service as app_cfg
    db_val = await app_cfg.get_setting_str(db, "api.gemini_model", "")
    if db_val:
        return db_val
    
    return _settings().gemini_model or _DEFAULT_MODEL


async def is_configured_db(db: "AsyncSession") -> bool:
    """Return True if a GEMINI_API_KEY is present (checks env, then DB, then file)."""
    return bool(await get_api_key_db(db))


# ── generation ────────────────────────────────────────────────────────────────

async def generate(prompt: str, system: Optional[str] = None) -> str:
    """
    Call the Gemini generateContent REST endpoint and return the text response.

    The system prompt is passed via the systemInstruction field of the v1beta API,
    which provides better instruction-following than a preamble turn.

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
        # Use system_instruction field for v1beta API
        system_instruction = {"parts": [{"text": system}]}
    else:
        system_instruction = None
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    body = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        },
    }
    if system_instruction:
        body["systemInstruction"] = system_instruction

    client = await _get_client()
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
        if status == 422:
            raise RuntimeError(
                f"Gemini API rejected the request (422). The model '{model}' may not support this request format. "
                f"Detail: {detail or str(exc)}"
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


async def generate_stream(prompt: str, system: Optional[str] = None) -> AsyncGenerator[str, None]:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    model = _model_name()
    url = f"{_BASE_URL}/models/{model}:streamGenerateContent?alt=sse&key={api_key}"

    contents: list[dict] = []
    if system:
        system_instruction = {"parts": [{"text": system}]}
    else:
        system_instruction = None
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    body = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        },
    }
    if system_instruction:
        body["systemInstruction"] = system_instruction

    client = await _get_client()
    try:
        async with client.stream("POST", url, json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                if not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                try:
                    chunk = json.loads(payload)
                    parts = chunk.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    for part in parts:
                        text = part.get("text", "")
                        if text:
                            yield text
                except json.JSONDecodeError:
                    continue
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 403:
            raise RuntimeError("Gemini API key is invalid or quota exceeded.")
        if status == 429:
            raise RuntimeError("Gemini API rate limit exceeded.")
        if status == 422:
            raise RuntimeError(f"Gemini streaming rejected (422). Model '{_model_name()}' may not support streaming.")
        raise RuntimeError(f"Gemini streaming error {status}")
    except httpx.TimeoutException:
        raise RuntimeError("Gemini streaming request timed out.")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Gemini streaming failed: {exc}")


# ── vision & document analysis ────────────────────────────────────────────────

async def analyze_image(image_path: str, prompt: str = "Describe this image in detail.") -> str:
    """
    Analyze an image using Gemini vision capabilities.
    
    Args:
        image_path: Path to image file (PNG, JPG, GIF, WebP, BMP)
        prompt: Question or instruction for the model
        
    Returns:
        Text analysis of the image
        
    Raises:
        RuntimeError with user-readable message on API errors
    """
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    
    # Read and encode image
    image_path = Path(image_path)
    if not image_path.exists():
        raise RuntimeError(f"Image file not found: {image_path}")
    
    mime_type = _get_mime_type_for_image(str(image_path))
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode()
    
    model = _model_name()
    url = f"{_BASE_URL}/models/{model}:generateContent?key={api_key}"
    
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": mime_type, "data": image_data}},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        },
    }
    
    client = await _get_client()
    try:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"Vision analysis failed: {exc}")
    
    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected vision response: {data}")


async def analyze_document(
    file_path: str,
    prompt: str = "Summarize this document. Extract: title, key sections, main topics, entities.",
) -> Dict[str, Any]:
    """
    Analyze a document (PDF, DOCX, TXT, image) using Gemini.
    
    Args:
        file_path: Path to document
        prompt: Analysis prompt
        
    Returns:
        {
            "summary": str,
            "key_sections": List[str],
            "topics": List[str],
            "entities": List[str],
            "raw_response": str,
        }
        
    Raises:
        RuntimeError on API or file errors
    """
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    
    file_path = Path(file_path)
    if not file_path.exists():
        raise RuntimeError(f"Document file not found: {file_path}")
    
    # Handle different file types
    text_content = ""
    file_ext = file_path.suffix.lower()
    
    if file_ext == ".pdf":
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(file_path))
            text_content = "".join([page.extract_text() or "" for page in reader.pages])
        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}. Proceeding with partial content.")
    elif file_ext == ".docx":
        try:
            import docx
            doc = docx.Document(str(file_path))
            text_content = "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            logger.warning(f"DOCX extraction failed: {e}")
    elif file_ext in [".txt", ".md"]:
        text_content = file_path.read_text(encoding="utf-8", errors="ignore")
    elif file_ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"]:
        # For images, use vision analysis
        return {
            "summary": await analyze_image(str(file_path), prompt),
            "key_sections": [],
            "topics": [],
            "entities": [],
            "raw_response": await analyze_image(str(file_path), prompt),
        }
    
    if not text_content.strip():
        raise RuntimeError(f"No readable content in {file_path}")
    
    # Cap text to avoid token limits
    text_content = text_content[:10000]
    
    # Call Gemini with analysis prompt
    analysis_prompt = f"{prompt}\n\nDocument content:\n{text_content}"
    
    try:
        raw_response = await generate(analysis_prompt, system="You are a document analyst.")
    except RuntimeError as e:
        raise RuntimeError(f"Document analysis failed: {e}")
    
    # Parse response (try to extract structured data)
    result = {
        "summary": raw_response,
        "key_sections": _extract_sections(raw_response),
        "topics": _extract_topics(raw_response),
        "entities": _extract_entities(raw_response),
        "raw_response": raw_response,
    }
    
    return result


async def generate_synthetic_training_data(
    topic: str,
    num_examples: int = 10,
    instruction_style: str = "question_answer",
) -> List[Dict[str, str]]:
    """
    Generate synthetic training data for LoRA fine-tuning.
    
    Args:
        topic: Subject for generated examples
        num_examples: Number of examples to generate
        instruction_style: 'question_answer', 'instruction_output', 'few_shot'
        
    Returns:
        List of {"instruction": str, "output": str} dicts (HuggingFace format)
        
    Raises:
        RuntimeError on API errors
    """
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    
    # Build prompt for synthetic data
    if instruction_style == "question_answer":
        data_prompt = f"""Generate {num_examples} high-quality question-answer pairs about: {topic}

Format each as JSON:
{{"instruction": "question", "output": "detailed answer"}}

Return ONLY valid JSON array, no markdown."""
    elif instruction_style == "instruction_output":
        data_prompt = f"""Generate {num_examples} instruction-output pairs for: {topic}

Format each as JSON:
{{"instruction": "task description", "output": "result"}}

Return ONLY valid JSON array."""
    else:
        data_prompt = f"""Generate {num_examples} few-shot examples about: {topic}

Format each as JSON:
{{"instruction": "query", "output": "response"}}

Return ONLY valid JSON array."""
    
    try:
        raw_response = await generate(data_prompt)
    except RuntimeError as e:
        raise RuntimeError(f"Synthetic data generation failed: {e}")
    
    # Parse JSON response
    try:
        # Extract JSON array from response
        start_idx = raw_response.find("[")
        end_idx = raw_response.rfind("]") + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_str = raw_response[start_idx:end_idx]
            data = json.loads(json_str)
            return data if isinstance(data, list) else [data]
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse synthetic data JSON: {e}")
        return []
    
    return []


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_mime_type_for_image(path: str) -> str:
    """Get MIME type for image based on extension."""
    ext = Path(path).suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/jpeg")


def _extract_sections(text: str) -> List[str]:
    """Extract section headers from analysis text."""
    lines = text.split("\n")
    sections = []
    for line in lines:
        line = line.strip()
        if line and (line.startswith("##") or line.startswith("**") or line.endswith(":**")):
            clean = line.replace("##", "").replace("**", "").replace(":", "").strip()
            if clean and len(clean) < 100:
                sections.append(clean)
    return sections[:10]


def _extract_topics(text: str) -> List[str]:
    """Extract key topics from analysis text."""
    # Simple keyword extraction
    common_stop = {"the", "a", "is", "are", "and", "or", "in", "on", "at", "to", "from", "for", "with", "by"}
    words = text.lower().split()
    word_freq = {}
    for word in words:
        clean = word.strip(".,!?;:'\"-").lower()
        if len(clean) > 4 and clean not in common_stop:
            word_freq[clean] = word_freq.get(clean, 0) + 1
    
    topics = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [t[0] for t in topics[:15]]


def _extract_entities(text: str) -> List[str]:
    """Extract named entities from analysis text."""
    # Simple heuristic: words followed by colons or in quotes
    entities = []
    lines = text.split("\n")
    for line in lines:
        if ":" in line:
            parts = line.split(":")
            if len(parts) >= 2:
                entity = parts[0].strip()
                if 2 < len(entity) < 80 and not entity[0].islower():
                    entities.append(entity)
    return list(dict.fromkeys(entities))[:20]

