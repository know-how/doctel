import asyncio
import io
from pathlib import Path
import os
import json
import re
import logging
from collections import Counter
from typing import Any
from urllib import request as urlrequest, error as urlerror
from fastapi import UploadFile, HTTPException
from app.models import (
    DocumentMetadata,
    DocumentCreateResponse,
    DocumentAnalysisResponse,
    PromptListResponse,
    ChatRequest,
    ChatResponse,
    ProjectCreateRequest,
    ProjectSummary,
    ProjectResponse,
    ProjectListResponse,
    ProjectDocumentListResponse,
)
from app.config import settings
from app.services.history_service import append_chat_history
from app.services.summary_history_service import append_summary_history
from app.services.document_store import (
    create_document,
    document_exists,
    get_document,
    set_document_storage_path,
    get_document_storage_path,
    create_project as create_project_entry,
    list_projects as list_project_entries,
    get_project,
    get_project_by_name,
    add_document_to_project,
    list_project_documents,
)


_llama_cpp_instance = None
_chunk_cache: dict[str, dict[str, Any]] = {}
logger = logging.getLogger(__name__)


def _clean_extracted_text(text: str) -> str:
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.strip() for line in normalized.splitlines())
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if len(normalized) > settings.extract_max_chars:
        normalized = normalized[: settings.extract_max_chars].rstrip()
    return normalized


def _llm_context(text: str) -> str:
    if not text:
        return ""
    normalized = " ".join(text.split())
    if len(normalized) > settings.llm_context_chars:
        return normalized[: settings.llm_context_chars]
    return normalized


def _read_txt_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    return _clean_extracted_text(text)


def _read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise HTTPException(status_code=500, detail="PDF reader dependency missing")
    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""
    parts = []
    for page in reader.pages:
        try:
            extracted = page.extract_text() or ""
        except Exception:
            extracted = ""
        if extracted:
            parts.append(extracted)
    return _clean_extracted_text("\n".join(parts))


def _read_docx_text(path: Path) -> str:
    try:
        from docx import Document
    except ImportError:
        raise HTTPException(status_code=500, detail="DOCX reader dependency missing")
    try:
        doc = Document(str(path))
    except Exception:
        return ""
    parts = [para.text for para in doc.paragraphs if para.text]
    return _clean_extracted_text("\n".join(parts))


def _read_image_text(path: Path) -> str:
    try:
        from app.services.gemini_service import analyze_image, is_configured as gemini_configured
        if gemini_configured():
            import asyncio
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(asyncio.run, analyze_image(str(path), "Extract and transcribe all visible text from this image. Describe the image content in detail.")).result()
                return _clean_extracted_text(result)
            else:
                result = asyncio.run(analyze_image(str(path), "Extract and transcribe all visible text from this image. Describe the image content in detail."))
                return _clean_extracted_text(result)
    except Exception as e:
        logger.warning("Gemini vision analysis failed for %s: %s", path, e)
    fallback = f"[Image: {path.name}] OCR requires Gemini API key for image text extraction."
    return fallback


def _read_document_text(document_id: str) -> str:
    storage_path = get_document_storage_path(document_id)
    if not storage_path:
        return ""
    path = Path(storage_path)
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return _read_txt_text(path)
    if suffix == ".pdf":
        return _read_pdf_text(path)
    if suffix == ".docx":
        return _read_docx_text(path)
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
    if suffix in image_exts:
        return _read_image_text(path)
    return ""


def _get_or_build_chunks(document_id: str) -> list[dict[str, str]]:
    storage_path = get_document_storage_path(document_id)
    if not storage_path:
        return []
    try:
        mtime = os.path.getmtime(storage_path)
    except OSError:
        mtime = 0.0
    cached = _chunk_cache.get(document_id)
    if cached and cached.get("mtime") == mtime:
        return cached.get("chunks", [])

    text = _read_document_text(document_id)
    if not text:
        _chunk_cache[document_id] = {"mtime": mtime, "chunks": []}
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[dict[str, str]] = []
    buf: list[str] = []
    buf_len = 0
    max_chars = 1200
    overlap_paras = 1
    for para in paragraphs:
        if buf_len + len(para) + 2 > max_chars and buf:
            chunk_text = "\n\n".join(buf).strip()
            chunks.append({"chunk_id": f"chunk_{len(chunks) + 1}", "text": chunk_text})
            buf = buf[-overlap_paras:] if overlap_paras > 0 else []
            buf_len = sum(len(p) for p in buf)
        buf.append(para)
        buf_len += len(para) + 2
    if buf:
        chunks.append({"chunk_id": f"chunk_{len(chunks) + 1}", "text": "\n\n".join(buf).strip()})

    _chunk_cache[document_id] = {"mtime": mtime, "chunks": chunks}
    return chunks


