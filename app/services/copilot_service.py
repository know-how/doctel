"""
copilot_service.py — DocTel Copilot Engine

Multi-mode interaction orchestrator for the DocTel AI assistant.
Provides four interaction modes:
  - chat:       Standard conversational Q&A with RAG context
  - research:   Deep multi-pass retrieval with expanded context
  - analyze:    Structured document analysis with formatting rules
  - draft:      Template-based document generation

Each mode configures system prompts, retrieval depth, and response formatting.
"""

import json
import logging
import re
from enum import Enum
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag_service import get_rag_answer_scoped
from app.services.model_resolver_service import resolve_model
from app.services.gemini_service import GEMINI_MODEL_ID, generate as gemini_generate
from app.services.deepseek_service import DEEPSEEK_MODEL_ID, generate as deepseek_generate
from app.services.opencode_zen_service import generate as zen_generate

logger = logging.getLogger(__name__)


class CopilotMode(str, Enum):
    CHAT = "chat"
    RESEARCH = "research"
    ANALYZE = "analyze"
    DRAFT = "draft"


MODE_DESCRIPTIONS = {
    CopilotMode.CHAT: "Standard conversational Q&A with document context",
    CopilotMode.RESEARCH: "Deep multi-pass analysis with expanded retrieval",
    CopilotMode.ANALYZE: "Structured document analysis with formal reporting",
    CopilotMode.DRAFT: "Template-based document and policy generation",
}

# ── Intent detection patterns ────────────────────────────────────────────────

_INTENT_PATTERNS: dict[str, list[str]] = {
    "summarize": [
        r"summarize", r"summary", r"summarise", r"tl;dr", r"gist",
        r"key.?points", r"brief me", r"overview",
    ],
    "research": [
        r"research", r"deep.?dive", r"investigate", r"thorough",
        r"comprehensive", r"explore", r"dig into",
    ],
    "analyze": [
        r"analyze", r"analyse", r"examine", r"evaluate", r"assessment",
        r"sentiment", r"trend", r"pattern", r"break.?down",
    ],
    "draft": [
        r"draft", r"write", r"compose", r"create", r"generate",
        r"policy", r"memo", r"report", r"letter", r"procedure",
    ],
    "diagram": [
        r"diagram", r"flowchart", r"mermaid", r"process.?flow",
        r"architecture", r"schema", r"visualize",
    ],
    "compare": [
        r"compare", r"contrast", r"difference", r"vs\.?", r"versus",
        r"similarities", r"pros and cons",
    ],
}


def detect_intent(user_query: str) -> dict[str, Any]:
    """Detect user intent from the query text.

    Returns:
        dict with keys:
          - primary_intent: str — the best-matching intent label
          - matched_patterns: list[str] — all matched intents
          - suggested_mode: CopilotMode — recommended mode based on intent
    """
    query_lower = user_query.lower()
    matched: list[str] = []
    for intent, patterns in _INTENT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, query_lower):
                matched.append(intent)
                break

    primary = matched[0] if matched else "chat"

    # Map intent → mode
    mode_map: dict[str, CopilotMode] = {
        "summarize": CopilotMode.ANALYZE,
        "research": CopilotMode.RESEARCH,
        "analyze": CopilotMode.ANALYZE,
        "draft": CopilotMode.DRAFT,
        "diagram": CopilotMode.CHAT,
        "compare": CopilotMode.RESEARCH,
    }
    suggested = mode_map.get(primary, CopilotMode.CHAT)

    return {
        "primary_intent": primary,
        "matched_patterns": matched,
        "suggested_mode": suggested,
    }


