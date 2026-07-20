# Phase 3 Audit Report: Context Streaming Verification

## Executive Summary

I traced the `augmented_question` variable through ALL 5 code paths where a user's question reaches the LLM. The core concern — "is the LLM getting the raw question or the augmented question?" — is **resolved: `augmented_question` IS correctly built and sent in the streaming path.** However, the investigation uncovered **1 critical new issue (Issue #14, P1):** the streaming endpoint calls the LLM **TWICE** — once wastefully via `get_rag_answer_scoped()` (whose `answer_text` is discarded) and once again via `_stream_cloud_answer()` (the actual response). This doubles API costs on every streaming RAG request.

Additionally, 2 previously-identified issues were confirmed: (a) non-streaming `ask_global()` unsafe fallback sends raw question with no context (Issue #2), and (b) streaming path's no-context fallback sends raw question with citation-demanding system prompt (Issue #6). The document-scoped paths (`ask_document`, `ask_document_stream`) both embed context correctly — no issues found.

---

## Issue #14 (P1): Wasted LLM API Call — Duplicate Generation in Streaming Path

**Root Cause:** `ask_global_stream()` calls `get_rag_answer_scoped()` which **unconditionally calls the LLM** to produce `answer_text`. But the streaming endpoint only uses `citations` and `rag_context` from the result — the `answer_text` is **discarded**. Then the endpoint calls the LLM AGAIN via `_stream_cloud_answer()`. This doubles API costs and per-request latency.

**Exact File (wasted call):** `app/services/rag_service.py`

**Exact Lines:** 341–370

```python
# Lines 343-370 inside get_rag_answer_scoped()
try:
    answer_text, reasoning_text = await gateway_generate(db, user_prompt, model_id=chosen, system=system_prompt)
except (ProviderNotFoundError, ProviderNotConfiguredError):
    answer_text = await ollama.generate(chosen, user_prompt, system=system_prompt)
except Exception as gateway_err:
    answer_text = await ollama.generate(chosen, user_prompt, system=system_prompt)
# answer_text is generated but NEVER USED by ask_global_stream()
```

**Exact File (discarding the result):** `app/routers/ask.py`

**Exact Lines:** 828–888

```python
rag_result = await rag_scoped(...)                  # Line 828 — LLM call #1 (WASTED)
citations_list = rag_result.get("citations", [])     # Line 838 — only citations used
rag_context = "\n\n".join(...)                       # Line 844 — only context used
# rag_result["answer_text"] NEVER READ               # ← THE WASTE
...
augmented_question = f"...Context:\n{rag_context}"   # Line 870
async for event in _stream_cloud_answer(augmented_question, ...)  # Line 888 — LLM call #2 (REAL)
```

**Before Behaviour:** Every streaming POST to `/api/ask/stream` triggers TWO LLM API calls:
1. Inside `get_rag_answer_scoped()` (rag_service.py:343-370) — generates `answer_text` that is discarded
2. Inside `_stream_cloud_answer()` (ask.py:888) — generates the actual streaming response the user sees

The first call wastes API credits, increases latency by 1–30 seconds, and may incur per-token costs on cloud providers (Gemini, DeepSeek, etc.).

**After Behaviour (proposed fix):** Replace the `get_rag_answer_scoped()` call in `ask_global_stream()` with a context-only retrieval function that does NOT call the LLM. Only gathers citations and builds the context string. The single LLM call happens only in `_stream_cloud_answer()`.

**Exact Fix (Option A — recommended):**
1. Create a new async function in `app/services/rag_service.py`:
   ```python
   async def retrieve_context_only(
       db, user_query: str, project_ids: list | None = None,
       document_id: int | None = None
   ) -> dict:
       """Retrieve RAG context+citations WITHOUT calling the LLM.
       
       Returns: {"citations": [...], "rag_context": str, "used_model": str}
       """
       # Copy lines 60-265 from get_rag_answer_scoped() — the retrieval + embedding
       # logic that builds `citations` and `context` — but STOP before the LLM call.
       # Return citations and context string directly.
   ```
2. In `app/routers/ask.py`, replace line 828:
   ```python
   # OLD: rag_result = await rag_scoped(db, question, ...)  # calls LLM
   # NEW:
   rag_result = await retrieve_context_only(db, question, ...)  # no LLM call
   ```
3. Remove the `augmented_question` build logic (lines 867-874) since the context is already embedded by `_stream_cloud_answer` — OR keep it and just remove the duplicate LLM call.

---

## Context Streaming Verification: All 5 Paths

### Path 1: `ask_global_stream()` with RAG context

| Step | File | Line(s) | What Happens | Verdict |
|------|------|---------|-------------|---------|
| RAG retrieval | `ask.py` | 828 | `rag_result = await rag_scoped(...)` — DUPLICATE LLM call | ❌ Issue #14 |
| Build context | `ask.py` | 844-860 | `rag_context = "\n\n".join(...)` from citations | ✅ |
| Build augmented_question | `ask.py` | 867-874 | `augmented_question = f"Answer...Question: {question}\n\nContext:\n{rag_context}"` | ✅ |
| Pass to stream | `ask.py` | 888 | `_stream_cloud_answer(augmented_question, ...)` | ✅ |
| Stream handler | `ask.py` | 93-135 | Passes `question` to `zen_stream_with_key()` or `gateway_stream()` | ✅ |
| **LLM receives context** | — | — | Full prompt with embedded context | **✅ YES** |

### Path 2: `ask_global_stream()` WITHOUT RAG context

| Step | File | Line(s) | What Happens | Verdict |
|------|------|---------|-------------|---------|
| RAG retrieval | `ask.py` | 828 | Returns no-citations result | ✅ |
| No context | `ask.py` | 867 | `augmented_question = question` — raw question | ❌ Issue #6 |
| Pass to stream | `ask.py` | 888 | Raw question sent to LLM | ✅ (but raw) |
| **LLM receives context** | — | — | Only raw question, citation-demanding system prompt | **❌ NO — hallucination risk** |

### Path 3: `ask_global()` non-streaming with RAG context

| Step | File | Line(s) | What Happens | Verdict |
|------|------|---------|-------------|---------|
| RAG retrieval | `ask.py` | 338 | `rag = await get_rag_answer_scoped(...)` — calls LLM inside service | ✅ |
| Context embedding | `rag_service.py` | 316 | `user_prompt = f"Question: {question}\n\nContext:\n{context}"` | ✅ |
| **LLM receives context** | — | — | Context embedded in user_prompt inside rag_service | **✅ YES** |

### Path 4: `ask_global()` non-streaming WITHOUT RAG context (UNSAFE FALLBACK)

| Step | File | Line(s) | What Happens | Verdict |
|------|------|---------|-------------|---------|
| RAG retrieval | `ask.py` | 338 | Returns no-citations (or empty from no-knowledge-found) | ✅ |
| Unsafe fallback | `ask.py` | 537-625 | Sends RAW `question` to `select_model_with_fallback()` | ❌ Issue #2 |
| **LLM receives context** | — | — | Raw question with citation-demanding system prompt | **❌ NO — hallucination risk** |

### Path 5: Document-scoped (both streaming and non-streaming)

| Step | File | Line(s) | What Happens | Verdict |
|------|------|---------|-------------|---------|
| `ask_document()` | `ask.py` | ~1055 | Delegates to `generate_document_response()` | ✅ |
| `ask_document_stream()` | `ask.py` | ~1270 | Builds `doc_prompt` with context | ✅ |
| RAG path | `document_response_service.py` | 103-120 | `get_rag_answer_scoped()` — context embedded | ✅ |
| Fallback path | `document_response_service.py` | 177-180 | `fallback_prompt = f"Answer...Context:\n{doc_context}"` | ✅ |
| No-context guardrail | `document_response_service.py` | 153-162 | Returns NO_KNOWLEDGE_FOUND without calling LLM | ✅ |
| **LLM receives context** | — | — | Context embedded in ALL branches | **✅ YES** |

---

## Phase 3 Issue Register

| # | Severity | Description | File | Status |
|---|----------|-------------|------|--------|
| 14 | **P1** | Wasted LLM API call — `get_rag_answer_scoped()` generates `answer_text` that streaming endpoint discards, then calls LLM again via `_stream_cloud_answer()` | `rag_service.py:343-370` + `ask.py:828-888` | **NEW — Unfixed** |
| 2 | P0 | Unsafe fallback — non-streaming path sends raw question with citation-demanding system prompt, no RAG context | `ask.py:537-625` | Confirmed (Phase 1) |
| 6 | P3 | Streaming path sends raw question when no RAG context found (citation-demanding system prompt still active) | `ask.py:867-888` | Confirmed (Phase 1) |