def _retrieve_chunks(document_id: str, query: str, k: int = 4) -> list[dict[str, str]]:
    chunks = _get_or_build_chunks(document_id)
    if not chunks:
        return []
    query_terms = _extract_keywords(query) or [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]{4,}", query)
    ]
    query_terms = [t.lower() for t in query_terms][:8]
    if not query_terms:
        return chunks[: min(k, len(chunks))]

    scored: list[tuple[int, int, dict[str, str]]] = []
    for idx, chunk in enumerate(chunks):
        lower = chunk["text"].lower()
        score = 0
        for term in query_terms:
            if term in lower:
                score += 3
            score += lower.count(term)
        scored.append((score, -idx, chunk))
    scored.sort(reverse=True)
    selected = [item[2] for item in scored[: min(k, len(scored))] if item[0] > 0]
    return selected or chunks[: min(k, len(chunks))]


def _ollama_generate(prompt: str) -> str:
    if not settings.llm_base_url or not settings.llm_model:
        raise HTTPException(status_code=500, detail="LLM configuration missing")
    url = settings.llm_base_url.rstrip("/") + "/api/generate"
    payload = {
        "model": settings.llm_model,
        "prompt": prompt,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=settings.llm_timeout_seconds) as res:
            if res.status < 200 or res.status >= 300:
                raise HTTPException(status_code=502, detail="LLM server error")
            body = res.read()
    except urlerror.HTTPError:
        raise HTTPException(status_code=502, detail="LLM server error")
    except urlerror.URLError:
        raise HTTPException(status_code=502, detail="LLM server unreachable")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=502, detail="LLM server response invalid")
    response = payload.get("response")
    if not response:
        raise HTTPException(status_code=502, detail="LLM server response invalid")
    return str(response).strip()


def _llama_cpp_generate(prompt: str) -> str:
    global _llama_cpp_instance
    if not settings.llm_model_path:
        return ""
    if _llama_cpp_instance is None:
        try:
            from llama_cpp import Llama
        except ImportError:
            logger.warning("llama-cpp-python not installed")
            return ""
        model_path = Path(settings.llm_model_path)
        if not model_path.exists():
            logger.warning("LLM model file not found at %s", model_path)
            return ""
        _llama_cpp_instance = Llama(
            model_path=str(model_path),
            n_ctx=settings.llm_n_ctx,
            n_threads=settings.llm_n_threads,
            n_gpu_layers=settings.llm_n_gpu_layers,
        )
    result = _llama_cpp_instance(
        prompt,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
        top_p=0.9,
        stop=["</s>"],
    )
    choices = result.get("choices", [])
    if not choices:
        return ""
    text = choices[0].get("text", "")
    return str(text).strip()


