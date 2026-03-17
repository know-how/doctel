import os
import hashlib
import json
import logging
import asyncio
import time
from typing import List, Optional
from pathlib import Path
from PIL import Image
import pytesseract
from PyPDF2 import PdfReader
import docx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Document, DocAnalysis, SuggestedPrompt, Chunk, Embedding
from app.utils.ollama_client import ollama
from app.services.model_router import select_text_model
from app.utils.chroma_client import chroma

logger = logging.getLogger(__name__)

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
            if len(text.strip()) < 50:
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
                    ocr_parts.append(pytesseract.image_to_string(pil_image))
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
        try:
            text = pytesseract.image_to_string(Image.open(file_path))
        except Exception as e:
            logger.error(f"Error performing OCR on image {file_path}: {e}")
            
    return text

def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return chunks

async def analyze_document(text: str, doc_id: int, db: AsyncSession):
    # Truncate text for analysis if needed to fit model context
    analysis_text = text[:12000]
    
    system_prompt = "You are a local, privacy-first analyst. Analyze the provided document text."
    
    # 1. Summaries
    summary_prompt = (
        "Produce an Executive Summary (max 10 sentences) and a Detailed Summary (bullets/short paragraphs) "
        "of the following text:\n\n" + analysis_text
    )
    model_name = select_text_model("summary_long")
    summaries_raw = await ollama.generate(model_name, summary_prompt, system=system_prompt)
    
    # Split executive and detailed (heuristic)
    parts = summaries_raw.split("\n\n")
    exec_summary = parts[0] if parts else ""
    detailed_summary = "\n\n".join(parts[1:]) if len(parts) > 1 else ""
    
    # 2. Key Insights
    insights_prompt = (
        "Extract key entities (people, orgs, dates), key topics/themes, overall sentiment "
        "(Positive, Neutral, Negative, Urgent), and any action items and decisions if present. "
        "Return ONLY a JSON object with keys: "
        "entities (list of strings), topics (list of strings), sentiment (string), "
        "action_items (list of strings), decisions (list of strings).\n\n"
        + analysis_text
    )
    insights_raw = await ollama.generate(model_name, insights_prompt, system=system_prompt)
    try:
        # Simple JSON extraction from LLM response
        json_start = insights_raw.find("{")
        json_end = insights_raw.rfind("}") + 1
        insights_json = json.loads(insights_raw[json_start:json_end])
    except Exception:
        insights_json = {"entities": [], "topics": [], "sentiment": "Neutral", "action_items": [], "decisions": []}
        
    # 3. Suggested Prompts
    prompts_prompt = (
        "Propose 5 specific, actionable questions a user should ask about this document. "
        "Make them document-specific (not generic), and include at least one prompt that asks to "
        "generate a process flow / diagram (Mermaid), and one prompt that asks to extract action items/decisions. "
        "Return ONLY a JSON object: {\"prompts\": [\"...\", ...]}.\n\n"
        + analysis_text
    )
    prompts_raw = await ollama.generate(model_name, prompts_prompt, system=system_prompt)
    suggested_prompts = []
    try:
        js = json.loads(prompts_raw[prompts_raw.find("{"):prompts_raw.rfind("}") + 1])
        suggested_prompts = [str(p).strip() for p in (js.get("prompts") or []) if str(p).strip()]
    except Exception:
        suggested_prompts = [p.strip("- ").strip() for p in prompts_raw.split("\n") if p.strip()]
    if len(suggested_prompts) < 3:
        suggested_prompts = (suggested_prompts + [
            "Summarize the key purpose and scope of this document.",
            "List all action items and decisions mentioned in this document.",
            "Generate a process flow diagram (Mermaid) from this document.",
            "What are the key risks and mitigations mentioned in this document?",
            "List any requirements, deadlines, and responsible parties mentioned.",
        ])[:5]
    
    # Save to DB
    analysis = DocAnalysis(
        document_id=doc_id,
        executive_summary=exec_summary,
        detailed_summary=detailed_summary,
        sentiment=insights_json.get("sentiment", "Neutral"),
        entities_json=json.dumps(insights_json.get("entities", [])),
        topics_json=json.dumps(insights_json.get("topics", [])),
        action_items_json=json.dumps(insights_json.get("action_items", [])),
        decisions_json=json.dumps(insights_json.get("decisions", [])),
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
        chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        chunks = [c.strip() for c in (chunks or []) if isinstance(c, str) and c.strip()]
        if not chunks:
            await _set_doc_state(
                db,
                doc,
                status="failed",
                step="chunk",
                percent=20,
                message="Chunking failed",
                error_message="Chunking produced no chunks",
            )
            return

        await _set_doc_state(db, doc, status="embedded", step="embed", percent=45, message="Generating embeddings")
        sem = asyncio.Semaphore(2)

        embeddings: list[list[float]] = []
        metadatas: list[dict] = []
        ids: list[str] = []
        documents: list[str] = []

        async def embed_one(i: int, chunk_text_content: str):
            async with sem:
                vec = await ollama.embed(settings.embed_model, chunk_text_content)
                return i, vec

        results = await asyncio.gather(*(embed_one(i, c) for i, c in enumerate(chunks)))
        results.sort(key=lambda x: x[0])
        for i, vec in results:
            if i < 0 or i >= len(chunks):
                continue
            chunk_text_content = chunks[i].strip()
            if not chunk_text_content:
                continue
            chroma_id = f"chroma_{doc_id}_{i}"
            ids.append(chroma_id)
            embeddings.append(vec)
            documents.append(chunk_text_content)
            metadatas.append({"filename": doc.filename, "chunk_index": i, "document_id": doc_id})

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
