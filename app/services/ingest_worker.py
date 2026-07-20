import asyncio
import logging
from typing import Optional
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.db.models import Document
from app.services.ingestion_service import ingest_document

logger = logging.getLogger(__name__)

# Bounded queue to avoid unbounded memory growth. Size can be tuned.
# Stores (document_id, owner_id) tuples so the worker can set RLS context
# before reading the document row.
_QUEUE_MAXSIZE = 1024
_queue: "asyncio.Queue[tuple[UUID, UUID]]" = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
_worker_task: Optional[asyncio.Task] = None
_semaphore = asyncio.Semaphore(1)
_cancelled_doc_ids: set[UUID] = set()

# Retry with exponential backoff
_MAX_RETRIES = 3
_retry_counts: dict[UUID, int] = {}
_dead_letter: set[UUID] = set()


async def _set_rls_context(db: AsyncSession, user_id: UUID) -> None:
    """Set app.current_user_id to the given user_id on the database session.
    Uses SESSION scope (is_local=false) to survive transaction boundaries."""
    await db.execute(
        text("SELECT set_config('app.current_user_id', :val, false)"),
        {"val": str(user_id)},
    )


def cancel_document_ids(doc_ids: list[UUID], user_id: Optional[UUID] = None) -> None:
    """Mark document IDs as cancelled so the worker skips them when dequeued.
    Also sets DB flag for persistent cancellation.

    Args:
        doc_ids: List of document UUIDs to cancel.
        user_id:  Optional user UUID for RLS context. If omitted, the UPDATE
                  may be blocked by RLS policies and the caller should perform
                  its own DB update.
    """
    _cancelled_doc_ids.update(doc_ids)
    if not user_id:
        return
    # Fire-and-forget DB update
    async def _persist():
        try:
            async with AsyncSessionLocal() as db:
                await _set_rls_context(db, user_id)
                for did in doc_ids:
                    await db.execute(
                        text("UPDATE documents SET cancel_requested = TRUE, processing_state = 'CANCELLED' WHERE id = :id"),
                        {"id": did},
                    )
                await db.commit()
        except Exception:
            pass
    try:
        asyncio.ensure_future(_persist())
    except Exception:
        pass


async def _mark_doc_state(
    doc_id: UUID,
    processing_state: str,
    owner_id: Optional[UUID] = None,
    error_msg: str = "",
) -> None:
    """Directly update a document's processing state without loading the full row.

    Sets RLS context before the UPDATE so that FORCE ROW LEVEL SECURITY policies
    do not silently block the write.  Falls back gracefully if the context cannot
    be established — the caller MAY lose this update but processing continues.
    """
    try:
        async with AsyncSessionLocal() as db:
            if owner_id:
                await _set_rls_context(db, owner_id)
            await db.execute(
                text("""
                    UPDATE documents
                    SET processing_state = CAST(:state AS VARCHAR),
                        status = LOWER(CAST(:state AS VARCHAR)),
                        error_message = CASE WHEN :error != '' THEN :error ELSE error_message END,
                        updated_at = NOW()
                    WHERE id = :doc_id
                """),
                {"state": processing_state, "doc_id": doc_id, "error": error_msg},
            )
            await db.commit()
    except Exception as e:
        logger.error(f"[WORKER] Failed to update doc state for {doc_id}: {e}")


async def enqueue(document_id: UUID, owner_id: UUID, timeout: float = 2.0) -> bool:
    """Enqueue a document id for ingestion.

    Stores (doc_id, owner_id) so the worker can set RLS context before reading.

    Returns True if queued successfully, False if the queue is full (enqueue timeout).
    """
    qsize = _queue.qsize()
    logger.debug("[ENQUEUE] document_id=%s owner_id=%s queue_size=%d", document_id, owner_id, qsize)
    try:
        await asyncio.wait_for(_queue.put((document_id, owner_id)), timeout=timeout)
        logger.debug("[ENQUEUE] SUCCESS document_id=%s queue_size=%d", document_id, _queue.qsize())
        await _mark_doc_state(document_id, "QUEUED", owner_id)
        return True
    except asyncio.TimeoutError:
        logger.warning("[ENQUEUE] TIMEOUT document_id=%s queue_size=%d", document_id, _queue.qsize())
        return False


