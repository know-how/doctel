"""
pgvector_client.py — DocTel pgvector Vector Store Client

Provides async insert and delete operations for the document_chunks table
(pgvector-enabled).  Only active when the DOCINTEL_USE_PGVECTOR feature flag
is enabled; import is safe regardless of the flag value.

Functions:
    insert_chunks(db, document_id, texts, embeddings, metadatas) -> int
    delete_document(db, document_id) -> None
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def insert_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
    texts: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any]],
) -> int:
    """Insert document chunks into the pgvector-enabled ``document_chunks`` table.

    Each chunk is stored with its embedding vector, text content, and
    metadata (filename, chunk_index, source_type, etc.).  Uses a single
    bulk INSERT via raw SQL with ``::vector`` cast for the embedding column.

    Args:
        db: Active async database session.
        document_id: UUID of the parent document row.
        texts: List of chunk text strings (parallel to embeddings/metadatas).
        embeddings: List of raw embedding vectors (list of floats).
        metadatas: List of metadata dicts, each containing at minimum
            ``chunk_index``, ``filename``, ``document_id``, and
            ``source_type``.  May also include ``page_number``,
            ``section_heading``, ``start_sec``, ``end_sec``, ``speaker``.

    Returns:
        Number of rows successfully inserted.
    """
    if not texts or not embeddings or not metadatas:
        logger.warning("[PGVECTOR] insert_chunks called with empty data")
        return 0

    n = min(len(texts), len(embeddings), len(metadatas))
    now = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []

    for i in range(n):
        meta = metadatas[i] if i < len(metadatas) else {}
        chunk_index = meta.get("chunk_index", i)
        chunk_text = texts[i]

        rows.append({
            "id": uuid.uuid4(),
            "document_id": document_id,
            "chunk_index": chunk_index,
            "chunk_size": len(chunk_text),
            "chunk_text": chunk_text,
            "page_number": meta.get("page_number"),
            "section_heading": meta.get("section_heading"),
            "preceding_context": meta.get("preceding_context"),
            "following_context": meta.get("following_context"),
            "embedding_model": meta.get("embedding_model"),
            "embedding_provider": meta.get("embedding_provider"),
            "embedded_at": now,
            "token_count": meta.get("token_count"),
            "quality_score": meta.get("quality_score"),
            "embedding": embeddings[i],
        })

    # Bulk insert using raw SQL with ::vector cast
    stmt = text("""
        INSERT INTO document_chunks (
            id, document_id, chunk_index, chunk_size, chunk_text,
            page_number, section_heading, preceding_context, following_context,
            embedding_model, embedding_provider, embedded_at, token_count,
            quality_score, embedding
        ) VALUES (
            :id, :document_id, :chunk_index, :chunk_size, :chunk_text,
            :page_number, :section_heading, :preceding_context, :following_context,
            :embedding_model, :embedding_provider, :embedded_at, :token_count,
            :quality_score, :embedding::vector
        )
    """)

    try:
        for row in rows:
            db.add(
                # Use the raw connection via execute for the vector cast
                None  # placeholder, we use execute below
            )

        # Execute bulk insert with proper vector casting
        for row in rows:
            params = {k: v for k, v in row.items()}
            # Convert embedding list to a PostgreSQL-compatible vector literal
            params["embedding"] = "[" + ",".join(str(x) for x in row["embedding"]) + "]"
            await db.execute(stmt, params)

        await db.commit()
        logger.info("[PGVECTOR] Inserted %d chunks for document %s", n, document_id)
        return n
    except Exception:
        await db.rollback()
        logger.exception("[PGVECTOR] Bulk insert failed for document %s", document_id)
        raise


async def delete_document(db: AsyncSession, document_id: uuid.UUID) -> None:
    """Hard-delete all chunks belonging to a document.

    Called before re-embedding to clear old chunk rows before inserting
    new embeddings.

    Args:
        db: Active async database session.
        document_id: UUID of the document whose chunks should be removed.
    """
    stmt = text("""DELETE FROM document_chunks WHERE document_id = :document_id""")
    try:
        result = await db.execute(stmt, {"document_id": document_id})
        await db.commit()
        deleted = result.rowcount
        logger.info("[PGVECTOR] Deleted %d chunks for document %s", deleted, document_id)
    except Exception:
        await db.rollback()
        logger.exception("[PGVECTOR] Delete failed for document %s", document_id)
        raise