_MODE_SYSTEM_PROMPTS = {
    CopilotMode.CHAT: (
        "You are DocTel (ZETDC), a local, privacy-first analyst. "
        "Use ONLY the provided context to answer. "
        "Always include short citations like [Doc: <filename>, chunk <n>]. "
        "Use ZETDC terminology (transmission, distribution, substations, feeders, SCADA, HSE, ZERA compliance). "
        "SUMMARY WRITING RULES: When writing summaries, NEVER use asterisks or markdown bold formatting. "
        "NEVER use numbered or bulleted lists. Write summaries as flowing narrative paragraphs in professional prose. "
        "Begin with a clear statement of scope and purpose, then present key findings in logically ordered paragraphs, "
        "and close with implications or required actions. Maintain a formal tone suitable for ZETDC leadership and staff."
    ),
    CopilotMode.RESEARCH: (
        "You are a senior research analyst for ZETDC. Provide a comprehensive, multi-perspective answer "
        "based on the retrieved document context. Structure your response with an executive summary, "
        "detailed findings organised by theme, supporting evidence with citations, and actionable conclusions. "
        "If the context is insufficient, state what additional information would be needed. "
        "ALWAYS cite sources as [Doc: <filename>, chunk <n>]. "
        "Write in professional prose — never use asterisks, bullet lists, or numbered lists."
    ),
    CopilotMode.ANALYZE: (
        "You are a document analysis specialist for ZETDC. Perform a structured analysis of the provided context. "
        "Your response must cover: 1) Document purpose and scope, 2) Key findings and themes, "
        "3) Notable entities and relationships, 4) Sentiment and tone assessment, "
        "5) Action items or decisions identified. "
        "Write in flowing narrative paragraphs. NEVER use asterisks, bullet lists, or numbered lists. "
        "Cite specific chunks as evidence using [Doc: <filename>, chunk <n>]."
    ),
    CopilotMode.DRAFT: (
        "You are a technical writer for ZETDC. Based on the provided context and user request, "
        "draft a professional document. Follow ZETDC document standards: clear sections, "
        "formal tone, precise language. Include a document purpose statement at the beginning. "
        "If drafting a policy, include: Purpose, Scope, Definitions, Responsibilities, Procedures, "
        "Exceptions, Version Control, References sections. "
        "Write in flowing narrative paragraphs. NEVER use asterisks, bullet lists, or numbered lists."
    ),
}

# ── Research mode: multi-pass retrieval ──────────────────────────────────────


async def _research_retrieval(
    project_ids: list[int],
    user_query: str,
    db: AsyncSession,
    document_id: Optional[int] = None,
) -> tuple[str, list[dict]]:
    """Multi-pass retrieval for deep research.

    First pass: standard RAG retrieval (top_k).
    Second pass: expanded query using key terms from the first-pass context.
    Combined results are deduplicated and returned.
    """
    from app.utils.ollama_client import ollama

    # Pass 1 — standard retrieval
    pass1 = await get_rag_answer_scoped(
        project_ids, user_query, db,
        document_id=document_id,
        force_policy=False, force_diagram=False,
    )
    all_rows_meta: list[dict] = pass1.get("citations", [])
    context_text = pass1.get("answer_text", "")

    # Extract key terms for Pass 2 query expansion
    key_terms = _extract_key_terms(user_query, context_text)
    if key_terms:
        expanded_query = f"{user_query} {' '.join(key_terms[:5])}"
        pass2 = await get_rag_answer_scoped(
            project_ids, expanded_query, db,
            document_id=document_id,
            force_policy=False, force_diagram=False,
        )
        for cite in pass2.get("citations", []):
            if cite not in all_rows_meta:
                all_rows_meta.append(cite)

    return pass1.get("answer_text", ""), all_rows_meta