async def start_worker() -> None:
    """Start the ingest worker background task (idempotent)."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        return
    try:
        _worker_task = asyncio.create_task(_run())
        logger.info("[WORKER] Worker task created")
    except Exception as e:
        logger.error(f"[WORKER] Failed to create worker task: {e}")
        raise

    # Fire-and-forget startup recovery — scans the database for documents
    # that were orphaned by the previous server incarnation and re-enqueues
    # them.  This is intentionally non-blocking so the worker loop starts
    # consuming immediately and the recovery runs concurrently.
    asyncio.create_task(_recover_orphaned_docs())


async def _run() -> None:
    """Worker loop that consumes document IDs and processes them.

    Resilient: exceptions from ingest_document are logged, retried with
    backoff, and failed items move to dead-letter. Session creation failures
    are caught so the loop survives them.
    """
    while True:
        doc_id: UUID
        owner_id: UUID
        try:
            doc_id, owner_id = await _queue.get()
        except Exception as e:
            logger.error(f"[WORKER] Failed to dequeue: {e}")
            await asyncio.sleep(1)
            continue

        logger.info(f"[WORKER] Dequeued document_id={doc_id} for ingestion")

        # ── Quick inline cancellation check ──
        if doc_id in _cancelled_doc_ids:
            logger.info(f"[WORKER] Document {doc_id} was cancelled (in-memory), skipping")
            _cancelled_doc_ids.discard(doc_id)
            await _mark_doc_state(doc_id, "CANCELLED", owner_id)
            continue

        try:
            # ── Pre-check DB cancel/pause flags (with RLS context) ──
            skip_doc = False
            try:
                async with AsyncSessionLocal() as check_db:
                    await _set_rls_context(check_db, owner_id)
                    chk = await check_db.execute(
                        text("SELECT cancel_requested, pause_requested FROM documents WHERE id = :doc_id"),
                        {"doc_id": doc_id},
                    )
                    row = chk.one_or_none()
                    if row is not None:
                        if row.cancel_requested:
                            logger.info(f"[WORKER] Document {doc_id} was cancelled (DB flag), skipping")
                            skip_doc = True
                        elif row.pause_requested:
                            logger.info(f"[WORKER] Document {doc_id} is paused, re-queueing")
                            await _queue.put((doc_id, owner_id))
                            skip_doc = True
            except Exception as chk_e:
                logger.warning(f"[WORKER] Flag check failed for {doc_id}: {chk_e}")
            if skip_doc:
                continue

            # ── Session-scoped processing ──
            try:
                async with _semaphore:
                    async with AsyncSessionLocal() as db:
                        await _set_rls_context(db, owner_id)

                        await db.execute(
                            text("""
                                UPDATE documents
                                SET processing_state = 'PROCESSING',
                                    status = 'ingesting',
                                    processing_step = 'dequeued',
                                    ingest_step = 'dequeued'
                                WHERE id = :doc_id
                            """),
                            {"doc_id": doc_id},
                        )
                        await db.commit()

                        # Re-set RLS context after commit since the async session
                        # may get a fresh connection from the pool.
                        await _set_rls_context(db, owner_id)

                        result = await db.execute(
                            select(Document)
                            .options(
                                selectinload(Document.project),
                                selectinload(Document.analysis),
                                selectinload(Document.chunks),
                                selectinload(Document.prompts),
                            )
                            .where(Document.id == doc_id)
                        )
                        doc = result.scalar_one_or_none()
                        if not doc:
                            await _mark_doc_state(doc_id, "FAILED", owner_id, "Document not found")
                            continue
                        logger.info("[WORKER] Starting ingest_document for %s (%s) state=%s",
                                    doc_id, doc.filename, doc.processing_state)
                        await ingest_document(doc_id, db)
                        logger.info("[WORKER] Completed ingest_document for %s", doc_id)
            except Exception as e:
                retries = _retry_counts.get(doc_id, 0) + 1
                _retry_counts[doc_id] = retries
                logger.error(f"[WORKER] Exception traceback for doc {doc_id}:", exc_info=True)
                if retries <= _MAX_RETRIES:
                    backoff = 2 ** retries
                    logger.warning(
                        f"[WORKER] Retry {retries}/{_MAX_RETRIES} for doc {doc_id} "
                        f"in {backoff}s: {e}"
                    )
                    await _mark_doc_state(doc_id, "RETRYING", owner_id, str(e))
                    _queue.put_nowait((doc_id, owner_id))
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        f"[WORKER] Document {doc_id} exhausted all {_MAX_RETRIES} "
                        f"retries, moving to dead-letter: {e}"
                    )
                    await _mark_doc_state(doc_id, "FAILED", owner_id, str(e))
                    _dead_letter.add(doc_id)
                    _retry_counts.pop(doc_id, None)
        finally:
            try:
                _queue.task_done()
            except Exception:
                pass


# ── Startup recovery ──────────────────────────────────────────────────────────

async def _recover_orphaned_docs() -> None:
    """Re-enqueue documents orphaned by a server restart.

    The in-memory ``asyncio.Queue`` is lost on every restart, so documents
    that had been enqueued (or were being processed) by the previous server
    incarnation would otherwise remain stuck forever.

    This function uses a ``SECURITY DEFINER`` database function
    (``get_orphaned_documents()``) owned by the ``doctel_rls_bypass`` role
    so it can SELECT from the ``documents`` table without being blocked by
    ``FORCE ROW LEVEL SECURITY``.

    The function is auto-created here as a convenience.  Ownership transfer
    to ``doctel_rls_bypass`` requires superuser privileges and is best-effort
    from the application layer.  For production deployments run
    ``migrations/startup_recovery_function.sql`` as the Postgres superuser.
    """
    logger.info("[RECOVERY] Scanning for orphaned documents...")
    print("[RECOVERY] Scanning for orphaned documents...", flush=True)

    # 1. Ensure the helper function exists in the database
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("""
                CREATE OR REPLACE FUNCTION get_orphaned_documents()
                RETURNS TABLE(doc_id UUID, doc_owner_id UUID)
                LANGUAGE plpgsql STABLE SECURITY DEFINER
                SET search_path = public, pg_temp
                AS $$ BEGIN
                    RETURN QUERY
                    SELECT d.id, d.owner_id
                    FROM documents d
                    WHERE d.processing_state IN ('UPLOADED', 'QUEUED', 'PROCESSING', 'RETRYING')
                      AND d.deleted_at IS NULL;
                END; $$;
            """))
            # 2. Best-effort ownership transfer — requires superuser membership
            try:
                await db.execute(
                    text("ALTER FUNCTION get_orphaned_documents() OWNER TO doctel_rls_bypass")
                )
                logger.info("[RECOVERY] Function ownership transferred to doctel_rls_bypass")
            except Exception:
                logger.warning(
                    "[RECOVERY] Cannot transfer function ownership — "
                    "run migrations/startup_recovery_function.sql as superuser "
                    "for full RLS bypass"
                )
            await db.commit()
    except Exception as e:
        logger.error("[RECOVERY] Failed to create recovery function: %s", e)
        print(f"[RECOVERY] Failed to create recovery function: {e}", flush=True)

    # 3. Query orphaned documents
    #     If the ownership transfer above failed (non-superuser) the function
    #     will still be subject to FORCE RLS and will return zero rows.  That
    #     is logged so the operator knows the migration is needed.
    try:
        async with AsyncSessionLocal() as db:
            rows = (
                await db.execute(
                    text("SELECT doc_id, doc_owner_id FROM get_orphaned_documents()")
                )
            ).all()
    except Exception as e:
        logger.error("[RECOVERY] Failed to query orphaned documents: %s", e)
        print(f"[RECOVERY] Failed to query orphaned documents: {e}", flush=True)
        return

    if not rows:
        logger.info(
            "[RECOVERY] No orphaned documents found"
            " (may be blocked by RLS — run the SQL migration if documents are stuck)"
        )
        print("[RECOVERY] No orphaned documents found (may be blocked by RLS)", flush=True)
        return

    logger.info("[RECOVERY] Found %d orphaned document(s), re-enqueueing...", len(rows))
    print(f"[RECOVERY] Found {len(rows)} orphaned document(s), re-enqueueing...", flush=True)
    for doc_id, owner_id in rows:
        try:
            ok = await enqueue(doc_id, owner_id)
            logger.info(
                "[RECOVERY] Re-enqueued doc=%s owner=%s success=%s",
                doc_id, owner_id, ok,
            )
            print(f"[RECOVERY] Re-enqueued doc={doc_id} owner={owner_id} success={ok}", flush=True)
        except Exception as e:
            logger.error("[RECOVERY] Failed to re-enqueue doc=%s: %s", doc_id, e)
            print(f"[RECOVERY] Failed to re-enqueue doc={doc_id}: {e}", flush=True)


# Health helpers

def queue_size() -> int:
    return _queue.qsize()


def dead_letter_size() -> int:
    return len(_dead_letter)


def worker_running() -> bool:
    return _worker_task is not None and not _worker_task.done()


def clear_dead_letter() -> None:
    _dead_letter.clear()


__all__ = [
    "enqueue",
    "start_worker",
    "cancel_document_ids",
    "queue_size",
    "dead_letter_size",
    "worker_running",
    "clear_dead_letter",
]
