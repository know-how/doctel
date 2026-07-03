import re
import os
import hashlib
import json
import logging
import asyncio
import time
import shutil
from typing import List, Optional
from pathlib import Path
from PIL import Image
import pytesseract
from PyPDF2 import PdfReader
import docx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_tesseract_checked = False
_tesseract_available = False

def _check_tesseract() -> bool:
    global _tesseract_checked, _tesseract_available
    if not _tesseract_checked:
        _tesseract_checked = True
        _tesseract_available = shutil.which("tesseract") is not None
        if not _tesseract_available:
            logger = logging.getLogger(__name__)
            logger.warning("tesseract not found in PATH – OCR will be skipped")
    return _tesseract_available

from app.config import settings
import asyncio

# Track auto-training cooldown (only trigger once per batch)
_last_auto_train = 0
AUTO_TRAIN_COOLDOWN_SEC = 300

def _schedule_auto_training(db, doc):
    """Schedule automatic model training after document ingestion."""
    global _last_auto_train
    import time
    now = time.time()
    if now - _last_auto_train < AUTO_TRAIN_COOLDOWN_SEC:
        return  # Cooldown - don't trigger too often
    _last_auto_train = now

    async def _do_train():
        try:
            from app.services.multi_model_trainer import train_models_from_project
            project_id = int(doc.project_id)
            result = await train_models_from_project(
                project_ids=[project_id],
                db=db,
            )
            import logging
            logging.getLogger().info(f"Auto-training complete for project {project_id}: {result}")
        except Exception as e:
            import logging
            logging.getLogger().warning(f"Auto-training skipped: {e}")

    asyncio.ensure_future(_do_train())
from app.db.models import Document, DocAnalysis, SuggestedPrompt, Chunk, Embedding
from app.utils.ollama_client import ollama
from app.services.model_router import select_text_model
from app.utils.chroma_client import chroma

logger = logging.getLogger(__name__)

# Cache for pre-chunked audio/video segments from process_audio_for_rag().
# Keyed by file path → {"chunks": list[dict], "source_type": str}
# Set by extract_text(), consumed by run_embedding_pipeline().
_audio_chunks_cache: dict[str, dict] = {}

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

async def _set_doc_state(
    db: AsyncSession,
    doc: Document,
    *,
    status: str,
    step: str,
    percent: int,
    message: str = "",
    error_message: str = "",
) -> None:
    doc.status = status
    doc.ingest_step = step
    doc.ingest_percent = percent
    doc.ingest_message = message
    doc.error_message = error_message
    doc.updated_at = _now_iso()
    if status == "uploaded":
        doc.ingestion_started = False
        doc.ingestion_completed = False
        doc.ingestion_failed = False
        doc.analysis_ready = False
    elif status in ("ingesting", "embedded", "summarized"):
        doc.ingestion_started = True
        doc.ingestion_failed = False
    elif status == "completed":
        doc.ingestion_started = True
        doc.ingestion_completed = True
        doc.ingestion_failed = False
        doc.analysis_ready = True
    elif status == "failed":
        doc.ingestion_started = True
        doc.ingestion_failed = True
    db.add(doc)
    try:
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass
        raise

