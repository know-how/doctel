"""
reembedding_service.py — DocTel Re-embedding Engine

Provides governance-aware re-embedding for documents whose embedding model
or provider has changed.  Supports single-document, bulk-mismatch, and
force-re-embed-all workflows.

Every operation:
1. Resolves the current embedding model from TaskMapping
2. Generates fresh embeddings via the provider gateway
3. Replaces ChromaDB entries atomically per document
4. Replaces Embedding + Chunk DB records with governance metadata
5. Updates Document embedding fields (provider, model, version, timestamp)

Usage:
    from app.services.reembedding_service import reembed_document
    result = await reembed_document(db, doc_id=42)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select as sa_select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Document,
    Chunk,
    Embedding,
    EMBEDDING_VERSION,
)
from app.services.embedding_service import (
    generate_embedding,
    generate_embeddings_batch,
    resolve_embedding_model,
    store_embedding_records,
    update_document_embedding_fields,
)
from app.utils.chroma_client import chroma

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════

async def _fetch_doc_and_chunks(
    db: AsyncSession, doc_id: int,
) -> tuple[Document | None, list[Chunk]]:
    """Return ``(doc, chunks)`` — either may be empty."""
    result = await db.execute(sa_select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        return None, []

    result = await db.execute(
        sa_select(Chunk)
        .where(Chunk.document_id == doc_id)
        .order_by(Chunk.chunk_index)
    )
    chunks = list(result.scalars().all())
    return doc, chunks


async def _delete_old_records(db: AsyncSession, doc_id: int) -> None:
    """Remove old Embedding + Chunk DB rows for *doc_id*."""
    # Collect embedding_ids referenced by chunks before deleting them
    rows = (
        await db.execute(
            sa_select(Chunk.embedding_id).where(Chunk.document_id == doc_id)
        )
    ).all()
    embed_ids = [r.embedding_id for r in rows if r.embedding_id is not None]

    await db.execute(sa_delete(Chunk).where(Chunk.document_id == doc_id))
    if embed_ids:
        await db.execute(sa_delete(Embedding).where(Embedding.id.in_(embed_ids)))
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

async def reembed_document(
    db: AsyncSession,
    doc_id: int,
    *,
    concurrency: int = 2,
) -> dict[str, Any]:
    """
    Re-embed a single document using the current TaskMapping model.

    Steps (all within a single logical operation):
        1. Resolve the embedding model from TaskMapping.
        2. Fetch the document and its chunks.
        3. Generate new embeddings for every chunk.
        4. Delete old ChromaDB entries for this document.
        5. Upsert new ChromaDB entries.
        6. Replace Embedding + Chunk DB rows with governance metadata.
        7. Update Document embedding governance fields.

    Args:
        db: Active database session.
        doc_id: Document primary key.
        concurrency: Max concurrent embedding API calls (default 2).

    Returns:
        A dict with keys ``success``, ``doc_id``, ``chunks_reembedded``,
        ``provider``, ``model``, and optionally ``error``.
    """
    doc, chunks = await _fetch_doc_and_chunks(db, doc_id)
    if doc is None:
        return {"success": False, "error": "Document not found"}

    # ── 1. Resolve current embedding model ────────────────────────────────
    tm_config = await resolve_embedding_model(db)
    if not tm_config:
        return {"success": False, "error": "No embedding model configured in TaskMapping"}
    provider = tm_config["provider_name"]
    model_id = tm_config["model_id"]

    if not chunks:
        # No chunks to embed — this is a failure, not a success
        logger.error(f"[REEMBED] Document {doc_id} has no chunks in the database. Cannot re-embed.")
        return {
            "success": False,
            "error": f"Document has no chunks. Original ingestion may have failed or produced no extractable text. Check document status and re-upload if needed.",
            "doc_id": doc_id,
            "chunks_reembedded": 0,
            "provider": provider,
            "model": model_id,
        }

    # ── 2. Collect texts ──────────────────────────────────────────────────
    texts = [c.text for c in chunks]

    # ── 3. Generate new embeddings ────────────────────────────────────────
    embeddings = await generate_embeddings_batch(
        db, texts, model_id=model_id, concurrency=concurrency,
    )

    if not embeddings or len(embeddings) != len(texts):
        return {
            "success": False,
            "error": f"Embedding generation returned {len(embeddings)} vectors for {len(texts)} chunks",
        }

    # ── 4. Prepare Chroma data ────────────────────────────────────────────
    new_ids = [f"{doc_id}_chunk_{c.chunk_index}" for c in chunks]
    metadatas: list[dict[str, Any]] = [
        {
            "document_id": doc_id,
            "project_id": doc.project_id,
            "chunk_index": c.chunk_index,
            "filename": doc.filename,
            "source_type": doc.mime_type or "document",
        }
        for c in chunks
    ]

    # ── 5. Delete old Chroma entries for this document ────────────────────
    try:
        chroma.delete_where(str(doc.project_id), {"document_id": doc_id})
    except Exception as exc:
        logger.warning("Chroma delete_where for doc %s: %s", doc_id, exc)

    # ── 6. Upsert new Chroma entries ──────────────────────────────────────
    chroma.upsert(str(doc.project_id), new_ids, texts, embeddings, metadatas)

    # ── 7. Replace DB records ─────────────────────────────────────────────
    await _delete_old_records(db, doc_id)

    dimensions = len(embeddings[0]) if embeddings else 0
    await store_embedding_records(
        db, doc_id, doc.project_id, new_ids, texts, metadatas,
        provider=provider, model=model_id, dimensions=dimensions,
    )

    # ── 8. Update Document governance fields ──────────────────────────────
    await update_document_embedding_fields(db, doc_id, provider=provider, model=model_id)

    logger.info(
        "Re-embedded doc %s (%d chunks) with %s/%s (dims=%d)",
        doc_id, len(chunks), provider, model_id, dimensions,
    )

    return {
        "success": True,
        "doc_id": doc_id,
        "chunks_reembedded": len(chunks),
        "provider": provider,
        "model": model_id,
        "dimensions": dimensions,
    }


async def reembed_mismatched_documents(db: AsyncSession) -> dict[str, Any]:
    """
    Re-embed every document whose stored embedding provider/model differs
    from the current TaskMapping, or that has never been embedded.

    Returns:
        A summary dict with ``success``, ``reembedded`` (list of doc IDs),
        ``errors`` (list of error dicts), and ``total`` (scanned count).
    """
    tm_config = await resolve_embedding_model(db)
    if not tm_config:
        return {"success": False, "error": "No embedding model configured in TaskMapping"}
    current_provider = tm_config["provider_name"]
    current_model = tm_config["model_id"]

    result = await db.execute(
        sa_select(Document).where(
            (Document.embedding_provider != current_provider)
            | (Document.embedding_model != current_model)
            | (Document.embedding_version != EMBEDDING_VERSION)
            | (Document.embedded_at.is_(None))
        )
    )
    docs = list(result.scalars().all())

    if not docs:
        return {"success": True, "reembedded": [], "total": 0}

    logger.info("Re-embedding %d mismatched documents", len(docs))

    reembedded: list[int] = []
    errors: list[dict] = []

    for doc in docs:
        try:
            r = await reembed_document(db, doc.id)
            if r["success"]:
                reembedded.append(doc.id)
            else:
                errors.append({"doc_id": doc.id, "error": r.get("error")})
        except Exception as exc:
            logger.exception("Re-embed failed for doc %s", doc.id)
            errors.append({"doc_id": doc.id, "error": str(exc)})

    return {
        "success": len(errors) == 0,
        "reembedded": reembedded,
        "errors": errors,
        "total": len(docs),
    }


async def reembed_all_documents(db: AsyncSession) -> dict[str, Any]:
    """
    Force re-embedding of **every** document in the database, regardless
    of current embedding state.

    Returns:
        Same shape as :func:`reembed_mismatched_documents`.
    """
    result = await db.execute(sa_select(Document))
    docs = list(result.scalars().all())

    if not docs:
        return {"success": True, "reembedded": [], "total": 0}

    logger.info("Force re-embedding all %d documents", len(docs))

    reembedded: list[int] = []
    errors: list[dict] = []

    for doc in docs:
        try:
            r = await reembed_document(db, doc.id)
            if r["success"]:
                reembedded.append(doc.id)
            else:
                errors.append({"doc_id": doc.id, "error": r.get("error")})
        except Exception as exc:
            logger.exception("Re-embed failed for doc %s", doc.id)
            errors.append({"doc_id": doc.id, "error": str(exc)})

    return {
        "success": len(errors) == 0,
        "reembedded": reembedded,
        "errors": errors,
        "total": len(docs),
    }