def _extract_key_terms(query: str, context: str, max_terms: int = 8) -> list[str]:
    """Simple key term extraction — pulls capitalized phrases and frequent non-stop words."""
    import re
    from collections import Counter

    # Find capitalized phrases (potential named entities / domain terms)
    capitalized = re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,3}\b", context)
    words = re.findall(r"\b[a-zA-Z]{4,}\b", context.lower())
    stop_words = {
        "this", "that", "with", "from", "have", "been", "will", "were",
        "what", "when", "where", "which", "their", "there", "about",
        "would", "could", "should", "also", "than", "then", "into",
        "more", "some", "such", "only", "other", "over", "very",
    }
    content_words = [w for w in words if w not in stop_words]
    freq = Counter(content_words)

    # Prioritize capitalized terms, then frequent content words
    seen: set[str] = set()
    terms: list[str] = []
    for term in capitalized:
        lower = term.lower()
        if lower not in seen:
            terms.append(term)
            seen.add(lower)
    for word, _ in freq.most_common(max_terms):
        if word not in seen:
            terms.append(word)
            seen.add(word)
    return terms[:max_terms]


# ── Main Copilot entry point ─────────────────────────────────────────────────


async def copilot_answer(
    project_ids: list[int],
    user_query: str,
    db: AsyncSession,
    mode: CopilotMode = CopilotMode.CHAT,
    document_id: Optional[int] = None,
    model_name: Optional[str] = None,
    source_types: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Copilot engine — routes to the appropriate mode handler.

    Args:
        project_ids: List of project IDs to scope retrieval.
        user_query: The user's question or request.
        db: Database session.
        mode: Interaction mode (chat, research, analyze, draft).
        document_id: Optional document ID to scope retrieval.
        model_name: Optional model override.
        source_types: Optional list of source types to filter (e.g. ["audio", "document"]).

    Returns:
        dict with keys: answer_text, mode, citations, used_model, intent_info, mermaid_code, drawing_prompt
    """
    intent_info = detect_intent(user_query)

    # Auto-suggest mode if user query matches a strong intent and mode wasn't explicitly set
    if mode == CopilotMode.CHAT and intent_info["primary_intent"] != "chat":
        suggested = intent_info["suggested_mode"]
        logger.info(f"Intent '{intent_info['primary_intent']}' detected — suggesting mode {suggested.value}")

    system_prompt = _MODE_SYSTEM_PROMPTS.get(mode, _MODE_SYSTEM_PROMPTS[CopilotMode.CHAT])

    if mode == CopilotMode.RESEARCH:
        # Multi-pass retrieval for deep research
        rag_context, citations = await _research_retrieval(
            project_ids, user_query, db, document_id=document_id,
        )
    else:
        # Single-pass RAG retrieval for chat/analyze/draft
        rag_result = await get_rag_answer_scoped(
            project_ids, user_query, db,
            document_id=document_id,
            model_name=model_name,
            force_policy=(mode == CopilotMode.DRAFT),
            force_diagram=False,
            source_types=source_types,
        )
        rag_context = rag_result.get("answer_text", "")
        citations = rag_result.get("citations", [])

    # Build context from RAG result
    context_str = rag_context if rag_context else f"Question: {user_query}"

    # Generate final response via centralized model resolver
    # Consults UI-configured task mappings as single source of truth.
    resolved = await resolve_model(db, requested_model=model_name, task_type="rag")
    chosen = resolved["model_id"]
    user_prompt = f"Mode: {mode.value}\n\nRequest: {user_query}\n\nContext:\n{context_str}"

    if chosen == DEEPSEEK_MODEL_ID:
        answer_text = await deepseek_generate(user_prompt, system=system_prompt)
    elif chosen == GEMINI_MODEL_ID:
        answer_text = await gemini_generate(user_prompt, system=system_prompt)
    elif chosen.startswith("zen/") or chosen.startswith("go/"):
        answer_text = await zen_generate(user_prompt, model=chosen, system=system_prompt)
    else:
        from app.utils.ollama_client import ollama
        answer_text = await ollama.generate(chosen, user_prompt, system=system_prompt)

    # Extract optional diagram / drawing prompts
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

    return {
        "answer_text": answer_text,
        "mode": mode.value,
        "citations": citations,
        "used_model": chosen,
        "intent_info": intent_info,
        "mermaid_code": mermaid_code,
        "drawing_prompt": drawing_prompt,
    }