async def _generate_with_llm(prompt: str) -> str:
    """Generate text using the configured provider.

    Supports: ollama, llama_cpp, gemini, deepseek, zen, huggingface.
    This is the async version — callers must ``await`` it.
    """
    if settings.llm_provider == "ollama":
        return _ollama_generate(prompt)
    if settings.llm_provider == "llama_cpp":
        return _llama_cpp_generate(prompt)
    if settings.llm_provider == "gemini":
        from app.services.gemini_service import (
            generate as gemini_generate,
        )
        try:
            result = await asyncio.wait_for(gemini_generate(prompt), timeout=120.0)
            return result or ""
        except Exception as exc:
            logger.warning("Gemini _generate_with_llm failed: %s", exc)
            return ""
    if settings.llm_provider == "deepseek":
        from app.services.deepseek_service import (
            generate as deepseek_generate,
        )
        try:
            result = await asyncio.wait_for(deepseek_generate(prompt), timeout=120.0)
            return result or ""
        except Exception as exc:
            logger.warning("DeepSeek _generate_with_llm failed: %s", exc)
            return ""
    if settings.llm_provider and settings.llm_provider.startswith("zen/"):
        from app.services.opencode_zen_service import (
            generate as zen_generate,
        )
        try:
            result = await asyncio.wait_for(
                zen_generate(prompt, model=settings.llm_provider), timeout=120.0
            )
            return result or ""
        except Exception as exc:
            logger.warning("Zen _generate_with_llm failed: %s", exc)
            return ""
    if settings.llm_provider and settings.llm_provider.startswith("huggingface/"):
        from app.services.huggingface_service import (
            generate as hf_generate,
        )
        try:
            result = await asyncio.wait_for(
                hf_generate(prompt, model=settings.llm_provider), timeout=120.0
            )
            return result or ""
        except Exception as exc:
            logger.warning("HF _generate_with_llm failed: %s", exc)
            return ""
    logger.warning("No supported llm_provider configured (current: %s)", settings.llm_provider)
    return ""


async def _maybe_generate_analysis_structured(document_id: str) -> dict[str, Any] | None:
    context = _read_document_text(document_id)
    if not context:
        return None
    prompt = (
        "You are a professional document analyst for ZETDC (Zimbabwe Electricity Transmission and Distribution Company). "
        "Return a JSON object only (no markdown, no asterisks) with keys:\n"
        "- executive_summary: string — a professional narrative summary in flowing prose (max 10 sentences). "
        "Do NOT use asterisks, bold markdown, numbered lists, or bullet points. Write as well-structured paragraphs. "
        "Begin with a clear statement of the document's purpose and scope. Organise logically: context, then findings, then implications.\n"
        "- detailed_summary: array of strings — each string must be a complete narrative sentence, not a bullet point or fragment. "
        "Present key findings as professional prose, categorised by theme.\n"
        "- sentiment: one of Positive, Neutral, Negative, Urgent\n"
        "- topics: array of short strings\n"
        "- entities: array of strings\n"
        "- key_entities: object with arrays people, dates, locations\n"
        "- action_items: array of strings — each as a complete professional sentence\n"
        "- decisions: array of strings — each as a complete professional sentence\n\n"
        "SUMMARY WRITING RULES:\n"
        "- NEVER use asterisks or markdown formatting for emphasis\n"
        "- NEVER use numbered or bulleted lists in executive_summary; write in narrative paragraphs\n"
        "- Each detailed_summary entry must be a complete, well-formed sentence\n"
        "- Maintain a formal, professional tone suitable for ZETDC leadership and staff\n"
        "- Use precise ZETDC terminology where applicable\n\n"
        "Use ONLY the document content. If something is not present, return an empty array.\n\n"
        f"Document:\n{_llm_context(context)}"
    )
    response = await _generate_with_llm(prompt)
    if not response:
        return None
    try:
        parsed = json.loads(response)
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


async def _maybe_generate_chat_answer(document_id: str, question: str) -> str:
    chunks = _retrieve_chunks(document_id, question, k=4)
    if not chunks:
        context = _read_document_text(document_id)
        if not context:
            return "No text could be extracted from this document."
        snippet = _build_source_snippet(context)
        return f"Relevant excerpt: {snippet}"
    excerpts = "\n\n".join(
        f"[{c['chunk_id']}]\n{_llm_context(c['text'])}" for c in chunks
    )
    prompt = (
        "You are DocIntel. Answer using ONLY the provided document excerpts. "
        "If the answer is not explicitly present, reply exactly: Not found in document.\n\n"
        f"Excerpts:\n{excerpts}\n\nQuestion: {question}\nAnswer:"
    )
    llm_answer = await _generate_with_llm(prompt)
    if llm_answer:
        return llm_answer
    extractive = _extractive_answer_from_chunks(question, chunks)
    if extractive != "Not found in document.":
        return extractive
    first = chunks[0].get("text") if chunks else ""
    first = _build_source_snippet(first or "")
    return f"Relevant excerpt: {first}"


