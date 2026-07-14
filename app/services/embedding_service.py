"""
embedding_service.py — DocTel Embedding Governance Service

Provides a unified interface for:
- Resolving the configured embedding model via TaskMapping
- Generating embeddings through the provider gateway
- Persisting embedding metadata (provider, model, dimensions)
- Managing document embedding lifecycle fields
- Detecting when re-embedding is required

This service is used by the ingestion pipeline and the RAG retrieval layer
to ensure consistent embedding governance across the application.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select as sa_select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Document,
    Chunk,
    Embedding,
    EMBEDDING_VERSION,
    DOC_STATUS_EMBEDDED,
    DOC_STATUS_RE_EMBED_REQUIRED,
)
from app.db.config_models import TaskMapping

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Model Resolution
# ═══════════════════════════════════════════════════════════════════════════════

async def resolve_embedding_model(db: AsyncSession) -> Optional[dict[str, Any]]:
    """
    Resolve the embedding model from TaskMapping for task_type='embedding'.

    Returns a dict with ``provider_name``, ``model_id``, ``vendor``, and
    ``provider_id`` keys, or ``None`` if no TaskMapping exists.

    The result can be passed to ``generate_embedding()`` and
    ``store_embedding_records()`` to ensure consistent metadata.
    """
    result = await db.execute(
        sa_select(TaskMapping).where(TaskMapping.task_type == "embedding")
    )
    tm = result.scalar_one_or_none()
    if not tm or not tm.model_id:
        logger.warning("No TaskMapping found for task_type='embedding' — embedding not configured")
        return None

    model_id = tm.model_id

    # Resolve the provider via the gateway's internal resolution chain
    from app.services.provider_gateway_service import _resolve_model_provider

    try:
        provider = await _resolve_model_provider(db, model_id)
        return {
            "provider_name": provider.get("name", ""),
            "model_id": model_id,
            "vendor": provider.get("vendor", ""),
            "provider_id": provider.get("id"),
        }
    except Exception as exc:
        logger.warning("Could not resolve provider for embedding model '%s': %s", model_id, exc)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Embedding Generation
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_embedding(db: AsyncSession, text: str, model_id: str = "") -> list[float]:
    """
    Generate an embedding vector via the provider gateway.

    Args:
        db: Database session (forwarded to gateway for audit logging).
        text: The input text to embed.
        model_id: Optional model ID.  If empty, the provider gateway falls
            back to the TaskMapping for ``task_type='embedding'``.

    Returns:
        A list of floats representing the embedding vector.
    """
    from app.services.provider_gateway_service import generate_embedding as gateway_call

    return await gateway_call(db, text, model_id)


async def generate_embeddings_batch(
    db: AsyncSession,
    texts: list[str],
    model_id: str = "",
    concurrency: int = 2,
) -> list[list[float]]:
    """
    Generate embeddings for *multiple* texts with controlled concurrency.

    Args:
        db: Database session.
        texts: List of text strings to embed.
        model_id: Optional model ID (see :func:`generate_embedding`).
        concurrency: Maximum concurrent embedding API calls (default 2).

    Returns:
        List of embedding vectors in the same order as *texts*.
    """
    sem = asyncio.Semaphore(concurrency)

    async def _embed_one(idx: int, chunk_text: str) -> tuple[int, list[float]]:
        async with sem:
            vec = await generate_embedding(db, chunk_text, model_id)
            return idx, vec

    tasks = [_embed_one(i, t) for i, t in enumerate(texts)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect and validate results (results are tuple[int, list[float]])
    items: list[tuple[int, list[float]]] = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("Batch embedding failed: %s", r)
            raise r
        items.append(r)  # r is (index, vector)

    # Sort by index to restore original order
    items.sort(key=lambda pair: pair[0])
    return [vec for _, vec in items]


# ═══════════════════════════════════════════════════════════════════════════════
# Persistence — Embedding & Chunk Records
# ═══════════════════════════════════════════════════════════════════════════════

async def store_embedding_records(
    db: AsyncSession,
    doc_id: int,
    project_id: int,
    chroma_ids: list[str],
    texts: list[str],
    metadatas: list[dict[str, Any]],
    *,
    provider: str = "",
    model: str = "",
    dimensions: int = 0,
) -> None:
    """
    Create ``Embedding`` and ``Chunk`` database rows for a set of vectors.

    This is the governance-aware replacement for the inline loop that
    currently lives in ``ingestion_service.py``.  It records the provider,
    model, and dimension metadata on each ``Embedding`` row.

    Args:
        db: Database session.
        doc_id: Document primary key.
        project_id: Project primary key.
        chroma_ids: ChromaDB vector IDs (one per chunk).
        texts: Chunk text content (one per chunk).
        metadatas: Metadata dicts (one per chunk, must include ``chunk_index``).
        provider: Provider name to record on the Embedding rows.
        model: Model ID to record on the Embedding rows.
        dimensions: Vector dimension count.
    """
    if not (len(chroma_ids) == len(texts) == len(metadatas)):
        raise ValueError(
            f"store_embedding_records: length mismatch "
            f"chroma_ids={len(chroma_ids)} texts={len(texts)} metadatas={len(metadatas)}"
        )

    for i, chroma_id in enumerate(chroma_ids):
        embedding = Embedding(
            vector_ref=chroma_id,
            model_name=model or None,
            provider=provider or None,
            dimensions=dimensions or None,
        )
        db.add(embedding)
        await db.flush()

        chunk_index = int(metadatas[i].get("chunk_index", i))
        chunk = Chunk(
            document_id=doc_id,
            project_id=project_id,
            chunk_index=chunk_index,
            text=texts[i],
            citation_ref=f"Chunk {chunk_index}",
            embedding_id=embedding.id,
        )
        db.add(chunk)

    await db.commit()
    logger.info(
        "Stored %d Embedding+Chunk records for document %s (provider=%s model=%s dims=%s)",
        len(chroma_ids),
        doc_id,
        provider or "?",
        model or "?",
        dimensions or "?",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Document Embedding Status
# ═══════════════════════════════════════════════════════════════════════════════

async def update_document_embedding_fields(
    db: AsyncSession,
    doc_id: int,
    provider: str = "",
    model: str = "",
) -> None:
    """
    Update a document's embedding governance fields after successful embedding.

    Sets ``embedding_provider``, ``embedding_model``, ``embedded_at``, and
    ``embedding_version``.  Uses :py:data:`EMBEDDING_VERSION` from the model
    definition as the current version tag.
    """
    now = datetime.now(timezone.utc)
    await db.execute(
        sa_update(Document)
        .where(Document.id == doc_id)
        .values(
            embedding_provider=provider or None,
            embedding_model=model or None,
            embedded_at=now,
            embedding_version=EMBEDDING_VERSION,
        )
    )
    await db.commit()
    logger.info("Updated embedding fields for document %s (v%s)", doc_id, EMBEDDING_VERSION)


async def get_document_embedding_status(db: AsyncSession, doc_id: int) -> dict[str, Any]:
    """
    Return the current embedding state of a document.

    Returns a dict with keys:
    - ``doc_id``
    - ``status`` (document status from DB)
    - ``embedding_provider``
    - ``embedding_model``
    - ``embedded_at``
    - ``embedding_version``
    - ``needs_reembed`` (bool — heuristic, see :func:`check_reembed_required`)
    """
    result = await db.execute(sa_select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        return {"doc_id": doc_id, "error": "Document not found"}

    needs = await check_reembed_required(db, doc_id)

    return {
        "doc_id": doc_id,
        "status": doc.status or "unknown",
        "embedding_provider": doc.embedding_provider,
        "embedding_model": doc.embedding_model,
        "embedded_at": doc.embedded_at.isoformat() if doc.embedded_at else None,
        "embedding_version": doc.embedding_version,
        "needs_reembed": needs,
    }


async def check_reembed_required(db: AsyncSession, doc_id: int) -> bool:
    """
    Determine whether a document needs re-embedding.

    Returns ``True`` if **any** of the following are true:

    * The document has no ``embedded_at`` timestamp (never embedded).
    * The document's ``embedding_version`` differs from the current
      :py:data:`EMBEDDING_VERSION` (model or provider was changed).
    * The document's ``embedding_provider`` or ``embedding_model`` does
      not match the currently configured ``TaskMapping`` for 'embedding'.

    Args:
        db: Database session.
        doc_id: Document primary key.

    Returns:
        ``True`` if re-embedding is recommended.
    """
    result = await db.execute(sa_select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        return False

    # Never embedded → needs embedding
    if doc.embedded_at is None:
        return True

    # Version mismatch → model/provider changed
    if doc.embedding_version != EMBEDDING_VERSION:
        return True

    # Check if the configured model differs from what was used
    tm_config = await resolve_embedding_model(db)
    if tm_config:
        configured_model = tm_config["model_id"]
        configured_provider = tm_config["provider_name"]
        if doc.embedding_model != configured_model:
            return True
        if doc.embedding_provider != configured_provider:
            return True

    return False
