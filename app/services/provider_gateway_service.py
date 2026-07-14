"""
provider_gateway_service.py — Single unified provider gateway.

Replaces gemini_service.py, deepseek_service.py, huggingface_service.py,
and opencode_zen_service.py with **one** entry point driven entirely by the
ai_providers database table.

Flow:
    chosen_model → ai_models → provider_id → ai_providers (base_url, api_key_value, vendor)
        → select_adapter(vendor) → generate / generate_stream

VISION 2.0 enhancements:
    - Streaming reasoning content (Pillar 5)
    - InteractionAudit records for every call (Pillar 20)
    - CostRecord entries for cost governance (Pillar 14)
    - ConfidenceScore per response (Pillar 15)
"""

from __future__ import annotations

import logging
import time
from typing import Optional, AsyncGenerator, List

# Import ProviderError for structured error handling
from app.services.openai_compatible_adapter import ProviderError

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class ProviderNotFoundError(RuntimeError):
    """No matching provider record found in ai_providers."""
    pass

class ProviderNotConfiguredError(RuntimeError):
    """Provider exists but api_key_value is empty."""
    pass

class ProviderRequestError(RuntimeError):
    """HTTP-level error from the provider."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════════

async def _resolve_model_provider(db, model_id: str) -> dict:
    """
    model_id → ai_models → provider_id → ai_providers row.
    Returns dict with keys: id, provider_id, name, vendor, base_url, api_key_value, provider_type, models_endpoint, chat_endpoint, messages_endpoint.
    """
    from sqlalchemy import select as sa_sel
    from app.db.config_models import AIModel, AIProvider

    # Find model - use limit(1) to prevent MultipleResultsFound
    result = await db.execute(sa_sel(AIModel).where(AIModel.model_id == model_id).limit(1))
    model = result.scalars().first()
    if not model:
        bare = model_id.split("/")[-1] if "/" in model_id else model_id
        result = await db.execute(sa_sel(AIModel).where(AIModel.model_id.ilike(f"%{bare}%")).limit(1))
        model = result.scalars().first()

    if not model:
        raise ProviderNotFoundError(f"No model '{model_id}' found in ai_models")

    # Find provider - use limit(1) to prevent MultipleResultsFound
    result = await db.execute(sa_sel(AIProvider).where(AIProvider.id == model.provider_id).limit(1))
    provider = result.scalars().first()
    if not provider:
        raise ProviderNotFoundError(f"No provider for model '{model_id}' (provider_id={model.provider_id})")

    return {
        "id": provider.id,
        "provider_id": provider.provider_id,
        "name": provider.name,
        "vendor": provider.vendor,
        "base_url": (provider.base_url or "").strip(),
        "api_key_value": (provider.api_key_value or "").strip(),
        "provider_type": (provider.provider_type or "openai").strip(),
        "models_endpoint": (provider.models_endpoint or "").strip(),
        "chat_endpoint": (provider.chat_endpoint or "").strip(),
        "messages_endpoint": (provider.messages_endpoint or "").strip(),
        "embeddings_endpoint": (provider.embeddings_endpoint or "").strip(),
    }


def _build_chat_url(provider: dict) -> str:
    """Build the chat completions URL from provider metadata."""
    # Prefer explicit chat_endpoint
    if provider["chat_endpoint"]:
        return provider["chat_endpoint"]
    # Fallback: base_url + /chat/completions
    base = provider["base_url"].rstrip("/")
    if base:
        return base + "/chat/completions"
    raise ProviderNotConfiguredError(f"Provider '{provider['name']}' has no base_url or chat_endpoint set")


# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTER SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

_ADAPTER_REGISTRY: dict[str, str] = {
    # Vendor → adapter module name
    "opencode": "openai_compatible",
    "deepseek": "openai_compatible",
    "openai": "openai_compatible",
    "mistral": "openai_compatible",
    "groq": "openai_compatible",
    "together": "openai_compatible",
    "openrouter": "openai_compatible",
    "lmstudio": "openai_compatible",
    "vllm": "openai_compatible",
    "llamacpp": "openai_compatible",
    "ollama": "openai_compatible",
    "huggingface": "openai_compatible",
    "google": "gemini",
    "gemini": "gemini",
    "anthropic": "anthropic",
}


def _select_adapter(vendor: str) -> str:
    """Map ai_providers.vendor to an adapter name."""
    if not vendor:
        return "openai_compatible"
    v = vendor.strip().lower()
    return _ADAPTER_REGISTRY.get(v, "openai_compatible")


def provider_supports_streaming(provider_type: str) -> bool:
    """Determine whether a given provider type supports streaming.

    All providers with a registered streaming adapter support streaming
    responses.  The adapter registry is the single source of truth —
    if a provider's vendor appears in the registry, streaming is available.

    Args:
        provider_type: The provider type/vendor string (e.g. ``"ollama"``,
            ``"gemini"``, ``"opencode"``, ``"anthropic"``).

    Returns:
        ``True`` if the provider has a streaming-capable adapter registered.
    """
    if not provider_type:
        return False
    pt = provider_type.strip().lower()
    return pt in _ADAPTER_REGISTRY


# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN ESTIMATION HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def _estimate_tokens(text: str) -> int:
    """Rough token estimate — ~4 chars per token for most LLMs."""
    if not text:
        return 0
    return max(1, len(text) // 4)


# ═══════════════════════════════════════════════════════════════════════════════
# VISION 2.0 — AUDIT & RECORD HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


async def _record_interaction_audit(
    db,
    *,
    provider_id: str,
    model_id: str,
    vendor: str,
    prompt_text: str,
    system_prompt: str,
    response_text: str,
    reasoning_text: str,
    duration_ms: int,
    user_id: Optional[int] = None,
    session_id: Optional[int] = None,
    message_id: Optional[int] = None,
    department: Optional[str] = None,
    tokens_input: Optional[int] = None,
    tokens_output: Optional[int] = None,
    tokens_total: Optional[int] = None,
    cost: Optional[float] = None,
    retrieval_strategy: Optional[str] = None,
    retrieved_chunks_json: Optional[str] = None,
    error_message: str = "",
) -> int:
    """Create an InteractionAudit record for a completed AI interaction.

    Returns the audit record ID (or 0 on failure).
    """
    try:
        from app.db.enterprise_models import InteractionAudit

        audit = InteractionAudit(
            session_id=session_id,
            message_id=message_id,
            user_id=user_id,
            department=department or "",
            prompt_text=prompt_text,
            system_prompt=system_prompt,
            provider_id=provider_id,
            model_id=model_id,
            vendor=vendor,
            response_text=response_text,
            reasoning_text=reasoning_text,
            duration_ms=duration_ms,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tokens_total=tokens_total,
            cost=cost,
            retrieval_strategy=retrieval_strategy or "vector",
            retrieved_chunks_json=retrieved_chunks_json or "[]",
            error_message=error_message,
        )
        db.add(audit)
        await db.flush()
        return audit.id  # type: ignore[return-value]
    except Exception as exc:
        logger.warning("Failed to record InteractionAudit: %s", exc, exc_info=True)
        return 0


async def _record_cost(
    db,
    *,
    source_type: str,
    source_id: Optional[int],
    provider_id: str,
    model_id: str,
    user_id: Optional[int] = None,
    project_id: Optional[int] = None,
    department: Optional[str] = None,
    tokens_input: int = 0,
    tokens_output: int = 0,
    tokens_total: int = 0,
    total_cost: float = 0.0,
    duration_ms: Optional[int] = None,
) -> int:
    """Create a CostRecord entry for cost governance.

    Returns the record ID (or 0 on failure).
    """
    try:
        from app.db.enterprise_models import CostRecord

        record = CostRecord(
            source_type=source_type,
            source_id=source_id,
            provider_id=provider_id,
            model_id=model_id,
            user_id=user_id,
            project_id=project_id,
            department=department or "",
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tokens_total=tokens_total,
            total_cost=total_cost,
            duration_ms=duration_ms,
        )
        db.add(record)
        await db.flush()
        return record.id  # type: ignore[return-value]
    except Exception as exc:
        logger.warning("Failed to record CostRecord: %s", exc, exc_info=True)
        return 0


async def _record_confidence_score(
    db,
    *,
    source_type: str,
    source_id: int,
    overall_score: float = 0.0,
    citation_coverage: Optional[float] = None,
    retrieval_relevance: Optional[float] = None,
    model_confidence: Optional[float] = None,
    source_agreement: Optional[float] = None,
    reasoning_coherence: Optional[float] = None,
) -> int:
    """Create a ConfidenceScore record for trust scoring.

    Returns the record ID (or 0 on failure).
    """
    try:
        from app.db.enterprise_models import ConfidenceScore

        score = ConfidenceScore(
            source_type=source_type,
            source_id=source_id,
            overall_score=overall_score,
            citation_coverage=citation_coverage,
            retrieval_relevance=retrieval_relevance,
            model_confidence=model_confidence,
            source_agreement=source_agreement,
            reasoning_coherence=reasoning_coherence,
            limited_evidence=overall_score < 0.4,
            contradictory_sources=(source_agreement is not None and source_agreement < 0.3),
            low_model_confidence=(model_confidence is not None and model_confidence < 0.3),
        )
        db.add(score)
        await db.flush()
        return score.id  # type: ignore[return-value]
    except Exception as exc:
        logger.warning("Failed to record ConfidenceScore: %s", exc, exc_info=True)
        return 0


async def _post_generate_audit(
    db,
    *,
    provider: dict,
    model_id: str,
    prompt: str,
    system: Optional[str],
    response_text: str,
    reasoning_text: str,
    duration_ms: int,
    tokens_input: int = 0,
    tokens_output: int = 0,
    user_id: Optional[int] = None,
    session_id: Optional[int] = None,
    message_id: Optional[int] = None,
    department: Optional[str] = None,
    project_id: Optional[int] = None,
    source_type: str = "message",
    retrieval_strategy: Optional[str] = None,
    retrieved_chunks_json: Optional[str] = None,
    error_message: str = "",
) -> None:
    """Record InteractionAudit + CostRecord + ConfidenceScore in one call.

    Shared by both ``generate()`` and ``generate_stream()`` to avoid
    duplicating the audit logic.
    """
    audit_id = await _record_interaction_audit(
        db,
        provider_id=provider["provider_id"],
        model_id=model_id,
        vendor=provider["vendor"],
        prompt_text=prompt,
        system_prompt=system or "",
        response_text=response_text,
        reasoning_text=reasoning_text,
        duration_ms=duration_ms,
        user_id=user_id,
        session_id=session_id,
        message_id=message_id,
        department=department,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        tokens_total=tokens_input + tokens_output,
        retrieval_strategy=retrieval_strategy,
        retrieved_chunks_json=retrieved_chunks_json,
        error_message=error_message,
    )

    if not error_message:
        await _record_cost(
            db,
            source_type=source_type,
            source_id=audit_id or None,
            provider_id=provider["provider_id"],
            model_id=model_id,
            user_id=user_id,
            project_id=project_id,
            department=department,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tokens_total=tokens_input + tokens_output,
            duration_ms=duration_ms,
        )

        if audit_id:
            await _record_confidence_score(
                db,
                source_type=source_type,
                source_id=audit_id,
                overall_score=0.7,  # Default — enhance later with actual model confidence
            )

    await db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API: non-streaming
# ═══════════════════════════════════════════════════════════════════════════════

async def generate(
    db,
    prompt: str,
    model_id: str = "",
    system: Optional[str] = None,
    # VISION 2.0 — tracking parameters (all optional, backward compatible)
    user_id: Optional[int] = None,
    session_id: Optional[int] = None,
    department: Optional[str] = None,
    message_id: Optional[int] = None,
    project_id: Optional[int] = None,
    source_type: str = "message",
    retrieval_strategy: Optional[str] = None,
    retrieved_chunks_json: Optional[str] = None,
) -> str:
    """
    Single entry point for all provider text generation.
    All parameters come from the database — no env vars, no hardcoded IDs.

    VISION 2.0: When ``user_id`` (or other tracking params) is supplied,
    an InteractionAudit, CostRecord, and ConfidenceScore are recorded
    automatically.
    """
    _t_start = time.monotonic()
    provider = await _resolve_model_provider(db, model_id)
    if not provider["api_key_value"]:
        # Last resort: raw SQL bypass (ORM may return stale cached value)
        from sqlalchemy import text as sa_text
        raw = await db.execute(sa_text("SELECT api_key_value FROM ai_providers WHERE id = :pid"), {"pid": provider["id"]})
        row = raw.fetchone()
        if row and row[0]:
            provider["api_key_value"] = str(row[0]).strip()
        if not provider["api_key_value"]:
            # Allow empty API key for local/offline providers (Ollama, localhost, etc.)
            vendor_lower = (provider.get("vendor") or "").strip().lower()
            base_url_lower = (provider.get("base_url") or "").strip().lower()
            is_local = (
                vendor_lower == "ollama"
                or base_url_lower.startswith("http://localhost")
                or base_url_lower.startswith("http://127.0.0.1")
                or base_url_lower.startswith("http://0.0.0.0")
            )
            if not is_local:
                raise ProviderNotConfiguredError(f"Provider '{provider['name']}' has no API key. Set it in Admin > Providers.")
            logger.info(
                "Provider '%s' (vendor=%s) has no API key — running without auth (local provider)",
                provider["name"], provider.get("vendor"),
            )

    adapter = _select_adapter(provider["vendor"])
    url = _build_chat_url(provider)
    error_message = ""

    try:
        if adapter == "openai_compatible":
            from app.services.openai_compatible_adapter import chat_completion
            response_text = await chat_completion(
                url=url,
                api_key=provider["api_key_value"],
                model=model_id,
                prompt=prompt,
                system=system,
            )
        elif adapter == "gemini":
            from app.services.gemini_adapter import chat_completion as gemini_chat
            response_text = await gemini_chat(
                api_key=provider["api_key_value"],
                model=model_id,
                prompt=prompt,
                system=system,
            )
        elif adapter == "anthropic":
            from app.services.anthropic_adapter import chat_completion as anthropic_chat
            response_text = await anthropic_chat(
                url=url,
                api_key=provider["api_key_value"],
                model=model_id,
                prompt=prompt,
                system=system,
            )
        else:
            raise ProviderNotFoundError(f"Unknown adapter '{adapter}' for vendor '{provider['vendor']}'")

        # ── Success: record audit, cost, and confidence ──────────────
        duration_ms = int((time.monotonic() - _t_start) * 1000)
        tokens_input = _estimate_tokens(prompt)
        tokens_output = _estimate_tokens(response_text)

        if user_id is not None:
            await _post_generate_audit(
                db,
                provider=provider,
                model_id=model_id,
                prompt=prompt,
                system=system,
                response_text=response_text,
                reasoning_text="",
                duration_ms=duration_ms,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                user_id=user_id,
                session_id=session_id,
                message_id=message_id,
                department=department,
                project_id=project_id,
                source_type=source_type,
                retrieval_strategy=retrieval_strategy,
                retrieved_chunks_json=retrieved_chunks_json,
                error_message=error_message,
            )

        return response_text

    except ProviderError as pe:
        # Re-raise ProviderError unchanged - it has structured error info
        error_message = str(pe)
        raise
    except Exception as exc:
        error_message = str(exc) or str(type(exc).__name__)
        # Log provider details for debugging
        logger.error(
            "[PROVIDER GATEWAY] Provider '%s' (vendor=%s) error: %s",
            provider.get("name", "unknown"),
            provider.get("vendor", "unknown"),
            error_message,
            exc_info=True
        )
        # Attempt to record the failure, but don't let audit failure mask the original
        if user_id is not None:
            try:
                duration_ms = int((time.monotonic() - _t_start) * 1000)
                await _post_generate_audit(
                    db,
                    provider=provider,
                    model_id=model_id,
                    prompt=prompt,
                    system=system,
                    response_text="",
                    reasoning_text="",
                    duration_ms=duration_ms,
                    user_id=user_id,
                    session_id=session_id,
                    message_id=message_id,
                    department=department,
                    source_type=source_type,
                    retrieval_strategy=retrieval_strategy,
                    retrieved_chunks_json=retrieved_chunks_json,
                    error_message=error_message,
                )
            except Exception as audit_exc:
                logger.warning("Audit recording also failed: %s", audit_exc)
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API: streaming
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_stream(
    db,
    prompt: str,
    model_id: str = "",
    system: Optional[str] = None,
    # VISION 2.0 — tracking parameters (all optional, backward compatible)
    user_id: Optional[int] = None,
    session_id: Optional[int] = None,
    department: Optional[str] = None,
    message_id: Optional[int] = None,
    project_id: Optional[int] = None,
    source_type: str = "message",
    retrieval_strategy: Optional[str] = None,
    retrieved_chunks_json: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """
    Single entry point for all provider streaming generation.
    Yields dicts: {"type": "content", "content": str} or {"type": "reasoning", "content": str}.

    VISION 2.0: When ``user_id`` is supplied, an InteractionAudit, CostRecord,
    and ConfidenceScore are recorded automatically after streaming completes.
    """
    _t_start = time.monotonic()
    provider = await _resolve_model_provider(db, model_id)
    if not provider["api_key_value"]:
        from sqlalchemy import text as sa_text
        raw = await db.execute(sa_text("SELECT api_key_value FROM ai_providers WHERE id = :pid"), {"pid": provider["id"]})
        row = raw.fetchone()
        if row and row[0]:
            provider["api_key_value"] = str(row[0]).strip()
        if not provider["api_key_value"]:
            # Allow empty API key for local/offline providers (Ollama, localhost, etc.)
            vendor_lower = (provider.get("vendor") or "").strip().lower()
            base_url_lower = (provider.get("base_url") or "").strip().lower()
            is_local = (
                vendor_lower == "ollama"
                or base_url_lower.startswith("http://localhost")
                or base_url_lower.startswith("http://127.0.0.1")
                or base_url_lower.startswith("http://0.0.0.0")
            )
            if not is_local:
                raise ProviderNotConfiguredError(f"Provider '{provider['name']}' has no API key. Set it in Admin > Providers.")
            logger.info(
                "Provider '%s' (vendor=%s) has no API key — running without auth (local provider)",
                provider["name"], provider.get("vendor"),
            )

    adapter = _select_adapter(provider["vendor"])
    url = _build_chat_url(provider)

    # ── Accumulator variables ─────────────────────────────────────────
    collected_content: List[str] = []
    collected_reasoning: List[str] = []
    error_message = ""

    async def _stream_inner() -> AsyncGenerator[dict, None]:
        """Yields raw chunks from the underlying adapter."""
        if adapter == "openai_compatible":
            from app.services.openai_compatible_adapter import chat_completion_stream
            async for chunk in chat_completion_stream(
                url=url,
                api_key=provider["api_key_value"],
                model=model_id,
                prompt=prompt,
                system=system,
            ):
                yield chunk
        elif adapter == "gemini":
            from app.services.gemini_adapter import chat_completion_stream as gemini_stream
            async for text in gemini_stream(
                api_key=provider["api_key_value"],
                model=model_id,
                prompt=prompt,
                system=system,
            ):
                yield {"type": "content", "content": text}
        elif adapter == "anthropic":
            from app.services.anthropic_adapter import chat_completion_stream as anthropic_stream
            async for text in anthropic_stream(
                url=url,
                api_key=provider["api_key_value"],
                model=model_id,
                prompt=prompt,
                system=system,
            ):
                yield {"type": "content", "content": text}
        else:
            raise ProviderNotFoundError(f"Unknown adapter '{adapter}' for vendor '{provider['vendor']}'")

    # ── Stream outer: consume _stream_inner, accumulate, yield ──
    try:
        async for chunk in _stream_inner():
            if chunk["type"] == "content":
                collected_content.append(chunk["content"])
            elif chunk["type"] == "reasoning":
                collected_reasoning.append(chunk["content"])
            yield chunk
    except ProviderError as pe:
        # Re-raise ProviderError unchanged - it has structured error info
        error_message = str(pe)
        raise
    except Exception as exc:
        error_message = str(exc) or str(type(exc).__name__)
        # Log provider details for debugging
        logger.error(
            "[PROVIDER GATEWAY] Provider '%s' (vendor=%s) error: %s",
            provider.get("name", "unknown"),
            provider.get("vendor", "unknown"),
            error_message,
            exc_info=True
        )
        raise
    finally:
        # ── Record audit, cost, and confidence after streaming completes ──
        duration_ms = int((time.monotonic() - _t_start) * 1000)
        response_text = "".join(collected_content)
        reasoning_text = "".join(collected_reasoning)
        tokens_input = _estimate_tokens(prompt)
        tokens_output = _estimate_tokens(response_text + reasoning_text)

        if user_id is not None:
            try:
                await _post_generate_audit(
                    db,
                    provider=provider,
                    model_id=model_id,
                    prompt=prompt,
                    system=system,
                    response_text=response_text,
                    reasoning_text=reasoning_text,
                    duration_ms=duration_ms,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    user_id=user_id,
                    session_id=session_id,
                    message_id=message_id,
                    department=department,
                    project_id=project_id,
                    source_type=source_type,
                    retrieval_strategy=retrieval_strategy,
                    retrieved_chunks_json=retrieved_chunks_json,
                    error_message=error_message,
                )
            except Exception as audit_exc:
                logger.warning("Streaming audit recording also failed: %s", audit_exc)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: embedding URL
# ═══════════════════════════════════════════════════════════════════════════════

def _build_embedding_url(provider: dict) -> str:
    """Build the embeddings URL from provider metadata."""
    if provider["embeddings_endpoint"]:
        return provider["embeddings_endpoint"]
    base = provider["base_url"].rstrip("/")
    if base:
        return base + "/embeddings"
    raise ProviderNotConfiguredError(
        f"Provider '{provider['name']}' has no base_url or embeddings_endpoint set"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API: embedding
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_embedding(
    db,
    text: str,
    model_id: str = "",
) -> list[float]:
    """
    Generate an embedding vector using the provider configured for the given model.

    Resolves the model to a provider via ``_resolve_model_provider()``, selects the
    appropriate adapter, and calls its ``embed_text()`` method.

    Args:
        db: Database session.
        text: The input text to embed.
        model_id: The model ID to use for embedding.  If empty, the TaskMapping
            for ``task_type='embedding'`` is consulted as a fallback.

    Returns:
        A list of floats representing the embedding vector.
    """
    if not model_id:
        # Fall back to TaskMapping for task_type='embedding'
        from sqlalchemy import select as sa_sel
        from app.db.config_models import TaskMapping

        tm_result = await db.execute(
            sa_sel(TaskMapping).where(TaskMapping.task_type == "embedding")
        )
        tm = tm_result.scalar_one_or_none()
        if tm and tm.model_id:
            model_id = tm.model_id
        else:
            raise ProviderNotFoundError(
                "No model_id given and no TaskMapping found for task_type='embedding'"
            )

    provider = await _resolve_model_provider(db, model_id)
    if not provider["api_key_value"]:
        from sqlalchemy import text as sa_text
        raw = await db.execute(
            sa_text("SELECT api_key_value FROM ai_providers WHERE id = :pid"),
            {"pid": provider["id"]},
        )
        row = raw.fetchone()
        if row and row[0]:
            provider["api_key_value"] = str(row[0]).strip()
        if not provider["api_key_value"]:
            # Allow empty API key for local/offline providers (Ollama, localhost, etc.)
            vendor_lower = (provider.get("vendor") or "").strip().lower()
            base_url_lower = (provider.get("base_url") or "").strip().lower()
            is_local = (
                vendor_lower == "ollama"
                or base_url_lower.startswith("http://localhost")
                or base_url_lower.startswith("http://127.0.0.1")
                or base_url_lower.startswith("http://0.0.0.0")
            )
            if not is_local:
                raise ProviderNotConfiguredError(
                    f"Provider '{provider['name']}' has no API key. Set it in Admin > Providers."
                )
            logger.info(
                "Provider '%s' (vendor=%s) has no API key — running without auth (local provider)",
                provider["name"], provider.get("vendor"),
            )

    adapter = _select_adapter(provider["vendor"])
    url = _build_embedding_url(provider)

    if adapter == "openai_compatible":
        from app.services.openai_compatible_adapter import embed_text as adapter_embed
        return await adapter_embed(
            url=url,
            api_key=provider["api_key_value"],
            model=model_id,
            input_text=text,
        )
    elif adapter == "gemini":
        from app.services.gemini_adapter import embed_text as adapter_embed
        return await adapter_embed(
            api_key=provider["api_key_value"],
            model=model_id,
            input_text=text,
        )
    elif adapter == "anthropic":
        from app.services.anthropic_adapter import embed_text as adapter_embed
        return await adapter_embed(
            api_key=provider["api_key_value"],
            model=model_id,
            input_text=text,
        )
    else:
        raise ProviderNotFoundError(
            f"Unknown adapter '{adapter}' for vendor '{provider['vendor']}'"
        )