def _extractive_answer_from_chunks(question: str, chunks: list[dict[str, str]]) -> str:
    question_terms = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]{4,}", question)
    ]
    if not question_terms:
        return "Not found in document."

    stop = {
        "the",
        "and",
        "for",
        "that",
        "with",
        "from",
        "this",
        "your",
        "you",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "but",
        "not",
        "all",
        "any",
        "can",
        "will",
        "shall",
        "may",
        "must",
        "about",
        "into",
        "over",
        "such",
        "more",
        "most",
        "less",
        "than",
        "then",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "how",
        "document",
        "section",
        "page",
    }
    terms = [t for t in question_terms if t not in stop][:10]
    if not terms:
        return "Not found in document."

    candidates: list[tuple[int, str]] = []
    for chunk in chunks:
        text = chunk.get("text") or ""
        if not text:
            continue
        sentences = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
        for sent in sentences:
            s = sent.strip()
            if not s:
                continue
            lower = s.lower()
            score = 0
            for term in terms:
                if term in lower:
                    score += 2 + lower.count(term)
            if score > 0:
                candidates.append((score, s))

    if not candidates:
        return "Not found in document."

    candidates.sort(key=lambda x: x[0], reverse=True)
    picked: list[str] = []
    for _, s in candidates:
        if s in picked:
            continue
        picked.append(s)
        if len(picked) >= 3:
            break
    return " ".join(picked) if picked else "Not found in document."


def _build_source_snippet(context: str) -> str:
    snippet = context.strip().replace("\n", " ")
    if len(snippet) > 200:
        snippet = snippet[:200] + "..."
    return snippet or "No local text extracted."


def _extract_keywords(text: str) -> list[str]:
    words = []
    stopwords = {
        "the",
        "and",
        "for",
        "that",
        "with",
        "from",
        "this",
        "your",
        "you",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "but",
        "not",
        "all",
        "any",
        "can",
        "will",
        "shall",
        "may",
        "must",
        "about",
        "into",
        "over",
        "such",
        "more",
        "most",
        "less",
        "than",
        "then",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "how",
        "document",
        "policy",
        "section",
        "page",
    }
    for raw in text.split():
        token = "".join(ch for ch in raw if ch.isalnum()).lower()
        if len(token) < 4 or token in stopwords:
            continue
        words.append(token)
    counts = Counter(words)
    return [word for word, _ in counts.most_common(5)]


def _extract_entities(text: str) -> list[str]:
    if not text:
        return []
    matches = re.findall(
        r"\b[A-Z][A-Za-z0-9&\-]{2,}(?:\s+[A-Z][A-Za-z0-9&\-]{2,})*\b",
        text,
    )
    unique: list[str] = []
    for item in matches:
        if item not in unique:
            unique.append(item)
        if len(unique) >= 6:
            break
    return unique


def _extract_dates(text: str) -> list[str]:
    if not text:
        return []
    matches = re.findall(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}|\d{4})\b",
        text,
        flags=re.IGNORECASE,
    )
    unique: list[str] = []
    for m in matches:
        val = str(m).strip()
        if not val:
            continue
        if val not in unique:
            unique.append(val)
        if len(unique) >= 6:
            break
    return unique


def _extract_locations(text: str) -> list[str]:
    if not text:
        return []
    candidates: list[str] = []
    for m in re.findall(r"\b(?:in|at)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\b", text):
        candidates.append(m.strip())
    allowlist = [
        "Zimbabwe",
        "Harare",
        "Bulawayo",
        "Mutare",
        "Gweru",
        "Masvingo",
    ]
    for name in allowlist:
        if name in text:
            candidates.append(name)
    unique: list[str] = []
    for item in candidates:
        if item not in unique:
            unique.append(item)
        if len(unique) >= 6:
            break
    return unique


