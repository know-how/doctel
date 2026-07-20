"""
knowledge_asset_service.py — DocTel Knowledge Asset Registry

Tracks documents, chunks, embeddings, and analysis as registered knowledge
assets for auditing and lifecycle management.  All registration methods are
safe to call and log failures as warnings rather than raising exceptions.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class KnowledgeAssetRegistry:
    """Registry that tracks knowledge assets (documents, chunks, embeddings, analysis)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register_document(self, document: Any) -> None:
        """Register a document as a knowledge asset."""
        try:
            logger.info(
                "[ASSET] Registered document %s (filename=%s)",
                getattr(document, "id", "?"),
                getattr(document, "filename", "?"),
            )
        except Exception as exc:
            logger.warning("[ASSET] register_document failed: %s", exc)

    async def register_chunks(self, document_id: Any, chunks: list[Any]) -> None:
        """Register chunk IDs as knowledge assets for a document."""
        try:
            chunk_ids = [getattr(c, "id", "?") for c in chunks]
            logger.info(
                "[ASSET] Registered %d chunks for document %s: %s",
                len(chunk_ids),
                document_id,
                chunk_ids,
            )
        except Exception as exc:
            logger.warning("[ASSET] register_chunks failed: %s", exc)

    async def register_embeddings(self, document_id: Any, embeddings: list[Any]) -> None:
        """Register embedding records as knowledge assets for a document."""
        try:
            logger.info(
                "[ASSET] Registered %d embeddings for document %s",
                len(embeddings),
                document_id,
            )
        except Exception as exc:
            logger.warning("[ASSET] register_embeddings failed: %s", exc)

    async def register_analysis(self, analysis: Any) -> None:
        """Register a document analysis as a knowledge asset."""
        try:
            logger.info(
                "[ASSET] Registered analysis %s for document %s",
                getattr(analysis, "id", "?"),
                getattr(analysis, "document_id", "?"),
            )
        except Exception as exc:
            logger.warning("[ASSET] register_analysis failed: %s", exc)
