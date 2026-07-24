import json
import logging
import re
from typing import List, Optional, Union
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

logger = logging.getLogger(__name__)

_GREETING_PATTERN = re.compile(
    r"^(hi|hello|hey|good morning|good afternoon|good evening|"
    r"how are you|thanks|thank you)[\s!?.]*$",
    re.IGNORECASE,
)

def _is_greeting(text: str) -> bool:
    """Return True if *text* is a simple greeting that should skip RAG retrieval."""
    return bool(_GREETING_PATTERN.match(text.strip()))

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
    project_ids: List[Union[int, str]],
    user_query: str,
    db: AsyncSession,
    document_id: Optional[Union[int, str]] = None,
    model_name: Optional[str] = None,
    force_policy: bool = False,
    force_diagram: bool = False,
    source_types: Optional[List[str]] = None,
    conversation_context: Optional[str] = None,
):
    logger.info("[RAG] get_rag_answer_scoped called — project_ids=%s, document_id=%s, user_query_prefix=%r, source_types=%s",
                project_ids, document_id, user_query[:80] if user_query else "", source_types)

    logger.info(
        "[RAG_TRACE] retrieval_start — question=%r | projects=%s | doc_filter=%s",
        user_query[:120] if user_query else "",
        project_ids,
        document_id,
    )

    # ── Greeting detection — skip RAG entirely for simple greetings ────
    if _is_greeting(user_query):
        logger.info("[RAG_GREETING] greeting_detected — input=%r | skipping RAG retrieval", user_query)
        return {
            "answer_text": "Hello from DocTel, your ZETDC AI assistant. How can I help you today?",
            "reasoning_text": "",
            "mermaid_code": "",
            "drawing_prompt": "",
            "citations": [],
            "cross_references": [],
            "used_model": "greeting-detection",
            "embedding_mismatch": False,
            "embedding_mismatch_docs": [],
        }

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
    for pid in project_ids:
        if pid is None:
            continue
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
    # NOTE: This is a diagnostic feature — failures are caught and logged
    #       but never allowed to crash the main retrieval pipeline.
    import uuid
    mismatch_docs: list[dict] = []
    if current_provider and current_model:
        try:
            seen_doc_ids: set = set()
            for r in results_rows:
                did = r.get("document_id")
                if did is not None:
                    seen_doc_ids.add(str(did))
            for did_str in seen_doc_ids:
                try:
                    uid = uuid.UUID(did_str) if isinstance(did_str, str) else did_str
                except (ValueError, TypeError):
                    logger.warning("[RAG_MISMATCH] Skipping invalid document_id=%r", did_str)
                    continue
                result = await db.execute(select(Document).where(Document.id == uid))
                doc = result.scalar_one_or_none()
                if doc and (
                    doc.embedding_provider != current_provider
                    or doc.embedding_model != current_model
                ):
                    mismatch_docs.append({
                        "document_id": did_str,
                        "filename": doc.filename,
                        "stored_provider": doc.embedding_provider,
                        "stored_model": doc.embedding_model,
                        "current_provider": current_provider,
                        "current_model": current_model,
                    })
        except Exception as exc:
            logger.warning("[RAG_MISMATCH] Mismatch detection failed (non-critical): %s", exc, exc_info=True)

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
            "project_id": str(r["project_id"]) if not isinstance(r["project_id"], int) else r["project_id"],
            "document_id": str(r["document_id"]) if r.get("document_id") is not None else None,
            "source_type": r.get("source_type", "document"),
            "distance": r.get("distance", 1.0),
        }
        citations.append(citation)
        # Better formatted context for LLM with clear source attribution
        source_label = f"📄 {r['filename']}"
        if r.get("source_type") in ("audio", "video"):
            source_label += f" [Type: {r['source_type']}]"
        context_chunks.append(
            f"{source_label}\n{'─' * 50}\n{r['text']}\n{'─' * 50}"
        )

    citations = _dedupe_keep_order(citations)
    context = "\n\n".join(context_chunks)
    logger.info("[RAG] Context built — citations count=%d, context length=%d chars, used_files=%s",
                len(citations), len(context), [c.get("filename") for c in citations if c.get("filename")])
    # ── GUARDRAIL: No context → return NO_KNOWLEDGE_FOUND ──────────────
    # Prevent LLM hallucination by refusing to call the model when no
    # retrieval context is available.
    if not context or len(context.strip()) == 0:
        logger.warning(
            "[RAG] No retrieval results — NO_KNOWLEDGE_FOUND guardrail triggered (no LLM call to prevent hallucination)"
        )
        logger.info(
            "[RAG_GUARD] guardrail=no_context | question=%r | project_ids=%s | document_id=%s | results_rows=%d",
            user_query[:120] if user_query else "",
            project_ids,
            document_id,
            len(results_rows),
        )
        return {
            "answer_text": "I could not find any relevant information in the knowledge base to answer your question. Please try rephrasing or providing more specific details.",
            "reasoning_text": "",
            "mermaid_code": "",
            "drawing_prompt": "",
            "citations": [],
            "cross_references": [],
            "used_model": "no-knowledge-found",
            "embedding_mismatch": False,
            "embedding_mismatch_docs": [],
        }

    logger.info("[RAG] Context preview (first 300 chars): %s", context[:300])
    used_files = list(dict.fromkeys([c.get("filename") for c in citations if c.get("filename")]))
    cross_refs = [{"filename": f, "reason": "Used as retrieval context"} for f in used_files[1:]]

    # ── Detect query type from the user's question ──────────────────────
    # This determines the response structure. Different question types need
    # different answer formats to provide the best user experience.
    query_lower = user_query.strip().lower()
    is_definition = bool(re.search(r"^(what|who|define|describe|explain)\s+(is|are|was|does|a|an|the)\b", query_lower))
    is_procedure = bool(re.search(r"^(how|what steps|what process|steps to|procedure|guide|walkthrough)\b", query_lower))
    is_policy = bool(re.search(r"\b(policy|policies|regulation|compliance|rule|standard|requirement|guideline|directive)\b", query_lower))
    is_comparison = bool(re.search(r"\b(compare|contrast|difference|vs\.?|versus|pros and cons|similarities)\b", query_lower))

    system_prompt = (
        "You are DocTel, ZETDC's enterprise AI assistant. Your role is to help ZETDC staff "
        "by providing clear, accurate answers grounded in internal documents.\n\n"
        "CRITICAL RULES:\n"
        "1. USE THE RETRIEVED DATA — The context below contains actual document content. "
        "Use the EXACT information from the context in your answer. List specific items, "
        "functions, and details that appear in the retrieved text. Do NOT generate a "
        "generic summary that ignores the specific data provided.\n"
        "2. NO SOURCE LINES IN ANSWER — Do NOT include any 'Source:', 'Based on', "
        "or 'According to' text IN the answer body. Source attribution is handled "
        "separately by the citation system. The user can see source documents in the "
        "citation cards below your answer.\n"
        "3. NO INLINE CITATIONS — Never write [Source: ...], (Source: ...), or "
        "'Source: Document Name' anywhere in your answer text.\n"
        "4. HIDE INTERNAL MECHANICS — Never mention 'chunk', 'context', 'document_id', "
        "or 'retrieval'.\n"
        "5. PARAPHRASE — Summarize information in your own words. Only use exact quotes "
        "for definitions, regulations, laws, or numerical specifications.\n"
        "6. TONE — Professional, concise, helpful. Avoid jargon unless the user's question "
        "demonstrates technical knowledge.\n\n"
        "INTENT-BASED RESPONSE TEMPLATES:\n"
    )

    if is_definition:
        system_prompt += (
            'The user is asking a DEFINITION question ("What is X?"). Use this structure:\n'
            '- First line: A clear, concise definition of the entity (what it is, its purpose).\n'
            '- Then: Key features or characteristics, using ACTUAL data from the context. '
            'List specific items (e.g., function IDs like F-CRM-007, specific capabilities).\n'
        )
    elif is_procedure:
        system_prompt += (
            'The user is asking a PROCEDURE question ("How do I?"). Use this structure:\n'
            '- First: A brief overview of what the procedure accomplishes.\n'
            '- Then: Numbered steps based on the retrieved document content.\n'
        )
    elif is_policy:
        system_prompt += (
            'The user is asking a POLICY question. Use this structure:\n'
            '- Summary: A 1-2 sentence overview of the policy.\n'
            '- Key Requirements: Specific rules, thresholds, or obligations from the document.\n'
        )
    elif is_comparison:
        system_prompt += (
            'The user is asking a COMPARISON question. Use this structure:\n'
            '- First: Identify the items being compared.\n'
            '- Then: Present differences and similarities using a structured format.\n'
            '- If the context lacks information for a fair comparison, say so clearly.\n'
        )
    else:
        system_prompt += (
            'For general questions:\n'
            '- Start with a direct answer to the question.\n'
            '- Use specific details from the retrieved context.\n'
            '- When asked about a system capabilities, list the actual functions '
            'and features described in the source documents.\n'
        )

    system_prompt += (
        "\nUse ZETDC terminology (transmission, distribution, substations, feeders, SCADA, HSE, ZERA compliance) "
        "when the context warrants it.\n\n"
        "SUMMARY WRITING RULES: When writing summaries, use flowing narrative paragraphs. "
        "Avoid bullet lists, numbered lists, and markdown formatting. "
        "Begin with a clear statement of scope and purpose, present key findings in logically ordered paragraphs, "
        "and close with implications or required actions. Maintain a formal tone suitable for ZETDC leadership and staff.\n\n"
        "CONVERSATIONAL CONTINUITY:\n"
        "The 'Conversation history' section contains the prior Q&A context. Use it to "
        "maintain coherent multi-turn dialogue. Follow these rules:\n"
        "1. RESOLVE CONTEXTUAL REFERENCES — If the current question uses pronouns (it, they, "
        "this, that, these, its) or implicit references ('the system', 'the document', 'the "
        "process'), first look at the conversation history to determine what entity they refer "
        "to, then answer based on that resolved reference.\n"
        "2. CONCEPT CHAINING — When the user asks about a relationship (e.g., 'What is its "
        "relationship with X?' or 'How does it compare to Y?'), identify the referent from "
        "the conversation history and answer the comparative or relational question directly, "
        "not just the new entity in isolation.\n"
        "3. SEQUENTIAL ELABORATION — When the user builds on a previous topic (e.g., asking "
        "'What are the modules?' after being told about a system), elaborate based on the "
        "established context. Do NOT re-introduce the earlier topic as brand-new information.\n"
        "4. CONTINUITY MARKERS — When appropriate, use natural transition phrases like "
        "'As mentioned', 'Building on the previous answer', 'In addition to the above', "
        "or 'To expand on that' to create a connected conversational flow.\n"
        "5. IMPLICIT COMPARISON — If the current question asks about something related to a "
        "previously discussed concept (e.g., 'What about [related entity]?'), frame the answer "
        "by drawing comparisons or contrasts with what was already covered.\n"
        "6. REDUNDANCY AVOIDANCE — When answering a follow-up that builds on prior discussion, "
        "do NOT re-state the full definition or introduction of already-established concepts "
        "unless the user explicitly requests a recap.\n\n"
        "If the conversation history is empty or the question is fully self-contained, ignore "
        "all of the above and answer based solely on the retrieved context."
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

    # Build the user prompt with optional conversation history
    user_prompt_parts = []
    if conversation_context:
        user_prompt_parts.append(f"Conversation history:\n{conversation_context}\n")
    user_prompt_parts.append(f"Current question: {user_query}")
    user_prompt_parts.append(f"\nRetrieved context:\n{context}")
    user_prompt = "\n\n---\n\n".join(user_prompt_parts)
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
        answer_text, reasoning_text = await gateway_generate(db, user_prompt, model_id=chosen, system=system_prompt)
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
        reasoning_text = ""
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
        reasoning_text = ""

    # ── Answer grounding validation ───────────────────────────────────────
    # Check whether the model-generated answer's key claims appear in the
    # retrieved chunks.  If too many claims are ungrounded, replace the
    # answer with a neutral "insufficient evidence" message to prevent
    # hallucination drift over long conversations.
    from app.services.answer_validator import validate_grounding
    chunk_texts = [c.get("text", "") for c in citations if c.get("text")]
    validation = validate_grounding(
        answer_text,
        chunk_texts,
        filename=used_files[0] if used_files else None,
    )
    if validation["rejected"]:
        logger.info(
            "[RAG_VALIDATOR] Replaced ungrounded answer — "
            "score=%.2f | claims=%d | ungrounded=%s",
            validation["score"],
            validation["total_claims"],
            validation["ungrounded_claims"][:5],
        )
        answer_text = validation["replacement"]
        # Clear reasoning since the replacement is a fixed message
        reasoning_text = ""

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
        "reasoning_text": reasoning_text,
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
    document_id: Optional[Union[int, str]] = None,
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
