import logging
import os
import json
from typing import Optional, Dict, Any, List, AsyncGenerator
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

DEEPSEEK_MODEL_ID = "deepseek-api"

_DEFAULT_MODEL = "deepseek-v4-flash-free"
_DEFAULT_BASE_URL = "https://opencode.ai/zen/v1"
_TIMEOUT = 120.0

_client: Optional[AsyncOpenAI] = None


def _normalize_base_url(url: str) -> str:
    url = url.rstrip("/")
    suffix = "/chat/completions"
    if url.endswith(suffix):
        url = url[: -len(suffix)]
    return url


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = _api_key()
        base_url = _base_url()
        _client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=_TIMEOUT)
    return _client


def get_display_name() -> str:
    model = _model_name()
    model_lower = model.lower()

    display_map = {
        "deepseek-v4-pro": "DeepSeek V4 Pro (API)",
        "deepseek-chat": "DeepSeek Chat (API)",
        "deepseek-coder": "DeepSeek Coder (API)",
        "deepseek-reasoner": "DeepSeek Reasoner (API)",
    }

    if model_lower in display_map:
        return display_map[model_lower]

    for key, display in display_map.items():
        if key in model_lower:
            return display

    return f"DeepSeek {model.replace('deepseek-', '').replace('_', ' ').title()} (API)"


def _settings() -> "Settings":
    from app.config import settings
    return settings


def _api_key() -> str:
    """Get API key from env, then file settings (DB override supported via settings proxy)."""
    val = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if val:
        return val
    return _settings().deepseek_api_key


def _model_name() -> str:
    """Get model name from env, then file settings, then hardcoded default."""
    val = os.getenv("DEEPSEEK_MODEL", "").strip()
    if val:
        return val
    return _settings().deepseek_model or _DEFAULT_MODEL


def _base_url() -> str:
    """Get base URL from env, then file settings, then hardcoded default."""
    val = os.getenv("DEEPSEEK_BASE_URL", "").strip()
    if val:
        return _normalize_base_url(val)
    return _normalize_base_url(_settings().deepseek_base_url or _DEFAULT_BASE_URL)


# ═══════════════════════════════════════════════════════════════════════════════
#  DB-AWARE ASYNC VERSIONS (for use with database-backed configuration)
# ═══════════════════════════════════════════════════════════════════════════════

async def get_api_key_db(db: "AsyncSession") -> str:
    """Get API key with DB override support. Priority: env > DB > file > empty."""
    val = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if val:
        return val
    
    from app.services import app_config_service as app_cfg
    db_val = await app_cfg.get_setting_str(db, "api.deepseek_api_key", "")
    if db_val:
        return db_val
    
    return _settings().deepseek_api_key


async def get_model_name_db(db: "AsyncSession") -> str:
    """Get model name with DB override support. Priority: env > DB > file > default."""
    val = os.getenv("DEEPSEEK_MODEL", "").strip()
    if val:
        return val
    
    from app.services import app_config_service as app_cfg
    db_val = await app_cfg.get_setting_str(db, "api.deepseek_model", "")
    if db_val:
        return db_val
    
    return _settings().deepseek_model or _DEFAULT_MODEL


async def get_base_url_db(db: "AsyncSession") -> str:
    """Get base URL with DB override support. Priority: env > DB > file > default."""
    val = os.getenv("DEEPSEEK_BASE_URL", "").strip()
    if val:
        return _normalize_base_url(val)
    
    from app.services import app_config_service as app_cfg
    db_val = await app_cfg.get_setting_str(db, "api.deepseek_base_url", "")
    if db_val:
        return _normalize_base_url(db_val)
    
    return _normalize_base_url(_settings().deepseek_base_url or _DEFAULT_BASE_URL)


def is_configured() -> bool:
    return bool(_api_key())


async def generate(prompt: str, system: Optional[str] = None) -> str:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not configured. "
            "Add DEEPSEEK_API_KEY=<your_key> to your .env file and restart the server."
        )

    client = _get_client()
    model = _model_name()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        status = getattr(exc, "status_code", 0)
        msg = str(exc)
        if status == 400:
            raise RuntimeError(f"DeepSeek API bad request: {msg}")
        if status == 401:
            raise RuntimeError("DeepSeek API key is invalid. Check your key at https://platform.deepseek.com")
        if status == 402:
            raise RuntimeError("DeepSeek API quota exceeded. Please top up your account at https://platform.deepseek.com")
        if status == 422:
            raise RuntimeError(f"DeepSeek API rejected the request (422). This usually means the model name is wrong or the request format is unsupported. Detail: {msg}. Model: {model}")
        if status == 429:
            raise RuntimeError("DeepSeek API rate limit exceeded. Wait a moment and try again.")
        if status == 404:
            raise RuntimeError(f"DeepSeek model '{model}' is not available. Try a supported model such as '{_DEFAULT_MODEL}'.")
        raise RuntimeError(f"DeepSeek API error {status}: {msg}")


async def generate_stream(prompt: str, system: Optional[str] = None) -> AsyncGenerator[str, None]:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")

    client = _get_client()
    model = _model_name()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
    except Exception as exc:
        status = getattr(exc, "status_code", 0)
        if status == 401:
            raise RuntimeError("DeepSeek API key is invalid.")
        if status == 429:
            raise RuntimeError("DeepSeek API rate limit exceeded.")
        if status == 422:
            raise RuntimeError(f"DeepSeek streaming rejected (422). Model '{model}' may be wrong or request format unsupported.")
        raise RuntimeError(f"DeepSeek streaming error: {exc}")


async def analyze_document(
    file_path: str,
    prompt: str = "Summarize this document. Extract: title, key sections, main topics, entities.",
) -> Dict[str, Any]:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")

    from pathlib import Path
    file_path = Path(file_path)
    if not file_path.exists():
        raise RuntimeError(f"Document file not found: {file_path}")

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

    if not text_content.strip():
        raise RuntimeError(f"No readable content in {file_path}")

    text_content = text_content[:10000]
    analysis_prompt = f"{prompt}\n\nDocument content:\n{text_content}"

    try:
        raw_response = await generate(analysis_prompt, system="You are a document analyst.")
    except RuntimeError as e:
        raise RuntimeError(f"Document analysis failed: {e}")

    return {"summary": raw_response, "raw_response": raw_response}


async def generate_synthetic_training_data(
    topic: str,
    num_examples: int = 10,
    instruction_style: str = "question_answer",
) -> List[Dict[str, str]]:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")

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

    try:
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
