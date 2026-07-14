import json
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.db.models import Message, Session, Chunk, Document
from app.utils.ollama_client import ollama
from app.utils.chroma_client import chroma

from app.services.embedding_service import (
    generate_embedding,
    resolve_embedding_model,
)
from sqlalchemy import select

logger = logging.getLogger(__name__)

def _dedupe_keep_order(items: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for it in items:
        key = (it.get("filename"), it.get("chunk_index"), it.get("project_id"), it.get("document_id"))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

async def get_rag_answer_scoped(
    project_ids: List[int],
    user_query: str,
    db: AsyncSession,
    document_id: Optional[int] = None,
    model_name: Optional[str] = None,
    force_policy: bool = False,
    force_diagram: bool = False,
    source_types: Optional[List[str]] = None,
):
    logger.info("[RAG] get_rag_answer_scoped called — project_ids=%s, document_id=%s, user_query_prefix=%r, source_types=%s",
                project_ids, document_id, user_query[:80] if user_query else "", source_types)

    logger.info(
        "[RAG_TRACE] retrieval_start — question=%r | projects=%s | doc_filter=%s",
        user_query[:120] if user_query else "",
        project_ids,
        document_id,
    )

    if not project_ids:
        logger.warning("[RAG] project_ids is EMPTY — no projects to search in ChromaDB")
    else:
        logger.info("[RAG] project_ids count=%d, projects=%s", len(project_ids), project_ids)

    query_embedding = await generate_embedding(db, user_query)
    logger.info("[RAG] Embedding generated — vector length=%d", len(query_embedding) if query_embedding else 0)

    # ── Resolve current embedding model for mismatch detection ────────────
    current_embedding = await resolve_embedding_model(db)
    current_provider = current_embedding["provider_name"] if current_embedding else None
    current_model = current_embedding["model_id"] if current_embedding else None
    logger.info("[RAG] Current embedding model — provider=%s, model=%s", current_provider, current_model)

    results_rows: list[dict] = []
    for pid in [int(p) for p in project_ids if p is not None]:
        try:
            where: dict = {}
            if document_id is not None:
                where["document_id"] = document_id
            if source_types:
                where["source_type"] = {"$in": source_types}
            where_clause = where if where else None
            logger.info("[RAG] ChromaDB query — project_id=%s, top_k=%s, where=%s", pid, settings.top_k, where_clause)
            res = chroma.query(str(pid), query_embedding, top_k=settings.top_k, where=where_clause)
            logger.info("[RAG] ChromaDB result for project %s — res type=%s, keys=%s", pid, type(res).__name__, list(res.keys()) if isinstance(res, dict) else "N/A")
        except Exception as exc:
            logger.error("[RAG] ChromaDB query EXCEPTION for project %s: %s", pid, exc, exc_info=True)
            continue
        docs = (res.get("documents") or [[]])[0] if isinstance(res, dict) else []
        metas = (res.get("metadatas") or [[]])[0] if isinstance(res, dict) else []
        dists = (res.get("distances") or [[]])[0] if isinstance(res, dict) else []
        # ── Raw structure diagnostics ───────────────────────────────────
        logger.info(
            "[RAG_RAW] project=%s | docs=%d | metas=%d | dists=%d | "
            "meta_types=%s",
            pid,
            len(docs or []),
            len(metas or []),
            len(dists or []),
            list(dict.fromkeys([type(m).__name__ for m in (metas or []) if m is not None]))[:5],
        )
        logger.info("[RAG] Project %s — documents returned=%d, metadatas=%d, distances=%d", pid, len(docs or []), len(metas or []), len(dists or []))
        null_meta_count = 0
        for i, txt in enumerate(docs or []):
            raw_meta = metas[i] if i < len(metas) else None
            # ── SAFETY: handle None metadata entries from ChromaDB ────
            if raw_meta is None:
                null_meta_count += 1
                if null_meta_count <= 3:
                    logger.warning(
                        "[RAG_META] index=%d meta=None — skipping chunk, "
                        "text_preview=%r",
                        i,
                        (txt or "")[:80].replace("\n", " "),
                    )
                meta = {}
            elif not isinstance(raw_meta, dict):
                null_meta_count += 1
                if null_meta_count <= 3:
                    logger.warning(
                        "[RAG_META] index=%d meta is not dict — type=%s value=%r",
                        i,
                        type(raw_meta).__name__,
                        raw_meta,
                    )
                meta = {}
            else:
                meta = raw_meta
            dist = dists[i] if i < len(dists) else None
            results_rows.append(
                {
                    "project_id": pid,
                    "document_id": meta.get("document_id"),
                    "filename": meta.get("filename", "Unknown"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "source_type": meta.get("source_type", "document"),
                    "text": txt or "",
                    "distance": float(dist) if dist is not None else 1.0,
                }
            )
        if null_meta_count > 0:
            logger.warning(
                "[RAG_RETRIEVAL] skipped_null_metadata=%d out of %d docs in project %s",
                null_meta_count,
                len(docs or []),
                pid,
            )

    results_rows.sort(key=lambda r: r.get("distance", 1.0))
    results_rows = results_rows[: max(6, int(settings.top_k or 6))]
    logger.info("[RAG] results_rows count=%d (after dedup/limit)", len(results_rows))
    if results_rows:
        logger.info("[RAG] First result — project_id=%s, document_id=%s, filename=%s, chunk_index=%s, distance=%s",
                    results_rows[0].get("project_id"), results_rows[0].get("document_id"),
                    results_rows[0].get("filename"), results_rows[0].get("chunk_index"),
                    results_rows[0].get("distance"))
        # ── Detailed per-result log ──────────────────────────────────────
        for idx, row in enumerate(results_rows[:10]):
            logger.info(
                "[RAG_RETRIEVAL] chunk %d — project=%s | doc_id=%s | filename=%s | "
                "chunk=%s | distance=%.4f | text_len=%d | text_preview=%r",
                idx,
                row.get("project_id"),
                row.get("document_id"),
                row.get("filename"),
                row.get("chunk_index"),
                row.get("distance", 1.0),
                len(row.get("text", "") or ""),
                (row.get("text", "") or "")[:80].replace("\n", " "),
            )
    else:
        logger.warning("[RAG] No retrieval results found — ChromaDB returned empty for all project_ids")

    # ── Embedding mismatch detection ──────────────────────────────────────
    # Compare each document's stored embedding model/provider against the
    # currently resolved TaskMapping.  A mismatch means the document was
    # embedded with a different model and may need re-embedding.
    mismatch_docs: list[dict] = []
    if current_provider and current_model:
        seen_doc_ids: set[int] = set()
        for r in results_rows:
            did = r.get("document_id")
            if did is not None:
                seen_doc_ids.add(int(did))
        for did in seen_doc_ids:
            result = await db.execute(select(Document).where(Document.id == did))
            doc = result.scalar_one_or_none()
            if doc and (
                doc.embedding_provider != current_provider
                or doc.embedding_model != current_model
            ):
                mismatch_docs.append({
                    "document_id": did,
                    "filename": doc.filename,
                    "stored_provider": doc.embedding_provider,
                    "stored_model": doc.embedding_model,
                    "current_provider": current_provider,
                    "current_model": current_model,
                })

    citations: list[dict] = []
    context_chunks: list[str] = []
    for r in results_rows:
        # Store full chunk text in citation (up to 1000 chars for traceability)
        full_text = r["text"] or ""
        citation: dict = {
            "filename": r["filename"],
            "chunk_index": int(r["chunk_index"] or 0),
            "text": full_text[:1000] + ("..." if len(full_text) > 1000 else ""),
            "full_text_available": len(full_text) <= 1000,
            "project_id": int(r["project_id"]),
            "document_id": int(r["document_id"]) if r.get("document_id") is not None else None,
            "source_type": r.get("source_type", "document"),
            "distance": r.get("distance", 1.0),
        }
        citations.append(citation)
        # Better formatted context for LLM with clear source attribution
        source_label = f"📖 SOURCE: {r['filename']} (Chunk {r['chunk_index']})"
        if r.get("source_type") in ("audio", "video"):
            source_label += f" [Type: {r['source_type']}]"
        context_chunks.append(
            f"{source_label}\n{'─' * 50}\n{r['text']}\n{'─' * 50}"
        )

    citations = _dedupe_keep_order(citations)
    context = "\n\n".join(context_chunks)
    logger.info("[RAG] Context built — citations count=%d, context length=%d chars, used_files=%s",
                len(citations), len(context), [c.get("filename") for c in citations if c.get("filename")])
    if not context or len(context.strip()) == 0:
        logger.warning("[RAG] No retrieval results found — context is EMPTY after building from %d results_rows", len(results_rows))
    else:
        logger.info("[RAG] Context preview (first 300 chars): %s", context[:300])
    used_files = list(dict.fromkeys([c.get("filename") for c in citations if c.get("filename")]))
    cross_refs = [{"filename": f, "reason": "Used as retrieval context"} for f in used_files[1:]]

    system_prompt = (
        "You are DocTel (ZETDC), a local, privacy-first analyst. "
        "Use ONLY the provided context to answer. "
        "CITATION RULES - YOU MUST FOLLOW THESE:\n"
        "1. When citing information, ALWAYS include the exact quoted text from the source in quotation marks.\n"
        "2. Format citations like: [Source: filename, Chunk N] immediately after the quote.\n"
        "3. Example: According to the manual, 'Application for reconnection must be submitted through the Debt Query module' [Source: Dunning Manual.pdf, Chunk 13].\n"
        "4. Never invent or paraphrase quotes - only use exact text from the provided sources.\n"
        "5. Multiple citations should each have their own quoted text.\n\n"
        "Use ZETDC terminology (transmission, distribution, substations, feeders, SCADA, HSE, ZERA compliance). "
        "SUMMARY WRITING RULES: When writing summaries, NEVER use asterisks or markdown bold formatting. "
        "NEVER use numbered or bulleted lists. Write summaries as flowing narrative paragraphs in professional prose. "
        "Begin with a clear statement of scope and purpose, then present key findings in logically ordered paragraphs, "
        "and close with implications or required actions. Maintain a formal tone suitable for ZETDC leadership and staff. "
    )
    if force_policy:
        system_prompt += (
            "When asked for a policy, output a draft policy with sections: "
            "Purpose, Scope, Definitions, Responsibilities, Procedures, Exceptions, Version Control, References. "
            "Cite internal sources."
        )
    if force_diagram:
        system_prompt += (
            "When asked for a process/diagram, output: "
            "1) concise numbered steps, 2) a Mermaid flowchart fenced block, 3) a one-sentence drawing prompt."
        )

    user_prompt = f"Question: {user_query}\n\nContext:\n{context}"
    # ── Resolve model via centralized model resolver ──────────────────────
    # This consults UI-configured task mappings as the single source of truth.
    from app.services.model_resolver_service import resolve_model
    resolved = await resolve_model(
        db,
        requested_model=model_name,
        task_type="rag"
    )
    chosen = resolved["model_id"]
    provider_type = resolved.get("provider_type", "ollama")
    provider_id = resolved.get("provider_id", "unknown")
    logger.info(
        "[RAG_MODEL] requested_model=%s | resolved_model=%s | provider_type=%s | provider_id=%s | source=%s",
        model_name, chosen, provider_type, provider_id, resolved.get("source", "?"),
    )

    logger.info(
        "[RAG_CONTEXT] built — chunk_count=%d | citation_count=%d | context_len=%d | "
        "user_prompt_len=%d | model=%s",
        len(results_rows),
        len(citations),
        len(context),
        len(user_prompt),
        chosen,
    )
    logger.info("[RAG_PROMPT] system_prompt=%d chars | user_prompt_first_300=%r",
                len(system_prompt), user_prompt[:300])

    # ── Route generation: ALWAYS try the provider gateway first ──────────
    # The gateway does a DB lookup: model → ai_models → provider_id → ai_providers.
    # If the model is NOT in the DB (e.g., a new Ollama model), the gateway
    # raises ProviderNotFoundError and we fall back to the Ollama client.
    # This ensures kimi-k2.5, deepseek, gemini, etc. always hit the right
    # cloud endpoint even when the model resolver incorrectly reports
    # provider_type=ollama (offline_only mode, missing AIModel record, etc.).
    from app.services.provider_gateway_service import generate as gateway_generate
    from app.services.provider_gateway_service import ProviderNotFoundError, ProviderNotConfiguredError
    logger.info(
        "[RAG_GATEWAY] Sending to gateway — model=%s | provider_type=%s | provider_id=%s | prompt_len=%d",
        chosen, provider_type, provider_id, len(user_prompt),
    )
    try:
        answer_text = await gateway_generate(db, user_prompt, model_id=chosen, system=system_prompt)
    except (ProviderNotFoundError, ProviderNotConfiguredError):
        # Model not in DB or provider not configured — use Ollama
        if chosen.startswith("kimi"):
            logger.warning(
                "[RAG_GATEWAY] Model '%s' is a configured cloud model but ProviderNotFound/NotConfigured — "
                "falling back to Ollama. Check that the provider for this model is correctly configured in Admin > Providers.",
                chosen,
            )
        logger.info(
            "[RAG_GENERATE] model=%s not in DB — falling back to Ollama (localhost:11434)",
            chosen,
        )
        answer_text = await ollama.generate(chosen, user_prompt, system=system_prompt)
    except Exception as gateway_err:
        if chosen.startswith("kimi"):
            logger.warning(
                "[RAG_GATEWAY] Model '%s' is a configured cloud model but gateway raised %s — "
                "falling back to Ollama. This overrides the UI-configured task mapping.",
                chosen, gateway_err,
            )
        logger.error(
            "[RAG_GENERATE] Gateway error for %s (%s) — falling back to Ollama",
            chosen, gateway_err,
        )
        answer_text = await ollama.generate(chosen, user_prompt, system=system_prompt)

    mermaid_code = ""
    drawing_prompt = ""
    if "```mermaid" in answer_text:
        try:
            start = answer_text.find("```mermaid") + len("```mermaid")
            end = answer_text.find("```", start)
            mermaid_code = answer_text[start:end].strip()
        except Exception:
            pass
    if "Drawing Prompt:" in answer_text:
        try:
            drawing_prompt = answer_text.split("Drawing Prompt:")[1].split("\n")[0].strip()
        except Exception:
            pass

    logger.info("[RAG] Returning answer — model=%s, answer_length=%d, citations=%d, embedding_mismatch=%s",
                chosen, len(answer_text) if answer_text else 0, len(citations), len(mismatch_docs) > 0)
    # ── Permanent diagnostic summary ───────────────────────────────────────
    # Logged on every RAG call so operators can trace exactly what happened.
    logger.info(
        "[RAG_DIAG] question=%r | project_ids=%s | chunks_retrieved=%d | "
        "document_ids=%s | filenames=%s | citation_count=%d | "
        "context_length=%d | answer_length=%d | model=%s",
        user_query[:120] if user_query else "",
        project_ids,
        len(results_rows),
        list(dict.fromkeys([r.get("document_id") for r in results_rows if r.get("document_id")])),
        list(dict.fromkeys([r.get("filename") for r in results_rows if r.get("filename")])),
        len(citations),
        len(context),
        len(answer_text) if answer_text else 0,
        chosen,
    )
    return {
        "answer_text": answer_text,
        "mermaid_code": mermaid_code,
        "drawing_prompt": drawing_prompt,
        "citations": citations,
        "cross_references": cross_refs,
        "used_model": chosen,
        "embedding_mismatch": len(mismatch_docs) > 0,
        "embedding_mismatch_docs": mismatch_docs,
    }

async def get_rag_answer(
    project_id: int,
    user_query: str,
    db: AsyncSession,
    session_id: Optional[int] = None,
    document_id: Optional[int] = None,
    model_name: Optional[str] = None,
):
    out = await get_rag_answer_scoped(
        [project_id],
        user_query,
        db,
        document_id=document_id,
        model_name=model_name,
        force_diagram=True,
    )
    if session_id:
        user_msg = Message(session_id=session_id, role="user", content=user_query)
        db.add(user_msg)
        assistant_msg = Message(
            session_id=session_id,
            role="assistant",
            content=out.get("answer_text", ""),
            citations_json=json.dumps(out.get("citations", [])),
        )
        db.add(assistant_msg)
        await db.commit()
    return out
