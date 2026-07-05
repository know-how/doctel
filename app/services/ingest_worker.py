import asyncio
import logging
from typing import Optional
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db.models import Document
from app.services.ingestion_service import ingest_document

logger = logging.getLogger(__name__)

# Bounded queue to avoid unbounded memory growth. Size can be tuned.
_QUEUE_MAXSIZE = 1024
_queue: "asyncio.Queue[int]" = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
_worker_task: Optional[asyncio.Task] = None
_semaphore = asyncio.Semaphore(1)
_cancelled_doc_ids: set[int] = set()


def cancel_document_ids(doc_ids: list[int]) -> None:
    """Mark document IDs as cancelled so the worker skips them when dequeued."""
    _cancelled_doc_ids.update(doc_ids)


async def enqueue(document_id: int, timeout: float = 2.0) -> bool:
    """Enqueue a document id for ingestion.

    Returns True if queued successfully, False if the queue is full (enqueue timeout).
    """
    try:
        await asyncio.wait_for(_queue.put(document_id), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        logger.warning("Ingest queue full, failed to enqueue document_id=%s", document_id)
        return False


async def start_worker() -> None:
    """Start the ingest worker background task (idempotent).

    This function schedules the background _run() coroutine and returns quickly.
    """
    global _worker_task
    if _worker_task and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_run())


async def _run() -> None:
    """Worker loop that consumes document IDs and processes them.

    This loop is resilient: exceptions from ingest_document are logged and the
    worker continues processing other items. Consider adding retry/backoff
    and moving failed items to a dead-letter queue if needed.
    """
    while True:
        doc_id = await _queue.get()
        try:
            if doc_id in _cancelled_doc_ids:
                _cancelled_doc_ids.discard(doc_id)
                continue
            async with _semaphore:
                async with AsyncSessionLocal() as db:
                    try:
                        result = await db.execute(select(Document).where(Document.id == doc_id))
                        doc = result.scalar_one_or_none()
                        if not doc:
                            logger.info("Ingest worker: document not found id=%s", doc_id)
                            continue
                        await ingest_document(doc_id, db)
                    except Exception:
                        logger.exception("Failed to ingest document id=%s", doc_id)
                        # On failure, don't crash the worker; optionally requeue or persist.
        finally:
            try:
                _queue.task_done()
            except Exception:
                pass


# Health helpers

def queue_size() -> int:
    return _queue.qsize()


def worker_running() -> bool:
    return _worker_task is not None and not _worker_task.done()


__all__ = [
    "enqueue",
    "start_worker",
    "cancel_document_ids",
    "queue_size",
    "worker_running",
]
