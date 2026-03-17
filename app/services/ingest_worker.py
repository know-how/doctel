import asyncio
from typing import Optional
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db.models import Document
from app.services.ingestion_service import ingest_document

_queue: "asyncio.Queue[int]" = asyncio.Queue()
_worker_task: Optional[asyncio.Task] = None
_semaphore = asyncio.Semaphore(1)


async def enqueue(document_id: int) -> None:
    await _queue.put(document_id)


async def start_worker() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_run())


async def _run() -> None:
    while True:
        doc_id = await _queue.get()
        try:
            async with _semaphore:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(Document).where(Document.id == doc_id))
                    doc = result.scalar_one_or_none()
                    if not doc:
                        continue
                    await ingest_document(doc_id, db)
        finally:
            _queue.task_done()

