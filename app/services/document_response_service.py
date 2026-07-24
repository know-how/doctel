"""
Document Response Service — single entry point for document Q&A.

Provides `generate_document_response(document_id, prompt, selected_model, db)`
as the common interface that ALL callers (ask endpoints, legacy chat endpoint,
internal code) must use when generating AI answers grounded in a document.

Architecture
────────────
  Caller
    │
    ▼
  generate_document_response()      ← THE single well‑known function
    │
    ├── ①  Try embedding‑based RAG via get_rag_answer_scoped()
    │        (requires the embed model to be installed in Ollama)
    │
    └── ②  Fallback: build context from DB Chunks directly
             → route to the correct provider based on selected_model
"""

import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Document, Chunk
from app.services.rag_service import get_rag_answer_scoped
from app.utils.ollama_client import ollama

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider health checks (must match the logic in ask.py & rag_service.py)
# ---------------------------------------------------------------------------
def _provider_is_cloud(model: str) -> bool:
    """Return True if *model* is a cloud‑hosted model identifier."""
    from app.services.gemini_service import GEMINI_MODEL_ID
    from app.services.deepseek_service import DEEPSEEK_MODEL_ID
    if model == GEMINI_MODEL_ID:
        return True
    if model == DEEPSEEK_MODEL_ID:
        return True
    if model.startswith("zen/") or model.startswith("go/"):
        return True
    if model.startswith("huggingface/"):
        return True
    return False


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def generate_document_response(
    document_id,
    prompt: str,
    selected_model: str,
    db: AsyncSession,
    conversation_context: Optional[str] = None,
) -> dict:
    """
    Generate an AI answer grounded in *document_id* using *selected_model*.

    This is **the** canonical function for document‑scoped Q&A.

    Parameters
    ----------
    document_id : int
        The primary key of the document in the database.
    prompt : str
        The user's question / prompt.
    selected_model : str
        The model identifier the frontend chose (e.g. ``"deepseek-chat"``,
        ``"gemini-2.0-flash-exp"``, ``"zen/deepseek-v4-flash-free"``,
        ``"huggingface/Qwen/Qwen2.5-72B-Instruct"``, or an Ollama model name).
    db : AsyncSession
        The active database session.

    Returns
    -------
    dict
        ``{"answer_text": str, "citations": list[dict], "used_model": str}``

        ``citations`` is a list of ``{"filename", "chunk_index", "text",
        "project_id", "document_id", "source_type"}`` dicts.

    Raises
    ------
    ValueError
        If *document_id* does not exist in the database.
    RuntimeError
        If no response could be obtained from any available provider.
    """
    # ── 1. Validate the document ──────────────────────────────────────
    doc = await db.get(Document, document_id)
    if doc is None:
        raise ValueError(f"Document #{document_id} not found.")

    project_id: int = doc.project_id
    project_ids = [project_id]
    question = (prompt or "").strip()
    if not question:
        return {"answer_text": "", "citations": [], "used_model": selected_model}

    sys_prompt = (settings.zetdc.system_prompt or "").strip() or None

    # ── 2. Try embedding‑based RAG ───────────────────────────────────
    answer_text: Optional[str] = None
    citations: list[dict] = []

    try:
        embed_available = False
        try:
            models = await ollama.list_models()
            embed_available = settings.embed_model in models
        except Exception:
            embed_available = False

        if embed_available:
            result = await get_rag_answer_scoped(
                project_ids,
                question,
                db,
                document_id=document_id,
                model_name=selected_model,
                conversation_context=conversation_context or None,
            )
            if result and result.get("answer_text"):
                answer_text = result["answer_text"]
                citations = result.get("citations", [])
                used_model = result.get("used_model", selected_model)
                return {
                    "answer_text": answer_text,
                    "citations": citations,
                    "used_model": used_model,
                }
    except Exception as exc:
        logger.warning(
            "embedding RAG failed for doc %s (model=%s): %s",
            document_id, selected_model, exc,
        )

    # ── 3. Fallback: retrieve chunks directly from DB ────────────────
    try:
        chunk_result = await db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
            .limit(12)
        )
        db_chunks = list(chunk_result.scalars().all())
    except Exception:
        db_chunks = []

    context_parts: list[str] = []
    citations = []
    for c in db_chunks:
        text_preview = (c.text or "")[:1500]
        context_parts.append(
            f"Source: {doc.filename or 'Unknown'}\nContent: {text_preview}"
        )
        citations.append({
            "filename": doc.filename or f"Document #{document_id}",
            "chunk_index": c.chunk_index or 0,
            "text": text_preview[:200] + "..." if len(text_preview) > 200 else text_preview,
            "project_id": project_id,
            "document_id": document_id,
            "source_type": "document",
        })

    doc_context = "\n\n".join(context_parts) if context_parts else None

    # ── GUARDRAIL: No context → return NO_KNOWLEDGE_FOUND ──────────────
    # Prevent LLM hallucination when no document chunks are available.
    if not doc_context:
        logger.warning(
            "[DOC_RESPONSE] No context available for doc %s — NO_KNOWLEDGE_FOUND guardrail triggered",
            document_id,
        )
        return {
            "answer_text": "I could not find any relevant information in this document to answer your question. The document content could not be retrieved for analysis.",
            "citations": citations,
            "used_model": selected_model,
        }

    # Build LLM prompt with conversation context when available
    # This ensures the model maintains conversational continuity even in the
    # fallback (non-embedding) path.
    fallback_question = question
    if conversation_context:
        fallback_question = (
            f"Conversation history:\n{conversation_context}\n\n"
            f"---\n\n"
            f"Current question: {question}"
        )
    fallback_prompt = (
        f"Answer the question using ONLY the provided context.\n\n"
        f"Question: {fallback_question}\n\nContext:\n{doc_context}"
    )

    # ── 4. Route to the correct provider ─────────────────────────────
    from app.services.gemini_service import (
        GEMINI_MODEL_ID,
        generate as gemini_generate,
    )
    from app.services.deepseek_service import (
        DEEPSEEK_MODEL_ID,
        generate as deepseek_generate,
    )
    from app.services.opencode_zen_service import (
        generate as zen_generate,
    )
    from app.services.huggingface_service import (
        generate as hf_generate,
    )

    import asyncio  # ensure imported for wait_for

    # 4a. DeepSeek
    if selected_model == DEEPSEEK_MODEL_ID:
        try:
            raw = await asyncio.wait_for(
                deepseek_generate(fallback_prompt, system=sys_prompt),
                timeout=120.0,
            )
            answer_text = raw or ""
        except asyncio.TimeoutError:
            answer_text = "The DeepSeek API timed out. Please try again."
        except Exception as exc:
            logger.warning("DeepSeek generate failed: %s", exc)
            answer_text = f"DeepSeek API error: {exc}"

    # 4b. Gemini
    elif selected_model == GEMINI_MODEL_ID:
        try:
            raw = await asyncio.wait_for(
                gemini_generate(fallback_prompt, system=sys_prompt),
                timeout=120.0,
            )
            answer_text = raw or ""
        except asyncio.TimeoutError:
            answer_text = "The Gemini API timed out. Please try again."
        except Exception as exc:
            logger.warning("Gemini generate failed: %s", exc)
            answer_text = f"Gemini API error: {exc}"

    # 4c. OpenCode Zen
    elif selected_model.startswith("zen/") or selected_model.startswith("go/"):
        try:
            raw = await asyncio.wait_for(
                zen_generate(fallback_prompt, model=selected_model, system=sys_prompt),
                timeout=120.0,
            )
            answer_text = raw or ""
        except asyncio.TimeoutError:
            answer_text = "The OpenCode Zen API timed out. Please try again."
        except Exception as exc:
            logger.warning("Zen generate failed: %s", exc)
            answer_text = f"OpenCode Zen API error: {exc}"

    # 4d. HuggingFace
    elif selected_model.startswith("huggingface/"):
        try:
            raw = await asyncio.wait_for(
                hf_generate(fallback_prompt, model=selected_model, system=sys_prompt),
                timeout=120.0,
            )
            answer_text = raw or ""
        except asyncio.TimeoutError:
            answer_text = "The HuggingFace API timed out. Please try again."
        except Exception as exc:
            logger.warning("HF generate failed: %s", exc)
            answer_text = f"HuggingFace API error: {exc}"

    # 4e. Ollama local model
    else:
        try:
            raw = await ollama.generate(selected_model, fallback_prompt, system=sys_prompt)
            answer_text = raw or ""
        except Exception as local_err:
            logger.warning("Local model %s failed: %s", selected_model, local_err)
            # Attempt cloud fallback cascade
            answer_text = None

            from app.services.opencode_zen_service import is_configured as zen_ok
            from app.services.deepseek_service import is_configured as deepseek_ok
            from app.services.gemini_service import is_configured as gemini_ok

            if zen_ok():
                try:
                    raw = await asyncio.wait_for(
                        zen_generate(fallback_prompt, system=sys_prompt),
                        timeout=120.0,
                    )
                    answer_text = raw or ""
                except Exception:
                    pass
            if not answer_text and deepseek_ok():
                try:
                    raw = await asyncio.wait_for(
                        deepseek_generate(fallback_prompt, system=sys_prompt),
                        timeout=120.0,
                    )
                    answer_text = raw or ""
                except Exception:
                    pass
            if not answer_text and gemini_ok():
                try:
                    raw = await asyncio.wait_for(
                        gemini_generate(fallback_prompt, system=sys_prompt),
                        timeout=120.0,
                    )
                    answer_text = raw or ""
                except Exception:
                    pass
            if not answer_text:
                answer_text = (
                    f"Local model '{selected_model}' failed and no cloud fallback was available. "
                    f"Please check that Ollama is running and the model is installed, "
                    f"or configure a cloud API key."
                )

    # ── 5. Return ────────────────────────────────────────────────────
    return {
        "answer_text": answer_text or "",
        "citations": citations,
        "used_model": selected_model,
    }