def _extract_action_items(text: str) -> list[str]:
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    keywords = ("must", "shall", "required", "requirement", "ensure", "should", "deadline", "action")
    items: list[str] = []
    for sent in sentences:
        s = sent.strip()
        if not s:
            continue
        lower = s.lower()
        if any(k in lower for k in keywords):
            items.append(s)
        if len(items) >= 8:
            break
    return items


def _extract_decisions(text: str) -> list[str]:
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    keywords = ("approved", "decided", "decision", "resolved", "agreed", "authorized")
    items: list[str] = []
    for sent in sentences:
        s = sent.strip()
        if not s:
            continue
        lower = s.lower()
        if any(k in lower for k in keywords):
            items.append(s)
        if len(items) >= 6:
            break
    return items


def _infer_sentiment(text: str) -> str:
    lower = (text or "").lower()
    if any(k in lower for k in ("urgent", "immediately", "asap", "critical", "high priority")):
        return "Urgent"
    if any(k in lower for k in ("risk", "issue", "failure", "noncompliance", "breach")):
        return "Negative"
    if any(k in lower for k in ("success", "improved", "benefit", "achieved", "positive")):
        return "Positive"
    return "Neutral"


def _extract_topics(text: str) -> list[str]:
    keywords = _extract_keywords(text)
    return [kw.capitalize() for kw in keywords]


def _extract_headings(text: str) -> list[str]:
    if not text:
        return []
    headings: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if len(line) < 6 or len(line) > 90:
            continue
        if re.match(r"^\d+(\.\d+)*\s+\S+", line):
            headings.append(line)
            continue
        if line.isupper() and any(ch.isalpha() for ch in line):
            headings.append(line.title())
            continue
        if line.endswith(":") and len(line.split()) <= 10:
            headings.append(line.rstrip(":"))
    unique: list[str] = []
    for h in headings:
        if h not in unique:
            unique.append(h)
        if len(unique) >= 6:
            break
    return unique


def _maybe_generate_prompts(document_id: str) -> list[str]:
    context = _read_document_text(document_id)
    if context:
        prompt = (
            "Generate 3-5 concise suggested questions for a user to ask about the "
            "document. Output each question on its own line with no numbering.\n\n"
            f"Document:\n{_llm_context(context)}"
        )
        response = _generate_with_llm(prompt)
        if response:
            lines = []
            for raw in response.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if line[0] in "-*":
                    line = line[1:].strip()
                if line and line[0].isdigit() and "." in line:
                    line = line.split(".", 1)[1].strip()
                if line:
                    lines.append(line)
            lines = [line for line in lines if line.endswith("?")]
            if len(lines) >= 3:
                return lines[:5]
        headings = _extract_headings(context)
        keywords = _extract_keywords(context)
        prompts: list[str] = []
        for heading in headings[:2]:
            prompts.append(f"Summarize the {heading} section.")
            prompts.append(f"List any requirements in the {heading} section.")
        for keyword in keywords:
            prompts.append(f"What does the document say about {keyword}?")
        prompts.extend(
            [
                "Extract all action items from this document.",
                "Extract any decisions or approvals mentioned.",
                "What risks or constraints are mentioned?",
            ]
        )
        unique: list[str] = []
        for item in prompts:
            if item not in unique:
                unique.append(item)
        return unique[:5]
    return [
        "Summarize the key requirements in this document.",
        "List the stakeholders and their roles.",
        "What are the main risks mentioned?",
    ]


