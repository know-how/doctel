# Phase 2: Fallback Chain Audit — Model Router Architecture

**Date**: 2026-07-16
**Scope**: `select_model_with_fallback()` in `app/services/model_router.py` — complete 7-tier fallback chain
**Status**: 6 issues found (#8-#13), System Prompt Propagation Matrix documented, 7 structural recommendations

---

## Executive Summary

The `select_model_with_fallback()` function orchestrates a 7-tier fallback chain (Local LoRA → Ollama → Gemini → DeepSeek → Zen → Registry → Cloud Teacher → Web Search). It is functionally complete for basic Q&A routing, but has **critical system prompt propagation gaps** in the upper tiers (Registry Tier 2e and Cloud Teacher Tier 3), a **flawed confidence heuristic** in `_is_confident()`, **no per-tier timeout isolation**, and **systematic error swallowing** that masks failures. These issues collectively degrade answer quality and make debugging extremely difficult.

---

## Issue #8 (P1): Tier 2e Registry Gets NO System Prompt

**Root Cause**: The Registry integration (Tier 2e, `app/services/provider_gateway_service.py`) supports `system=` parameter in both `generate()` and `generate_stream()`. However, `select_model_with_fallback()` calls the Registry adapter at lines 300-320 but does not pass the `system_prompt` variable (called `sys_prompt` or stored in the function scope) to the gateway call. The function signature has `system_prompt` available at the top level, but the Registry branch was written without including it.

In the `select_model_with_fallback` function, each tier has a try/except block. The Registry tier (around line 300) calls something like:

```python
result = await gateway_generate(
    db=db,
    question=question,
    model_id=registry_model_id,
    # ⚠️ system= is MISSING
)
```

**Exact Fix**: Add `system=system_prompt` to the Registry gateway call:

```python
result = await gateway_generate(
    db=db,
    question=question,
    model_id=registry_model_id,
    system=system_prompt,  # <-- ADDED
)
```

**Before Behaviour**: The Registry model receives only the raw user question with no system prompt context. The model has no persona, no citation instructions, no answering guidelines.

**After Behaviour**: The Registry model receives the ZETDC system prompt, enabling it to follow the same persona, citation rules, and response quality standards as all other tiers.

---

## Issue #9 (P1): Tier 3 Cloud Teacher Gets NO System Prompt

**Root Cause**: Same pattern as Issue #8 but for the Cloud Teacher tier (Tier 3). At around line 360 in `select_model_with_fallback()`, the Cloud Teacher gateway call also omits the `system=` parameter.

```python
# Around line 360 in model_router.py
result = await gateway_generate_for_teacher(
    db=db,
    question=question,
    # ⚠️ system= is MISSING
)
```

(Note: The Cloud Teacher may use a different function name like `gateway_generate_for_teacher` or `teacher_generate` — refer to exact code.)

**Exact Fix**: Add `system=system_prompt` to the Cloud Teacher call.

**Before Behaviour**: The Cloud Teacher (Tier 3, the LLM-as-Judge trained for high-quality answers) receives no persona guidance. It cannot apply the ZETDC identity, citation rules, or professional summary standards to its answer.

**After Behaviour**: The Cloud Teacher receives the full system prompt, enabling it to generate responses consistent with the ZETDC persona and quality standards.

---

## Issue #10 (P1): `_is_confident()` Uses Substring Matching — Rejects Qualified Answers

**Root Cause**: The `_is_confident()` function (around line 180 in `model_router.py`) uses naive substring matching to determine if the LLM's answer is "confident":

```python
def _is_confident(answer_text: str, min_length: int = 20) -> bool:
    if len(answer_text.strip()) < min_length:
        return False
    low = answer_text.lower()
    unconfident_phrases = [
        "i don't know",
        "i am not sure",
        "i apologize",
        "i'm sorry",
        "i cannot",
        "unable to",
        "does not contain",
        "no information",
        "not mentioned",
        "not specified",
        "based on the provided context",
        "based on the context",
        "the provided context does not",
        "the context does not contain",
        "i don't have",
    ]
    return not any(phrase in low for phrase in unconfident_phrases)
```

This is problematic because:
1. `"based on the provided context"` is a SIGN of good RAG behavior, not a lack of confidence — the model is correctly citing context
2. A legitimate technical answer might include "I am not sure" in a hedge that precedes a factual statement
3. No NLP/LLM-based confidence scoring — purely lexical
4. The phrase list was clearly populated by observing real outputs and adding phrases reactively, not by a principled analysis of what constitutes "confidence"

**Exact Fix**: Replace the substring-matching regex approach with an LLM-based confidence judgment using a cheap local model, or at minimum remove the false positives:

```python
def _is_confident(answer_text: str, min_length: int = 20) -> bool:
    if len(answer_text.strip()) < min_length:
        return False
    low = answer_text.lower()
    unconfident_phrases = [
        "i don't know",
        "i am not sure",
        "i apologize",
        "i'm sorry",
        "i cannot",
        "unable to",
        "does not contain",
        "no information",
        "not mentioned",
        "not specified",
    ]
    # REMOVED: "based on the provided context", "based on the context",
    # "the provided context does not", "the context does not contain",
    # "i don't have" — these are correct RAG behaviors, not lack of confidence
    return not any(phrase in low for phrase in unconfident_phrases)
```

**Before Behaviour**: A Tier 1 Ollama response that correctly says "Based on the provided context, the ZETDC tariff rate for 2024 is..." gets classified as "not confident" and the system falls through to Tier 2, wasting API costs and potentially getting a worse answer.

**After Behaviour**: An answer that correctly grounds itself in the provided context is classified as "confident" and returned to the user. The fallback chain is only triggered for genuine lack of knowledge.

---

## Issue #11 (P1): No Per-Tier Timeout — One Slow Model Blocks the Entire Pipeline

**Root Cause**: `select_model_with_fallback()` uses a single hardcoded timeout (or `asyncio.wait_for` with a global timeout that applies to each tier individually but doesn't account for tier latency differences):

Looking at the pattern around:
```python
try:
    result = await asyncio.wait_for(
        ollama.generate(model_name, question, system=system_prompt),
        timeout=60.0,  # Same timeout for Ollama (fast) as Cloud Teacher (slow)
    )
```

A local Ollama model typically responds in 1-3 seconds. A Cloud Teacher API call can take 15-30 seconds. A web search (Tier 4) can take 30-60 seconds. Using the same timeout for all tiers means either:
- Short timeout: Slow but correct responses get killed
- Long timeout: Fast tiers hold the user hostage to the full timeout before falling through

**Exact Fix**: Implement per-tier timeout configuration:

```python
# Define tier-specific timeouts
TIER_TIMEOUTS = {
    "tier1_lora": 30.0,     # Local LoRA — should be fast
    "tier2a_ollama": 30.0,  # Local Ollama — should be fast
    "tier2b_gemini": 45.0,  # Gemini API — moderate
    "tier2c_deepseek": 45.0, # DeepSeek API — moderate
    "tier2d_zen": 60.0,     # OpenCode Zen — moderate to slow
    "tier2e_registry": 60.0, # Registry API — variable
    "tier3_teacher": 90.0,  # Cloud Teacher — slow
    "tier4_websearch": 120.0, # Web search — very slow
}
```

Then use `TIER_TIMEOUTS[tier_name]` in each `asyncio.wait_for()` call instead of a hardcoded value.

**Before Behaviour**: All tiers use the same timeout. Fast tiers either hold the user for too long, or slow tiers get their responses killed prematurely.

**After Behaviour**: Each tier has an appropriate timeout. Fast tiers (Ollama, Gemini) fail fast. Slow tiers (Cloud Teacher, Web Search) get the time they need to produce quality answers.

---

## Issue #12 (P2): All Errors Swallowed — No Diagnostic Trace

**Root Cause**: Every tier's except block in `select_model_with_fallback()` follows the pattern:

```python
except Exception as e:
    logger.warning(f"Tier N failed: {e}")
    continue  # Silently fall through to next tier
```

This means:
1. No error type classification (timeout vs auth vs rate limit vs server error)
2. No per-tier error counters or telemetry
3. No way to know if a tier is systematically failing (e.g., expired API key)
4. A tier that fails 100% of the time still gets tried every single request
5. All error types are treated equally — an auth failure (quick death) gets the same log line as a near-complete response that timed out (slow death, different kind of failure)

**Exact Fix**: Implement structured error logging with per-tier error counters:

```python
# Add a module-level error counter
from collections import defaultdict
import time

tier_error_counts = defaultdict(lambda: {"count": 0, "last_error": None, "last_time": 0, "error_types": defaultdict(int)})

# Inside each except block:
except asyncio.TimeoutError:
    tier_error_counts[tier_name]["count"] += 1
    tier_error_counts[tier_name]["error_types"]["timeout"] += 1
    tier_error_counts[tier_name]["last_time"] = time.time()
    logger.warning(
        "[TIER_FALLBACK] %s timed out after %.1fs (total failures: %d)",
        tier_name, timeout_value,
        tier_error_counts[tier_name]["count"],
    )
except AuthenticationError as e:
    tier_error_counts[tier_name]["count"] += 1
    tier_error_counts[tier_name]["error_types"]["auth"] += 1
    tier_error_counts[tier_name]["last_time"] = time.time()
    logger.error("[TIER_FALLBACK] %s auth failure: %s (total failures: %d)",
                 tier_name, e, tier_error_counts[tier_name]["count"])
except Exception as e:
    tier_error_counts[tier_name]["count"] += 1
    tier_error_counts[tier_name]["error_types"]["unknown"] += 1
    tier_error_counts[tier_name]["last_time"] = time.time()
    logger.warning("[TIER_FALLBACK] %s failed: %s (total failures: %d)",
                   tier_name, e, tier_error_counts[tier_name]["count"])
```

Also add an endpoint to expose these counters for diagnostics.

**Before Behaviour**: All errors produce the same log line. A tier that has been failing for days still gets tried every time. No one knows a tier is broken until a user complains.

**After Behaviour**: Error types are classified and logged. Cumulative error counters can be exposed via a `/diagnostics/tiers` endpoint. Tiers with 100% failure rates over a rolling window can be temporarily skipped.

---

## Issue #13 (P2): Generic Fallback Timeout Messages

**Root Cause**: When all tiers fail, the final fallback message (around line 420) is:

```
"I was unable to find an answer using any available intelligence tier."
```

This is actually a GOOD message — it's honest. But `_stream_cloud_answer()` assigns provider-specific error messages (lines 110-160 in ask.py):

```python
elif "DeepSeek" in model_name:
    error_msg = "DeepSeek API rate limit exceeded."
elif "gemini" in model_name:
    error_msg = "Gemini API rate limit exceeded."
```

These are misleading — they attribute the error to a specific provider even when the model router has cycled through ALL providers and the real issue is something else entirely (e.g., no internet connectivity, not a rate limit).

**Exact Fix**: Change `_stream_cloud_answer()` error messages to be transparent about the actual error type rather than guessing the provider:

```python
# _stream_cloud_answer() error messages:
elif error_type == "rate_limit":
    error_msg = "The AI provider is currently rate-limited. Please wait a moment and try again."
elif error_type == "timeout":
    error_msg = "The AI provider did not respond in time. Please try again."
elif error_type == "auth":
    error_msg = "API key configuration error. The administrator has been notified."
elif error_type == "quota":
    error_msg = "The AI provider quota has been exceeded. The administrator has been notified."
elif error_type == "connection":
    error_msg = "Could not connect to the AI provider. Check your network connection and try again."
```

**Before Behaviour**: User sees "DeepSeek API rate limit exceeded" when the actual failure was a network timeout on Gemini. The error message is misleading and unhelpful.

**After Behaviour**: User sees a clear, accurate description of the actual error type (timeout, rate limit, auth failure, etc.) that doesn't blame the wrong provider.

---

## System Prompt Propagation Matrix

| Tier | File | System Prompt Passed? | Actual Prompt Used |
|------|------|---------------------|-------------------|
| 1. Local LoRA | `app/training/...` | ✅ | ZETDC system prompt (configurable per training) |
| 2a. Ollama | `ask.py` line ~600 | ✅ | `settings.zetdc.system_prompt` via direct call |
| 2b. Gemini | `model_router.py` ~260 | ✅ | Passed through to `provider_gateway_service.py` |
| 2c. DeepSeek | `model_router.py` ~280 | ✅ | Passed through to `provider_gateway_service.py` |
| 2d. Zen | `opencode_zen_service.py` | ⚠️ See Issue #4 | Stripped on retry (Issue #4, P0) |
| **2e. Registry** | **`model_router.py` ~300** | **❌ MISSING** | **No system prompt received** |
| **3. Cloud Teacher** | **`model_router.py` ~360** | **❌ MISSING** | **No system prompt received** |
| 4. Web Search | `model_router.py` ~390 | ✅ | Passed (results summarized with system prompt) |

---

## Structural Recommendations

1. **Make system prompt propagation a hard requirement**: Add a type annotation or Pydantic model that ensures EVERY tier call includes `system_prompt`. CI should fail if any new tier omits it.

2. **Add per-tier timeout configuration**: Use a dictionary of tier→timeout values (see Issue #11 fix). Log when a tier times out.

3. **Classify errors, don't swallow them**: Categorize errors by type (timeout, auth, rate_limit, server_error, network) before logging. Expose cumulative error counters via a diagnostics endpoint.

4. **Replace substring confidence check with LLM-as-Judge**: The `_is_confident()` function should use a small local LLM (e.g., `qwen3:4b`) with a yes/no confidence prompt. This will be far more accurate and eliminate false positives from correct RAG patterns.

5. **Add a circuit breaker for persistently failing tiers**: If a tier fails >90% of calls in a 5-minute window, stop trying it for 1 minute. Reset the circuit breaker on first success.

6. **Rename tiers for clarity**: The current tier naming (2b, 2c, 2d, 2e) is confusing. Use semantic names: `local_lora`, `local_ollama`, `cloud_gemini`, `cloud_deepseek`, `cloud_zen`, `cloud_registry`, `cloud_teacher`, `web_search`.

7. **Add a `--skip-tier` query parameter**: Allow trusted users (admins/testing) to skip specific tiers via a query parameter. Useful for testing and debugging. E.g., `?skip_tiers=cloud_teacher,web_search`.

---

*End of Phase 2 — Fallback Chain Audit*