async def get_file_hash(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

async def extract_text(file_path: str, mime_type: str) -> str:
    text = ""
    file_ext = Path(file_path).suffix.lower()
    
    if file_ext == ".pdf":
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() or ""
            
            # Fallback to OCR if text is poor/empty
            if len(text.strip()) < 50 and _check_tesseract():
                logger.info(f"PDF text extraction poor for {file_path}, falling back to OCR")
                try:
                    import pypdfium2 as pdfium
                except Exception as e:
                    raise RuntimeError("PDF OCR requires pypdfium2") from e
                pdf = pdfium.PdfDocument(file_path)
                ocr_parts: list[str] = []
                for i in range(len(pdf)):
                    page = pdf.get_page(i)
                    pil_image = page.render(scale=2).to_pil()
                    try:
                        ocr_parts.append(pytesseract.image_to_string(pil_image))
                    except Exception:
                        pass
                    page.close()
                pdf.close()
                text = "\n".join(ocr_parts)
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {e}")
            
    elif file_ext == ".docx":
        try:
            doc = docx.Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            logger.error(f"Error extracting text from DOCX {file_path}: {e}")
            raise
            
    elif file_ext in [".txt", ".md"]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            logger.error(f"Error reading TXT {file_path}: {e}")
            
    elif file_ext in [".png", ".jpg", ".jpeg"]:
        if _check_tesseract():
            try:
                text = pytesseract.image_to_string(Image.open(file_path))
            except Exception as e:
                logger.error(f"Error performing OCR on image {file_path}: {e}")
        else:
            logger.info(f"Skipping OCR for {file_path} – tesseract not available")

    elif file_ext in {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".wma"}:
        try:
            from app.services.transcription_service import process_audio_for_rag
            result = await process_audio_for_rag(file_path, mime_type=mime_type)
            rag_chunks: list[dict] = result.get("rag_chunks", [])
            full_text: str = result.get("full_text", "")
            stype: str = result.get("source_type", "audio")
            if rag_chunks:
                _audio_chunks_cache[file_path] = {"chunks": rag_chunks, "source_type": stype}
                text = " ".join(c["text"] for c in rag_chunks)
                logger.info(f"Audio pipeline: {len(rag_chunks)} natural chunks, source_type={stype}, {len(text)} chars from {file_path}")
            elif full_text:
                text = full_text
                logger.info(f"Audio transcription extracted {len(text)} chars from {file_path} (no chunks)")
            else:
                logger.warning(f"Audio transcription returned no content for {file_path}")
        except Exception as e:
            logger.error(f"Error transcribing audio {file_path}: {e}")

    elif file_ext in {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"}:
        try:
            from app.services.transcription_service import process_audio_for_rag
            result = await process_audio_for_rag(file_path, mime_type=mime_type)
            rag_chunks: list[dict] = result.get("rag_chunks", [])
            full_text: str = result.get("full_text", "")
            stype: str = result.get("source_type", "video")
            if rag_chunks:
                _audio_chunks_cache[file_path] = {"chunks": rag_chunks, "source_type": stype}
                text = " ".join(c["text"] for c in rag_chunks)
                logger.info(f"Video pipeline: {len(rag_chunks)} natural chunks, source_type={stype}, {len(text)} chars from {file_path}")
            elif full_text:
                text = full_text
                logger.info(f"Video transcription extracted {len(text)} chars from {file_path} (no chunks)")
            else:
                logger.warning(f"Video transcription returned no content for {file_path}")
        except Exception as e:
            logger.error(f"Error transcribing video {file_path}: {e}")

    return text

def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    chunks = []
    # Safeguard against infinite loops and bad configs
    if chunk_size <= 0:
        chunk_size = 1000
    if chunk_overlap >= chunk_size:
        chunk_overlap = chunk_size // 10

    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += (chunk_size - chunk_overlap)
    return chunks

async def analyze_document(text: str, doc_id: int, db: AsyncSession):
    # Cap context so even small models don't OOM. 6 000 chars ≈ 1 500 tokens.
    analysis_text = text[:6000].strip()

    model_name = select_text_model("summary_long")

    # ── Single combined prompt ──────────────────────────────────────────────
    # One round-trip to Ollama or Gemini produces everything we need.
    combined_prompt = (
        "You are a professional document analyst for ZETDC (Zimbabwe Electricity Transmission and Distribution Company). "
        "Analyze the document excerpt below and return ONLY a valid JSON object "
        "(no markdown, no commentary, no asterisks) with exactly these keys:\n"
        "  executive_summary  – string: a professional narrative summary in flowing prose (max 10 sentences). "
        "Do NOT use asterisks, bold markdown, numbered lists, or bullet points. Write as well-structured paragraphs.\n"
        "  detailed_summary   – array of strings: each string must be a complete narrative sentence (not a bullet point). "
        "Present key findings as professional prose, not as a list of fragments.\n"
        "  sentiment          – one of: Positive, Neutral, Negative, Urgent\n"
        "  topics             – array of short strings (max 8)\n"
        "  entities           – array of strings (people, orgs, systems)\n"
        "  action_items       – array of strings: each as a complete professional sentence\n"
        "  decisions          – array of strings: each as a complete professional sentence\n"
        "  prompts            – array of 5 specific, actionable questions a user could ask "
        "about this document (include one Mermaid diagram prompt and one action-items prompt)\n\n"
        "SUMMARY WRITING RULES:\n"
        "- NEVER use asterisks (**bold**) or markdown formatting for emphasis\n"
        "- NEVER use numbered or bulleted lists in executive_summary; write in narrative paragraphs\n"
        "- Each detailed_summary entry must be a complete, well-formed sentence — not a fragment or bullet point\n"
        "- Maintain a formal, professional tone suitable for ZETDC leadership and staff\n"
        "- Begin executive_summary with a clear statement of the document's purpose and scope\n"
        "- Organise content logically: context first, then key findings, then implications\n"
        "- Use precise ZETDC terminology (transmission, distribution, substations, feeders, SCADA, HSE, ZERA compliance)\n\n"
        "Document excerpt:\n" + analysis_text
    )

    structured: dict = {}
    
    # ── Try Gemini API first (superior analysis quality) ───────────────────
    if settings.gemini_api_key:
        try:
            from app.services.gemini_service import generate as gemini_generate
            logger.info(f"Analyzing document {doc_id} with Gemini API")
            raw = await gemini_generate(
                combined_prompt,
                system="You are a precise document analyst. Output only valid JSON."
            )
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                structured = json.loads(raw[json_start:json_end])
                logger.info(f"Document {doc_id}: Gemini analysis successful")
        except Exception as e:
            logger.warning(f"Gemini analysis failed for doc {doc_id} ({e}); trying DeepSeek API")
    
    # ── Try DeepSeek API if Gemini failed ──────────────────────────────────
    if not structured and settings.deepseek_api_key:
        try:
            from app.services.deepseek_service import generate as deepseek_generate
            logger.info(f"Analyzing document {doc_id} with DeepSeek API")
            raw = await deepseek_generate(
                combined_prompt,
                system="You are a precise document analyst. Output only valid JSON."
            )
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                structured = json.loads(raw[json_start:json_end])
                logger.info(f"Document {doc_id}: DeepSeek analysis successful")
        except Exception as e:
            logger.warning(f"DeepSeek analysis failed for doc {doc_id} ({e}); falling back to Ollama")
    
    # ── Fallback to Ollama local model ──────────────────────────────────────
    if not structured:
        try:
            logger.info(f"Analyzing document {doc_id} with Ollama model: {model_name}")
            raw = await ollama.generate(
                model_name,
                combined_prompt,
                system="You are a precise document analyst. Output only valid JSON.",
                options={"num_ctx": 4096, "temperature": 0},
            )
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                structured = json.loads(raw[json_start:json_end])
                logger.info(f"Document {doc_id}: Ollama analysis successful")
        except Exception as e:
            logger.warning(f"Ollama analysis failed for doc {doc_id} ({e}); using extractive fallback")

    # ── Extractive fallback ─────────────────────────────────────────────────
    def _extract_sentences(t: str, n: int) -> list[str]:
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", t.replace("\n", " ")) if s.strip()]
        return sents[:n]

    def _extract_entities_simple(t: str) -> list[str]:
        words = re.findall(r"\b[A-Z][a-zA-Z]{2,}(?:\s[A-Z][a-zA-Z]{2,})*\b", t)
        seen: dict[str, int] = {}
        for w in words:
            seen[w] = seen.get(w, 0) + 1
        return [w for w, _ in sorted(seen.items(), key=lambda x: -x[1])][:10]

    def _infer_sentiment_simple(t: str) -> str:
        tl = t.lower()
        if any(w in tl for w in ("urgent", "critical", "immediate", "emergency", "risk", "fail")):
            return "Urgent"
        if any(w in tl for w in ("success", "achiev", "complet", "positive", "benefit", "improve")):
            return "Positive"
        if any(w in tl for w in ("problem", "issue", "error", "negativ", "concern", "loss")):
            return "Negative"
        return "Neutral"

    default_prompts = [
        "Summarize this document in 10 bullets.",
        "List all action items and decisions mentioned in this document.",
        "Generate a Mermaid process flow diagram from the key steps in this document.",
        "Extract all key entities: people, departments, locations, systems, and dates.",
        "What are the key risks, mitigations, and compliance implications?",
    ]

    exec_summary = str(structured.get("executive_summary") or "").strip()
    if not exec_summary:
        sentences = _extract_sentences(analysis_text, 10)
        exec_summary = " ".join(sentences) if sentences else "No content available."

    def _ensure_list(val, default: list) -> list:
        if isinstance(val, list) and val:
            return [str(x).strip() for x in val if str(x).strip()]
        return default

    detailed_summary = _ensure_list(structured.get("detailed_summary"), _extract_sentences(analysis_text, 5))
    entities = _ensure_list(structured.get("entities"), _extract_entities_simple(analysis_text))
    topics = _ensure_list(structured.get("topics"), [])
    action_items = _ensure_list(structured.get("action_items"), [])
    decisions = _ensure_list(structured.get("decisions"), [])
    suggested_prompts = _ensure_list(structured.get("prompts"), default_prompts)
    if len(suggested_prompts) < 3:
        suggested_prompts = (suggested_prompts + default_prompts)[:5]

    sentiment = str(structured.get("sentiment") or "").strip().title()
    if sentiment not in {"Positive", "Neutral", "Negative", "Urgent"}:
        sentiment = _infer_sentiment_simple(analysis_text)

    # ── Persist to DB ───────────────────────────────────────────────────────
    analysis = DocAnalysis(
        document_id=doc_id,
        executive_summary=exec_summary,
        detailed_summary="\n".join(detailed_summary),
        sentiment=sentiment,
        entities_json=json.dumps(entities),
        topics_json=json.dumps(topics),
        action_items_json=json.dumps(action_items),
        decisions_json=json.dumps(decisions),
    )
    db.add(analysis)

    for p_text in suggested_prompts[:5]:
        db.add(SuggestedPrompt(document_id=doc_id, prompt_text=p_text))

    await db.commit()

async def ingest_document(doc_id: int, db: AsyncSession):
    # Get document details
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        return

    try:
        await _set_doc_state(db, doc, status="ingesting", step="extract", percent=0, message="Extracting text")
        text = await extract_text(doc.path, doc.mime_type)
        if not text or len(text.strip()) < 10:
            await _set_doc_state(
                db,
                doc,
                status="failed",
                step="extract",
                percent=0,
                message="No extractable text",
                error_message="No text could be extracted from the document",
            )
            return

        await _set_doc_state(db, doc, status="ingesting", step="chunk", percent=20, message="Chunking text")

        # Initial chunking (e.g., ~1000 chars = ~250 tokens)
        init_chunk_size = settings.chunk_size
        init_overlap = settings.chunk_overlap
        
        async def run_embedding_pipeline(c_size: int, c_overlap: int) -> tuple[list[str], list[list[float]], list[str], list[dict]]:
            # Check for pre-chunked audio/video segments from extract_text()
            cached = _audio_chunks_cache.pop(doc.path, None)
            pre_chunked = cached["chunks"] if cached else None
            pre_source_type = cached["source_type"] if cached else None
            if pre_chunked:
                chunks = [c["text"] for c in pre_chunked]
                chunks = [c.strip() for c in chunks if c.strip()]
                if not chunks:
                    raise ValueError("Audio chunks produced no text segments")
                logger.info(f"Using {len(chunks)} pre-chunked audio/video segments for {doc.filename}")
            else:
                chunks = chunk_text(text, c_size, c_overlap)
                chunks = [c.strip() for c in (chunks or []) if isinstance(c, str) and c.strip()]
                if not chunks:
                    raise ValueError("Chunking produced no chunks")

            sem = asyncio.Semaphore(2)
            async def embed_one(i: int, chunk_text_content: str):
                async with sem:
                    try:
                        vec = await ollama.embed(settings.embed_model, chunk_text_content)
                        return i, vec
                    except Exception as e:
                        logger.error(f"Embedding failed at chunk {i}: {e}")
                        raise

            results = await asyncio.gather(*(embed_one(i, c) for i, c in enumerate(chunks)))
            results.sort(key=lambda x: x[0])
            
            emb_out, metadatas, ids, docs = [], [], [], []
            for i, vec in results:
                if i < 0 or i >= len(chunks):
                    continue
                content = chunks[i].strip()
                if not content:
                    continue
                chroma_id = f"chroma_{doc_id}_{i}_{c_size}"
                ids.append(chroma_id)
                emb_out.append(vec)
                docs.append(content)
                # Determine source_type from file extension
                # For pre-chunked audio/video, use the source_type from the pipeline
                f_ext = Path(doc.filename).suffix.lower() if doc.filename else ""
                if pre_source_type:
                    stype = pre_source_type
                elif f_ext in [".pdf", ".docx", ".txt", ".md"]:
                    stype = "document"
                elif f_ext in [".png", ".jpg", ".jpeg"]:
                    stype = "image"
                elif f_ext in [".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".wma"]:
                    stype = "audio"
                elif f_ext in [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"]:
                    stype = "video"
                else:
                    stype = "unknown"
                # Build metadata – include start_sec/end_sec for audio/video segments
                meta: dict = {
                    "filename": doc.filename,
                    "chunk_index": i,
                    "document_id": doc_id,
                    "source_type": stype,
                }
                if pre_chunked and i < len(pre_chunked):
                    seg = pre_chunked[i]
                    if "start_sec" in seg:
                        meta["start_sec"] = seg["start_sec"]
                    if "end_sec" in seg:
                        meta["end_sec"] = seg["end_sec"]
                    if "speaker" in seg and seg["speaker"]:
                        meta["speaker"] = seg["speaker"]
                metadatas.append(meta)
            return chunks, emb_out, ids, docs, metadatas

        await _set_doc_state(db, doc, status="embedded", step="embed", percent=45, message="Generating embeddings")
        
        try:
            _, embeddings, ids, documents, metadatas = await run_embedding_pipeline(init_chunk_size, init_overlap)
        except Exception as embed_err:
            err_str = str(embed_err).lower()
            if "token out of range" in err_str or "context length" in err_str or "size limit" in err_str:
                logger.warning(f"Token limit exceeded for doc {doc_id}. Retrying with smaller chunks (50% size).")
                await _set_doc_state(db, doc, status="embedded", step="embed", percent=45, message="Recovering from token limit; retrying with smaller chunks")
                fallback_size = max(200, init_chunk_size // 2)
                fallback_overlap = max(20, init_overlap // 2)
                _, embeddings, ids, documents, metadatas = await run_embedding_pipeline(fallback_size, fallback_overlap)
            else:
                raise embed_err

        if not (len(ids) == len(embeddings) == len(documents) == len(metadatas)) or len(ids) == 0:
            raise RuntimeError(
                f"Vector upsert input mismatch: ids={len(ids)} docs={len(documents)} emb={len(embeddings)} meta={len(metadatas)}"
            )

        batch_size = 96
        failures: list[str] = []
        for start in range(0, len(ids), batch_size):
            end = min(len(ids), start + batch_size)
            bid = ids[start:end]
            bdoc = documents[start:end]
            bemb = embeddings[start:end]
            bmeta = metadatas[start:end]
            if not (len(bid) == len(bdoc) == len(bemb) == len(bmeta)) or len(bid) == 0:
                failures.append(f"batch_len_mismatch({start}-{end})")
                continue
            try:
                chroma.upsert(str(doc.project_id), bid, bdoc, bemb, bmeta)
            except Exception as e:
                failures.append(str(e))
                break

        if failures:
            raise RuntimeError("Embedding upsert failed: " + "; ".join(failures[:3]))

        for i, chroma_id in enumerate(ids):
            embedding = Embedding(vector_ref=chroma_id)
            db.add(embedding)
            await db.flush()
            chunk_index = int(metadatas[i].get("chunk_index", i))
            chunk = Chunk(
                document_id=doc_id,
                project_id=doc.project_id,
                chunk_index=chunk_index,
                text=documents[i],
                citation_ref=f"Chunk {chunk_index}",
                embedding_id=embedding.id,
            )
            db.add(chunk)
        await db.commit()

        await _set_doc_state(db, doc, status="summarized", step="summarize", percent=80, message="Generating summaries")
        await analyze_document(text, doc_id, db)

        await _set_doc_state(db, doc, status="completed", step="done", percent=100, message="Completed")
        # Auto-trigger transfer learning on local models
        _schedule_auto_training(db, doc)
    except Exception as e:
        await _set_doc_state(
            db,
            doc,
            status="failed",
            step="failed",
            percent=doc.ingest_percent or 0,
            message="Failed",
            error_message=str(e),
        )