async def upload_document(
    file: UploadFile,
    project_id: str | None = None,
    project_name: str | None = None,
    document_type: str | None = None,
    document_date: str | None = None,
) -> DocumentCreateResponse:
    allowed_content_types = (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
        "image/gif",
        "image/bmp",
        "audio/wav",
        "audio/mpeg",
        "audio/mp4",
        "audio/ogg",
        "audio/webm",
        "audio/flac",
        "audio/x-m4a",
        "video/mp4",
        "video/avi",
        "video/quicktime",
        "video/x-msvideo",
    )
    if file.content_type not in allowed_content_types:
        ext = Path(file.filename or "file").suffix.lower() if file.filename else ""
        allowed_exts = {
            ".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
            ".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac", ".aac",
            ".mp4", ".avi", ".mov", ".mkv",
        }
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type or ext}. Allowed: PDF, DOCX, TXT, images, audio, video")

    resolved_project_id = project_id
    resolved_project_name = project_name

    if resolved_project_id:
        project = get_project(resolved_project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        resolved_project_name = project["name"]
    elif resolved_project_name:
        existing_project_id = get_project_by_name(resolved_project_name)
        if existing_project_id:
            resolved_project_id = existing_project_id
        else:
            resolved_project_id = create_project_entry(resolved_project_name)

    metadata = DocumentMetadata(
        project_id=resolved_project_id,
        project_name=resolved_project_name,
        document_type=document_type,
        document_date=document_date,
    )
    filename = file.filename or "document"
    document_id = create_document(
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        metadata=metadata.model_dump(),
    )
    if resolved_project_id:
        add_document_to_project(document_id, resolved_project_id)
    safe_name = Path(filename).name
    storage_dir = Path(__file__).resolve().parent.parent / "data" / "documents"
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{document_id}_{safe_name}"
    content = await file.read()
    storage_path.write_bytes(content)
    set_document_storage_path(document_id, str(storage_path))

    return DocumentCreateResponse(
        id=document_id,
        filename=filename,
        status="PROCESSING",
        metadata=metadata,
    )


async def get_document_file(document_id: str) -> tuple[str, str, str]:
    entry = get_document(document_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Document not found")
    storage_path = entry.get("storage_path") or get_document_storage_path(document_id)
    if not storage_path:
        raise HTTPException(status_code=404, detail="Document file not found")
    path = Path(str(storage_path))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document file not found")
    media_type = str(entry.get("content_type") or "application/octet-stream")
    filename = str(entry.get("filename") or path.name)
    return str(path), media_type, filename


async def create_project(request: ProjectCreateRequest) -> ProjectResponse:
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")
    existing_project_id = get_project_by_name(request.name)
    project_id = existing_project_id or create_project_entry(request.name)
    project = get_project(project_id)
    return ProjectResponse(
        id=project_id,
        name=project["name"],
        document_ids=list(project.get("document_ids", [])),
    )


async def get_projects() -> ProjectListResponse:
    projects = [
        ProjectSummary(
            id=project_id,
            name=project["name"],
            document_count=len(project.get("document_ids", [])),
        )
        for project_id, project in list_project_entries().items()
    ]
    return ProjectListResponse(projects=projects)


async def get_project_documents(project_id: str) -> ProjectDocumentListResponse:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectDocumentListResponse(
        project_id=project_id,
        document_ids=list_project_documents(project_id),
    )


async def get_project_detail(project_id: str) -> ProjectResponse:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        id=project_id,
        name=project["name"],
        document_ids=list_project_documents(project_id),
    )


async def get_project_analysis(
    project_id: str,
    ec_number: str | None = None,
) -> DocumentAnalysisResponse:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    document_ids = list_project_documents(project_id)
    analysis = DocumentAnalysisResponse(
        id=f"project_{project_id}",
        executive_summary=(
            f"Project {project['name']} includes {len(document_ids)} documents."
        ),
        detailed_summary=[
            f"Document {doc_id} included in project scope." for doc_id in document_ids
        ]
        or ["No documents in this project yet."],
        entities=[project["name"]],
        topics=["Project analysis", "Document grouping"],
        sentiment="Neutral",
        status="READY",
    )

    if ec_number:
        append_summary_history(ec_number, analysis)

    return analysis


async def get_document_analysis(
    document_id: str,
    ec_number: str | None = None,
) -> DocumentAnalysisResponse:
    if not document_exists(document_id):
        raise HTTPException(status_code=404, detail="Document not found")

    context = _read_document_text(document_id)
    entities = _extract_entities(context)
    topics = _extract_topics(context)
    key_entities = {
        "people": entities[:6],
        "dates": _extract_dates(context),
        "locations": _extract_locations(context),
    }
    sentiment = _infer_sentiment(context)
    action_items = _extract_action_items(context)
    decisions = _extract_decisions(context)

    structured = await _maybe_generate_analysis_structured(document_id)
    if structured:
        executive_summary = str(structured.get("executive_summary") or "").strip()
        detailed_summary = structured.get("detailed_summary") or []
        if not isinstance(detailed_summary, list):
            detailed_summary = []
        detailed_summary = [str(x).strip() for x in detailed_summary if str(x).strip()]
        parsed_topics = structured.get("topics") or []
        if isinstance(parsed_topics, list):
            topics = [str(x).strip() for x in parsed_topics if str(x).strip()] or topics
        parsed_entities = structured.get("entities") or []
        if isinstance(parsed_entities, list):
            entities = [str(x).strip() for x in parsed_entities if str(x).strip()] or entities
        parsed_key_entities = structured.get("key_entities") or {}
        if isinstance(parsed_key_entities, dict):
            key_entities = {
                "people": [str(x).strip() for x in (parsed_key_entities.get("people") or []) if str(x).strip()],
                "dates": [str(x).strip() for x in (parsed_key_entities.get("dates") or []) if str(x).strip()],
                "locations": [str(x).strip() for x in (parsed_key_entities.get("locations") or []) if str(x).strip()],
            }
        parsed_sentiment = str(structured.get("sentiment") or "").strip().title()
        if parsed_sentiment in {"Positive", "Neutral", "Negative", "Urgent"}:
            sentiment = parsed_sentiment
        parsed_action_items = structured.get("action_items") or []
        if isinstance(parsed_action_items, list):
            action_items = [str(x).strip() for x in parsed_action_items if str(x).strip()] or action_items
        parsed_decisions = structured.get("decisions") or []
        if isinstance(parsed_decisions, list):
            decisions = [str(x).strip() for x in parsed_decisions if str(x).strip()] or decisions
    else:
        sentences = re.split(r"(?<=[.!?])\s+", context.replace("\n", " ").strip())
        executive_summary = " ".join([s for s in sentences if s][:10]).strip()
        if not executive_summary:
            executive_summary = _build_source_snippet(context) if context else ""
        detailed_summary = []
        if action_items:
            detailed_summary.extend(action_items[:5])
        if not detailed_summary:
            for sent in sentences[:8]:
                s = sent.strip()
                if s and s not in detailed_summary:
                    detailed_summary.append(s)
                if len(detailed_summary) >= 5:
                    break
        if not detailed_summary and executive_summary:
            detailed_summary = [executive_summary]

    if not context:
        executive_summary = "No content available yet."
        detailed_summary = ["Upload a document to generate a detailed summary."]
        entities = entities or ["DocIntel System"]
        topics = topics or ["Document analysis"]
        sentiment = "Neutral"

    analysis = DocumentAnalysisResponse(
        id=document_id,
        executive_summary=executive_summary,
        detailed_summary=detailed_summary,
        entities=entities,
        key_entities=key_entities,
        topics=topics,
        sentiment=sentiment,
        action_items=action_items[:10],
        decisions=decisions[:10],
        status="READY",
    )

    if ec_number:
        append_summary_history(ec_number, analysis)

    return analysis


async def get_document_prompts(document_id: str) -> PromptListResponse:
    if not document_exists(document_id):
        raise HTTPException(status_code=404, detail="Document not found")

    prompts = _maybe_generate_prompts(document_id)

    return PromptListResponse(
        document_id=document_id,
        prompts=prompts,
    )


async def chat_with_document(
    document_id: str,
    request: ChatRequest,
) -> ChatResponse:
    if not document_exists(document_id):
        raise HTTPException(status_code=404, detail="Document not found")

    answer = await _maybe_generate_chat_answer(document_id, request.question)
    chunks = _retrieve_chunks(document_id, request.question, k=4)
    if not answer:
        if chunks:
            answer = "Not found in document."
        else:
            answer = "Not found in document."

    response = ChatResponse(
        document_id=document_id,
        question=request.question,
        answer=answer,
        sources=[
            {
                "chunk_id": c["chunk_id"],
                "snippet": _build_source_snippet(c["text"]),
            }
            for c in chunks
        ],
    )

    if request.ec_number:
        append_chat_history(
            ec_number=request.ec_number,
            document_id=document_id,
            question=request.question,
            answer=answer,
        )

    return response
