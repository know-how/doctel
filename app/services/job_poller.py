"""
job_poller.py — Persistent Job Poller & Claiming Engine

Replaces the volatile in-memory ``asyncio.Queue`` with a database-backed
persistent claiming engine.  The poller calls the SECURITY DEFINER function
``claim_next_job()`` (``FOR UPDATE SKIP LOCKED``) to atomically claim the
next eligible job, then dispatches it to the appropriate worker by
``job_type``.

Key responsibilities:
    • Poll ``claim_next_job()`` every ~1 s (configurable)
    • Dispatch claimed jobs to handlers by ``job_type``
    • Worker heartbeat (refresh ``claimed_at`` every 15 s)
    • Dead worker detection via ``reclaim_orphaned_jobs()`` every 60 s
    • Graceful shutdown — reset in-progress jobs back to QUEUED
    • Job CRUD: ``create_job()``, ``cancel_job()``

Architecture:
    ┌─────────────────────────────────────────────┐
    │              _poller_loop()                  │
    │  ┌──────────┐   ┌───────────────────────┐   │
    │  │ poll_cycle│──▶│_execute_and_release() │   │
    │  │  (1s)    │   │  ┌─────────────────┐  │   │
    │  └──────────┘   │  │ _execute_job()   │  │   │
    │                  │  │  ┌─────────────┐ │  │   │
    │                  │  │  │document_     │ │  │   │
    │                  │  │  │ingest handler│ │  │   │
    │                  │  │  └─────────────┘ │  │   │
    │                  │  └─────────────────┘  │   │
    │                  └───────────────────────┘   │
    │                                              │
    │  ┌──────────────────────────────────────┐    │
    │  │ _heartbeat_loop()  — every 15 s      │    │
    │  │ _reclaim_loop()    — every 60 s      │    │
    │  └──────────────────────────────────────┘    │
    └─────────────────────────────────────────────┘

Version: Phase 3/12 — Job Poller + Claiming Engine
"""

# ═══════════════════════════════════════════════════════════════════════════════
# Imports
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from datetime import timedelta
from typing import Optional, Any
from uuid import UUID

from sqlalchemy import text, select

from app.db.database import AsyncSessionLocal
from app.db.job_models import VALID_JOB_TYPES, VALID_JOB_STATES
from app.db.models import Document
from app.services.ingestion_service import ingest_document
from app.services.reembedding_service import reembed_document
from app.services.vision_service import analyze_image
from app.services.transcription_service import transcribe_file
from app.services.agent_executor_service import AgentExecutor
from app.services.agent_orchestration_service import OrchestratorAgent
from app.config import settings

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Unique identity for *this* worker process — used when claiming jobs so that
# dead-worker detection can reclaim jobs if the worker crashes.
_WORKER_ID: str = f"worker-{socket.gethostname()}-{os.getpid()}"

# Poller interval when no jobs are available (seconds)
_POLL_IDLE_INTERVAL: float = settings.job_poller.poll_interval_seconds

# Poller interval after an unexpected error (seconds) — backoff to avoid
# tight looping on persistent failures.
_POLL_ERROR_INTERVAL: float = 5.0

# Heartbeat interval (seconds) — how often we refresh claimed_at for
# PROCESSING jobs owned by this worker.
_HEARTBEAT_INTERVAL: float = settings.job_poller.heartbeat_interval_seconds

# Dead-worker reclamation interval (seconds) — how often we call
# reclaim_orphaned_jobs() to reset CLAIMED jobs whose heartbeat has expired.
_RECLAIM_INTERVAL: float = settings.job_poller.reclaim_interval_seconds

# Heartbeat TTL passed to reclaim_orphaned_jobs() — any job CLAIMED longer
# than this interval is considered orphaned and reset to QUEUED.
_RECLAIM_TIMEOUT: timedelta = timedelta(seconds=settings.job_poller.reclaim_interval_seconds)

# Max time to wait for active jobs to finish during shutdown (seconds).
_SHUTDOWN_WAIT_TIMEOUT: float = settings.job_poller.shutdown_wait_seconds

# Job types this poller can handle.  Phase 4 expands this to a dynamic
# worker registry loaded from app/services/workers/.
_SUPPORTED_JOB_TYPES: list[str] = [
    "document_ingest",
    "embedding",
    "image_process",
    "audio_transcribe",
    "video_transcribe",
    "workflow",
    "agent_run",
    "agent_research",
    "agent_kg",
]

# All valid job types (used for validation in cancel and status lookups).
_ALL_JOB_TYPES: list[str] = sorted(VALID_JOB_TYPES)

# Job states that are considered "in progress" — these need to be reset on
# graceful shutdown.
_IN_PROGRESS_STATES: frozenset = frozenset({"CLAIMED", "PROCESSING"})

# Job states that are "terminal" — no further transitions possible.
_TERMINAL_STATES: frozenset = frozenset({"COMPLETED", "FAILED", "CANCELLED"})

# ═══════════════════════════════════════════════════════════════════════════════
# Module-level state
# ═══════════════════════════════════════════════════════════════════════════════

_poller_task: Optional[asyncio.Task] = None
"""Reference to the main poller background task (set by ``start_poller()``)."""

_semaphore = asyncio.Semaphore(settings.job_poller.max_workers or 1)
"""Concurrency guard.  Default 1; increased in Phase 4 for multi-worker."""

_active_jobs: dict[UUID, asyncio.Task] = {}
"""Mapping of ``job_id → asyncio.Task`` for currently executing jobs.

Used for:
    • Graceful shutdown — wait for active tasks to finish
    • Cancel-by-job-id — cancel the in-flight task immediately
"""

_shutdown_event = asyncio.Event()
"""Signals all loops (poller, heartbeat, reclaim) to stop gracefully."""

# Optional background-task references kept so we can cancel them on stop.
_heartbeat_task: Optional[asyncio.Task] = None
_reclaim_task: Optional[asyncio.Task] = None


# ═══════════════════════════════════════════════════════════════════════════════
# RLS Context Helper
# ═══════════════════════════════════════════════════════════════════════════════

async def set_rls_context(db: Any, user_id: UUID) -> None:
    """Set ``app.current_user_id`` using **session** scope (``is_local=false``).

    Session scope survives transaction boundaries, which is essential for
    the poller/worker operations that span multiple transactions (e.g., a
    poll cycle that claims a job, reads data, writes checkpoints, etc.).

    This is a **public** function so that worker modules (Phase 4) can call
    it independently without importing private helpers.

    Args:
        db: A SQLAlchemy ``AsyncSession`` (or any connection with ``.execute()``).
        user_id: The UUID of the user to impersonate for RLS policies.
    """
    await db.execute(
        text("SELECT set_config('app.current_user_id', :val, false)"),
        {"val": str(user_id)},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Job CRUD
# ═══════════════════════════════════════════════════════════════════════════════

async def create_job(
    job_type: str,
    *,
    document_id: Optional[UUID] = None,
    asset_id: Optional[UUID] = None,
    owner_id: Optional[UUID] = None,
    priority: int = 0,
    max_retries: int = 3,
    payload: Optional[dict[str, Any]] = None,
) -> Optional[UUID]:
    """Create a new ``processing_job`` and return its UUID.

    This is the primary insertion point — replaces the old ``enqueue()``.
    The job is created in **QUEUED** state and will be picked up by the
    next available poll cycle.

    Args:
        job_type:
            One of ``VALID_JOB_TYPES`` (e.g. ``"document_ingest"``).
        document_id:
            Optional target document UUID.
        asset_id:
            Optional target knowledge-asset UUID.
        owner_id:
            **Required** — the user who owns this job.  Used for RLS.
        priority:
            Higher values = more urgent.  Negative for background jobs.
        max_retries:
            Max retry attempts before the job moves to FAILED (default 3).
        payload:
            Optional arbitrary JSON-serialisable dict.

    Returns:
        The UUID of the newly created job, or ``None`` on failure.

    Example::

        job_id = await create_job(
            "document_ingest",
            document_id=doc_id,
            owner_id=current_user.id,
        )
    """
    # ── Validate inputs ────────────────────────────────────────────────────
    if job_type not in VALID_JOB_TYPES:
        logger.error("[CREATE_JOB] Invalid job_type=%s (valid: %s)", job_type, sorted(VALID_JOB_TYPES))
        return None

    if owner_id is None:
        logger.error("[CREATE_JOB] owner_id is required")
        return None

    # ── Persist ────────────────────────────────────────────────────────────
    try:
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)

            result = await db.execute(
                text("""
                    INSERT INTO processing_jobs
                        (job_type, job_state, priority,
                         document_id, asset_id, owner_id,
                         max_retries, retry_count,
                         pause_requested, cancel_requested,
                         payload)
                    VALUES
                        (:job_type, 'QUEUED', :priority,
                         :document_id, :asset_id, :owner_id,
                         :max_retries, 0,
                         FALSE, FALSE,
                         CAST(:payload AS jsonb))
                    RETURNING id
                """),
                {
                    "job_type": job_type,
                    "priority": priority,
                    "document_id": document_id,
                    "asset_id": asset_id,
                    "owner_id": owner_id,
                    "max_retries": max_retries,
                    "payload": json.dumps(payload) if payload else None,
                },
            )
            await db.commit()
            job_id = result.scalar()

            logger.info(
                "[CREATE_JOB] Created %s job=%s doc=%s owner=%s prio=%d",
                job_type, job_id, document_id, owner_id, priority,
            )
            return job_id

    except Exception as exc:
        logger.error(
            "[CREATE_JOB] Failed job_type=%s owner=%s doc=%s asset=%s: %s",
            job_type, owner_id, document_id, asset_id, exc,
            exc_info=True,
        )
        return None


async def cancel_job(
    *,
    job_id: Optional[UUID] = None,
    document_id: Optional[UUID] = None,
    owner_id: Optional[UUID] = None,
) -> int:
    """Cancel one or more processing jobs.

    Sets ``cancel_requested = TRUE`` and transitions to **CANCELLED**.
    In-flight tasks are cancelled immediately via ``asyncio.Task.cancel()``.

    Args:
        job_id:
            Cancel a single job by its UUID.
        document_id:
            Cancel **all** non-terminal jobs for a given document.
        owner_id:
            **Required** when ``document_id`` is provided (for RLS).
            Optional when ``job_id`` is provided.

    Returns:
        Number of jobs that were cancelled (database rows updated).

    Example::

        # Cancel one job
        await cancel_job(job_id=my_job_id)

        # Cancel all jobs for a document
        await cancel_job(document_id=doc_id, owner_id=user_id)
    """
    if job_id is None and document_id is None:
        logger.warning("[CANCEL_JOB] Neither job_id nor document_id provided")
        return 0

    # ── Gather job IDs of in-flight tasks for this document (pre-emptive) ──
    cancelled_active: list[UUID] = []
    if document_id:
        # We can't easily map document_id→job_id in _active_jobs without
        # a lookup table, so we rely on the DB query below.  For single-job
        # cancel, we handle it inline.
        pass

    try:
        async with AsyncSessionLocal() as db:
            if owner_id:
                await set_rls_context(db, owner_id)

            if job_id is not None:
                # ── Cancel a single job ────────────────────────────────────
                result = await db.execute(
                    text("""
                        UPDATE processing_jobs
                        SET cancel_requested = TRUE,
                            job_state         = 'CANCELLED',
                            completed_at      = now(),
                            updated_at        = now()
                        WHERE id = :job_id
                          AND job_state NOT IN ('COMPLETED', 'CANCELLED', 'FAILED')
                    """),
                    {"job_id": job_id},
                )
                count = result.rowcount

                # Cancel the in-flight task if running
                if job_id in _active_jobs:
                    _active_jobs[job_id].cancel()
                    logger.info("[CANCEL_JOB] Cancelled in-flight task for job=%s", job_id)

                logger.info("[CANCEL_JOB] Cancelled job=%s (count=%d)", job_id, count)

            else:
                # ── Cancel all jobs for a document ─────────────────────────
                result = await db.execute(
                    text("""
                        UPDATE processing_jobs
                        SET cancel_requested = TRUE,
                            job_state         = 'CANCELLED',
                            completed_at      = now(),
                            updated_at        = now()
                        WHERE document_id = :doc_id
                          AND job_state NOT IN ('COMPLETED', 'CANCELLED', 'FAILED')
                        RETURNING id
                    """),
                    {"doc_id": document_id},
                )
                rows = result.fetchall()
                count = len(rows)

                # Cancel any in-flight tasks for these jobs
                for row in rows:
                    jid = row[0] if isinstance(row, (list, tuple)) else row.id
                    if jid in _active_jobs:
                        _active_jobs[jid].cancel()

                logger.info("[CANCEL_JOB] Cancelled %d job(s) for document=%s", count, document_id)

            await db.commit()
            return count

    except Exception as exc:
        logger.error("[CANCEL_JOB] Failed: %s", exc, exc_info=True)
        return 0


async def retry_job(job_id: UUID) -> bool:
    """Reset a FAILED job back to QUEUED for retry.

    Increments ``max_retries`` by 1 to allow another attempt beyond the
    original retry budget.  Clears ``last_error`` and ``completed_at``.

    Args:
        job_id: The UUID of the failed job to retry.

    Returns:
        ``True`` if the job was found and reset, ``False`` otherwise.
    """
    try:
        async with AsyncSessionLocal() as db:
            # Verify job exists and is in FAILED state
            check = await db.execute(
                text("SELECT job_state FROM processing_jobs WHERE id = :jid"),
                {"jid": job_id},
            )
            row = check.one_or_none()
            if row is None:
                logger.warning("[RETRY_JOB] Job not found: %s", job_id)
                return False
            if row.job_state != "FAILED":
                logger.warning("[RETRY_JOB] Job %s is in state %s (expected FAILED)", job_id, row.job_state)
                return False

            result = await db.execute(
                text("""
                    UPDATE processing_jobs
                    SET job_state      = 'QUEUED',
                        retry_count    = 0,
                        last_error     = NULL,
                        completed_at   = NULL,
                        worker_id      = NULL,
                        claimed_at     = NULL,
                        updated_at     = now()
                    WHERE id = :jid
                      AND job_state = 'FAILED'
                """),
                {"jid": job_id},
            )
            await db.commit()
            success = result.rowcount > 0
            if success:
                logger.info("[RETRY_JOB] Job %s reset to QUEUED", job_id)
            return success
    except Exception as exc:
        logger.error("[RETRY_JOB] Failed: %s", exc, exc_info=True)
        return False


async def restart_job(job_id: UUID) -> bool:
    """Reset a COMPLETED or stuck job back to QUEUED for re-processing.

    Unlike ``retry_job()``, this accepts COMPLETED, CANCELLED, or FAILED
    states and fully resets the job as if it were new (preserving original
    ``job_type``, ``document_id``, ``payload``, etc.).

    Args:
        job_id: The UUID of the job to restart.

    Returns:
        ``True`` if the job was found and reset, ``False`` otherwise.
    """
    try:
        async with AsyncSessionLocal() as db:
            check = await db.execute(
                text("SELECT job_state FROM processing_jobs WHERE id = :jid"),
                {"jid": job_id},
            )
            row = check.one_or_none()
            if row is None:
                logger.warning("[RESTART_JOB] Job not found: %s", job_id)
                return False

            result = await db.execute(
                text("""
                    UPDATE processing_jobs
                    SET job_state        = 'QUEUED',
                        retry_count      = 0,
                        last_error       = NULL,
                        completed_at     = NULL,
                        worker_id        = NULL,
                        claimed_at       = NULL,
                        pause_requested  = FALSE,
                        cancel_requested = FALSE,
                        checkpoint       = NULL,
                        updated_at       = now()
                    WHERE id = :jid
                """),
                {"jid": job_id},
            )
            await db.commit()
            success = result.rowcount > 0
            if success:
                logger.info("[RESTART_JOB] Job %s reset to QUEUED", job_id)
            return success
    except Exception as exc:
        logger.error("[RESTART_JOB] Failed: %s", exc, exc_info=True)
        return False


async def get_job_stats() -> dict[str, Any]:
    """Return aggregate statistics for all processing jobs.

    Returns:
        Dict with counts by state, counts by type, total jobs,
        and active worker count.
    """
    try:
        async with AsyncSessionLocal() as db:
            # Count by state
            state_result = await db.execute(
                text("""
                    SELECT job_state, COUNT(*) AS cnt
                    FROM processing_jobs
                    GROUP BY job_state
                    ORDER BY job_state
                """)
            )
            by_state: dict[str, int] = {}
            for row in state_result.fetchall():
                by_state[row.job_state] = row.cnt

            # Count by type
            type_result = await db.execute(
                text("""
                    SELECT job_type, COUNT(*) AS cnt
                    FROM processing_jobs
                    GROUP BY job_type
                    ORDER BY job_type
                """)
            )
            by_type: dict[str, int] = {}
            for row in type_result.fetchall():
                by_type[row.job_type] = row.cnt

            # Total job count
            total = sum(by_state.values())

            # Active worker count (distinct worker_ids with CLAIMED/PROCESSING jobs)
            worker_result = await db.execute(
                text("""
                    SELECT COUNT(DISTINCT worker_id) AS active_workers
                    FROM processing_jobs
                    WHERE job_state IN ('CLAIMED', 'PROCESSING')
                      AND worker_id IS NOT NULL
                """)
            )
            active_workers = worker_result.scalar() or 0

            return {
                "total_jobs": total,
                "by_state": by_state,
                "by_type": by_type,
                "active_workers": active_workers,
                "poller_running": poller_running(),
                "this_worker_active_jobs": active_job_count(),
                "this_worker_id": current_worker_id(),
            }
    except Exception as exc:
        logger.error("[JOB_STATS] Failed: %s", exc, exc_info=True)
        return {
            "total_jobs": 0,
            "by_state": {},
            "by_type": {},
            "active_workers": 0,
            "poller_running": poller_running(),
            "this_worker_active_jobs": active_job_count(),
            "this_worker_id": current_worker_id(),
        }


async def get_job(
    job_id: UUID,
    owner_id: Optional[UUID] = None,
) -> Optional[dict[str, Any]]:
    """Retrieve a single job by its UUID.

    Args:
        job_id: The UUID of the job to retrieve.
        owner_id: Optional owner filter (for RLS context).

    Returns:
        A dict of job columns, or ``None`` if not found.
    """
    try:
        async with AsyncSessionLocal() as db:
            if owner_id:
                await set_rls_context(db, owner_id)

            result = await db.execute(
                text("""
                    SELECT id, job_type, job_state, priority,
                           document_id, asset_id, owner_id,
                           worker_id, retry_count, max_retries,
                           created_at, updated_at, claimed_at, completed_at,
                           last_error, pause_requested, cancel_requested,
                           checkpoint, payload
                    FROM processing_jobs
                    WHERE id = :job_id
                """),
                {"job_id": job_id},
            )
            row = result.one_or_none()
            if row is None:
                return None

            return {
                "id": str(row.id),
                "job_type": row.job_type,
                "job_state": row.job_state,
                "priority": row.priority,
                "document_id": str(row.document_id) if row.document_id else None,
                "asset_id": str(row.asset_id) if row.asset_id else None,
                "owner_id": str(row.owner_id),
                "worker_id": row.worker_id,
                "retry_count": row.retry_count,
                "max_retries": row.max_retries,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "claimed_at": row.claimed_at.isoformat() if row.claimed_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "last_error": row.last_error,
                "pause_requested": row.pause_requested,
                "cancel_requested": row.cancel_requested,
                "checkpoint": row.checkpoint,
                "payload": row.payload,
            }

    except Exception as exc:
        logger.error("[GET_JOB] Failed for job=%s: %s", job_id, exc, exc_info=True)
        return None


async def list_jobs(
    *,
    owner_id: Optional[UUID] = None,
    job_type: Optional[str] = None,
    job_state: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List processing jobs with optional filters.

    Args:
        owner_id: Filter by owner (uses RLS context).
        job_type: Filter by job type (e.g. ``"document_ingest"``).
        job_state: Filter by state (e.g. ``"FAILED"``).
        limit: Max rows to return (default 50).
        offset: Pagination offset (default 0).

    Returns:
        List of job dicts (same shape as ``get_job()``).
    """
    try:
        async with AsyncSessionLocal() as db:
            if owner_id:
                await set_rls_context(db, owner_id)

            conditions: list[str] = []
            params: dict[str, Any] = {"limit": limit, "offset": offset}

            if job_type:
                conditions.append("job_type = :job_type")
                params["job_type"] = job_type
            if job_state:
                conditions.append("job_state = :job_state")
                params["job_state"] = job_state

            where_clause = " AND ".join(conditions) if conditions else "TRUE"

            result = await db.execute(
                text(f"""
                    SELECT id, job_type, job_state, priority,
                           document_id, asset_id, owner_id,
                           worker_id, retry_count, max_retries,
                           created_at, updated_at, claimed_at, completed_at,
                           last_error, pause_requested, cancel_requested,
                           checkpoint, payload
                    FROM processing_jobs
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                params,
            )
            rows = result.fetchall()

            jobs: list[dict[str, Any]] = []
            for row in rows:
                jobs.append({
                    "id": str(row.id),
                    "job_type": row.job_type,
                    "job_state": row.job_state,
                    "priority": row.priority,
                    "document_id": str(row.document_id) if row.document_id else None,
                    "asset_id": str(row.asset_id) if row.asset_id else None,
                    "owner_id": str(row.owner_id),
                    "worker_id": row.worker_id,
                    "retry_count": row.retry_count,
                    "max_retries": row.max_retries,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    "claimed_at": row.claimed_at.isoformat() if row.claimed_at else None,
                    "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                    "last_error": row.last_error,
                    "pause_requested": row.pause_requested,
                    "cancel_requested": row.cancel_requested,
                    "checkpoint": row.checkpoint,
                    "payload": row.payload,
                })

            return jobs

    except Exception as exc:
        logger.error("[LIST_JOBS] Failed: %s", exc, exc_info=True)
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Claiming Engine
# ═══════════════════════════════════════════════════════════════════════════════

async def _call_claim_next_job(
    db: Any,
    job_types: Optional[list[str]] = None,
) -> Optional[dict[str, Any]]:
    """Call the SECURITY DEFINER function ``claim_next_job()``.

    The function returns a JSON object (not a SETOF / TABLE), so we parse
    with ``json.loads()``.  It bypasses RLS internally, so the poller can
    claim jobs belonging to any user.

    Args:
        db: A SQLAlchemy ``AsyncSession``.
        job_types:
            Optional filter — only claim jobs whose ``job_type`` is in this
            list.  ``None`` or empty means any job type.

    Returns:
        A dict with keys ``id``, ``job_type``, ``document_id``, ``owner_id``,
        ``payload``, etc., or ``None`` if no eligible job was found.
    """
    result = await db.execute(
        text("SELECT claim_next_job(:worker_id, :job_types)"),
        {
            "worker_id": _WORKER_ID,
            "job_types": job_types,
        },
    )
    raw = result.scalar()
    if raw is None:
        return None

    # The function returns JSON — handle both str and dict responses.
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
    # Some drivers may return a list (unlikely with row_to_json).
    if isinstance(raw, (list, tuple)):
        return dict(raw) if raw else None
    return None


async def _transition_to_processing(db: Any, job_id: UUID) -> bool:
    """Transition a CLAIMED job to PROCESSING state.

    This marks the point where the worker actually begins working.  If the
    job is no longer in CLAIMED state (e.g., another worker grabbed it or
    it was cancelled), this is a no-op.

    Returns:
        ``True`` if the transition succeeded, ``False`` otherwise.
    """
    result = await db.execute(
        text("""
            UPDATE processing_jobs
            SET job_state = 'PROCESSING',
                updated_at = now()
            WHERE id = :job_id
              AND job_state = 'CLAIMED'
        """),
        {"job_id": job_id},
    )
    await db.commit()
    return result.rowcount > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Job Execution
# ═══════════════════════════════════════════════════════════════════════════════

async def _execute_job(job_data: dict[str, Any]) -> None:
    """Execute a claimed job by dispatching to the appropriate handler.

    This is the core dispatch function.  Currently supports:
        - ``document_ingest`` → ``ingest_document()``

    Phase 4 expands this to a dynamic worker registry from
    ``app/services/workers/``.

    Args:
        job_data: Dict returned by ``claim_next_job()``.  Must contain keys:
            ``id``, ``job_type``, ``document_id``, ``owner_id``.
    """
    # ── Normalise UUIDs ───────────────────────────────────────────────────
    raw_id: Any = job_data["id"]
    job_id: UUID = UUID(raw_id) if isinstance(raw_id, str) else raw_id

    job_type: str = job_data["job_type"]
    raw_doc: Any = job_data.get("document_id")
    document_id: Optional[UUID] = UUID(raw_doc) if raw_doc else None
    raw_owner: Any = job_data["owner_id"]
    owner_id: UUID = UUID(raw_owner) if isinstance(raw_owner, str) else raw_owner

    # Extract optional fields for extended job types
    raw_asset: Any = job_data.get("asset_id")
    asset_id: Optional[UUID] = UUID(raw_asset) if raw_asset else None
    payload: Optional[dict[str, Any]] = job_data.get("payload")
    if payload is not None and not isinstance(payload, dict):
        payload = None

    logger.info(
        "[EXECUTE_JOB] Starting job=%s type=%s doc=%s owner=%s",
        job_id, job_type, document_id, owner_id,
    )

    # ── Check pre-execution flags ─────────────────────────────────────────
    if job_data.get("cancel_requested"):
        logger.info("[EXECUTE_JOB] Job %s was cancelled before execution", job_id)
        await _mark_job_terminal(job_id, "CANCELLED", owner_id)
        return

    if job_data.get("pause_requested"):
        logger.info("[EXECUTE_JOB] Job %s was paused before execution", job_id)
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)
            await db.execute(
                text("""
                    UPDATE processing_jobs
                    SET job_state = 'PAUSED', updated_at = now()
                    WHERE id = :job_id
                """),
                {"job_id": job_id},
            )
            await db.commit()
        return

    # ── Transition CLAIMED → PROCESSING ───────────────────────────────────
    try:
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)
            ok = await _transition_to_processing(db, job_id)
            if not ok:
                logger.warning(
                    "[EXECUTE_JOB] Job %s already claimed by another worker or cancelled", job_id
                )
                return
    except Exception as exc:
        logger.error("[EXECUTE_JOB] Failed to transition job %s to PROCESSING: %s", job_id, exc)
        await _handle_job_failure(job_id, owner_id, f"Transition error: {exc}")
        return

    # ── Dispatch by job_type ──────────────────────────────────────────────
    try:
        if job_type == "document_ingest":
            await _execute_document_ingest(job_id, document_id, owner_id)
        elif job_type == "embedding":
            await _execute_embedding(job_id, document_id, owner_id)
        elif job_type == "image_process":
            await _execute_image_process(job_id, document_id, owner_id)
        elif job_type == "audio_transcribe":
            await _execute_audio_transcribe(job_id, document_id, owner_id)
        elif job_type == "video_transcribe":
            await _execute_video_transcribe(job_id, document_id, owner_id)
        elif job_type == "workflow":
            await _execute_workflow(job_id, document_id, owner_id, payload)
        elif job_type == "agent_run":
            await _execute_agent_run(job_id, document_id, owner_id, payload)
        elif job_type == "agent_research":
            await _execute_agent_research(job_id, document_id, owner_id, payload)
        elif job_type == "agent_kg":
            await _execute_agent_kg(job_id, document_id, owner_id, payload)
        else:
            error_msg = f"Unsupported job_type: {job_type}"
            logger.error("[EXECUTE_JOB] %s", error_msg)
            await _handle_job_failure(job_id, owner_id, error_msg)

    except asyncio.CancelledError:
        logger.info("[EXECUTE_JOB] Job %s was cancelled (task cancelled)", job_id)
        await _reclaim_job(job_id, owner_id, "Cancelled by shutdown")
        raise

    except Exception as exc:
        logger.error(
            "[EXECUTE_JOB] Unhandled error for job %s: %s", job_id, exc, exc_info=True
        )
        await _handle_job_failure(job_id, owner_id, str(exc))


async def _execute_document_ingest(
    job_id: UUID,
    document_id: Optional[UUID],
    owner_id: UUID,
) -> None:
    """Run document ingestion for a ``document_ingest`` job.

    Delegates to ``ingest_document()`` from ``ingestion_service.py``.
    On success, marks the job **COMPLETED**.
    On failure, calls ``_handle_job_failure()`` which decides retry vs. fail.
    """
    if document_id is None:
        await _mark_job_terminal(job_id, "FAILED", owner_id, "document_ingest job has no document_id")
        return

    logger.info("[DOC_INGEST] Starting ingest doc=%s job=%s", document_id, job_id)

    try:
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)
            await ingest_document(document_id, db)

        # ── Success — mark COMPLETED ───────────────────────────────────────
        await _mark_job_terminal(job_id, "COMPLETED", owner_id)
        logger.info("[DOC_INGEST] Completed doc=%s job=%s", document_id, job_id)

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        logger.error("[DOC_INGEST] Failed doc=%s job=%s: %s", document_id, job_id, exc)
        await _handle_job_failure(job_id, owner_id, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4 — Extended Job Handlers
# ═══════════════════════════════════════════════════════════════════════════════

async def _execute_embedding(
    job_id: UUID,
    document_id: Optional[UUID],
    owner_id: UUID,
) -> None:
    """Regenerate embeddings for a document (``embedding`` job).

    Delegates to ``reembed_document()`` from ``reembedding_service.py``.
    """
    if document_id is None:
        await _mark_job_terminal(job_id, "FAILED", owner_id, "embedding job has no document_id")
        return

    logger.info("[EMBEDDING] Starting reembed doc=%s job=%s", document_id, job_id)

    try:
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)
            await reembed_document(db, doc_id=document_id)

        await _mark_job_terminal(job_id, "COMPLETED", owner_id)
        logger.info("[EMBEDDING] Completed doc=%s job=%s", document_id, job_id)

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        logger.error("[EMBEDDING] Failed doc=%s job=%s: %s", document_id, job_id, exc)
        await _handle_job_failure(job_id, owner_id, str(exc))


async def _execute_image_process(
    job_id: UUID,
    document_id: Optional[UUID],
    owner_id: UUID,
) -> None:
    """Analyze an image document (``image_process`` job).

    Queries the ``Document`` for its path, then delegates to
    ``analyze_image()`` from ``vision_service.py``.
    """
    if document_id is None:
        await _mark_job_terminal(job_id, "FAILED", owner_id, "image_process job has no document_id")
        return

    logger.info("[IMAGE_PROCESS] Starting analysis doc=%s job=%s", document_id, job_id)

    try:
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)

            # Resolve Document path
            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result.scalar_one_or_none()
            if doc is None or not doc.path:
                await _mark_job_terminal(
                    job_id, "FAILED", owner_id,
                    f"Document {document_id} not found or has no path",
                )
                return

            image_path = doc.path
            question: str = "Analyze this image and describe its contents in detail."

        # Run analysis outside the DB session
        description: str = await analyze_image(image_path, question)

        # Store result in job payload
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)
            await db.execute(
                text("""
                    UPDATE processing_jobs
                    SET payload = jsonb_set(
                        COALESCE(payload, '{}'::jsonb),
                        '{analysis_result}',
                        :result::jsonb
                    ),
                    updated_at = now()
                    WHERE id = :job_id
                """),
                {"job_id": job_id, "result": json.dumps({"description": description})},
            )
            await db.commit()

        await _mark_job_terminal(job_id, "COMPLETED", owner_id)
        logger.info("[IMAGE_PROCESS] Completed doc=%s job=%s", document_id, job_id)

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        logger.error("[IMAGE_PROCESS] Failed doc=%s job=%s: %s", document_id, job_id, exc)
        await _handle_job_failure(job_id, owner_id, str(exc))


async def _execute_audio_transcribe(
    job_id: UUID,
    document_id: Optional[UUID],
    owner_id: UUID,
) -> None:
    """Transcribe an audio file (``audio_transcribe`` job).

    Queries the ``Document`` for its path and mime_type, then delegates to
    ``transcribe_file()`` from ``transcription_service.py``.
    """
    if document_id is None:
        await _mark_job_terminal(job_id, "FAILED", owner_id, "audio_transcribe job has no document_id")
        return

    logger.info("[AUDIO_TRANSCRIBE] Starting doc=%s job=%s", document_id, job_id)

    try:
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)

            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result.scalar_one_or_none()
            if doc is None or not doc.path:
                await _mark_job_terminal(
                    job_id, "FAILED", owner_id,
                    f"Document {document_id} not found or has no path",
                )
                return

            file_path = doc.path
            mime_type = doc.mime_type or "audio/mpeg"

        transcript: str = await transcribe_file(file_path, mime_type)

        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)
            await db.execute(
                text("""
                    UPDATE processing_jobs
                    SET payload = jsonb_set(
                        COALESCE(payload, '{}'::jsonb),
                        '{transcription_result}',
                        :result::jsonb
                    ),
                    updated_at = now()
                    WHERE id = :job_id
                """),
                {"job_id": job_id, "result": json.dumps({"transcript": transcript})},
            )
            await db.commit()

        await _mark_job_terminal(job_id, "COMPLETED", owner_id)
        logger.info("[AUDIO_TRANSCRIBE] Completed doc=%s job=%s", document_id, job_id)

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        logger.error("[AUDIO_TRANSCRIBE] Failed doc=%s job=%s: %s", document_id, job_id, exc)
        await _handle_job_failure(job_id, owner_id, str(exc))


async def _execute_video_transcribe(
    job_id: UUID,
    document_id: Optional[UUID],
    owner_id: UUID,
) -> None:
    """Transcribe a video file (``video_transcribe`` job).

    Identical pattern to ``_execute_audio_transcribe`` — extracts audio
    track via ``transcribe_file()``.
    """
    if document_id is None:
        await _mark_job_terminal(job_id, "FAILED", owner_id, "video_transcribe job has no document_id")
        return

    logger.info("[VIDEO_TRANSCRIBE] Starting doc=%s job=%s", document_id, job_id)

    try:
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)

            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result.scalar_one_or_none()
            if doc is None or not doc.path:
                await _mark_job_terminal(
                    job_id, "FAILED", owner_id,
                    f"Document {document_id} not found or has no path",
                )
                return

            file_path = doc.path
            mime_type = doc.mime_type or "video/mp4"

        transcript: str = await transcribe_file(file_path, mime_type)

        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)
            await db.execute(
                text("""
                    UPDATE processing_jobs
                    SET payload = jsonb_set(
                        COALESCE(payload, '{}'::jsonb),
                        '{transcription_result}',
                        :result::jsonb
                    ),
                    updated_at = now()
                    WHERE id = :job_id
                """),
                {"job_id": job_id, "result": json.dumps({"transcript": transcript})},
            )
            await db.commit()

        await _mark_job_terminal(job_id, "COMPLETED", owner_id)
        logger.info("[VIDEO_TRANSCRIBE] Completed doc=%s job=%s", document_id, job_id)

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        logger.error("[VIDEO_TRANSCRIBE] Failed doc=%s job=%s: %s", document_id, job_id, exc)
        await _handle_job_failure(job_id, owner_id, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 8 — Workflow & Agent Handlers
# ═══════════════════════════════════════════════════════════════════════════════

async def _execute_workflow(
    job_id: UUID,
    document_id: Optional[UUID],
    owner_id: UUID,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """Execute a document workflow (``workflow`` job).

    Delegates to ``OrchestratorAgent`` from ``agent_orchestration_service.py``.
    Expects ``workflow_type`` in payload (e.g. ``"document_review"``).
    """
    resource_id = document_id or job_id
    logger.info("[WORKFLOW] Starting workflow job=%s doc=%s", job_id, resource_id)

    try:
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)

            workflow_type: str = "document_review"
            if payload and isinstance(payload, dict):
                workflow_type = payload.get("workflow_type", workflow_type)

            agent = OrchestratorAgent(db)
            result: str = await agent.execute_workflow(
                workflow_type=workflow_type,
                input_text=payload.get("input_text", "") if payload else "",
                user_id=owner_id,
                document_id=resource_id,
            )

            # Store result in payload
            await db.execute(
                text("""
                    UPDATE processing_jobs
                    SET payload = jsonb_set(
                        COALESCE(payload, '{}'::jsonb),
                        '{workflow_result}',
                        :result::jsonb
                    ),
                    updated_at = now()
                    WHERE id = :job_id
                """),
                {"job_id": job_id, "result": json.dumps({"output": result})},
            )
            await db.commit()

        await _mark_job_terminal(job_id, "COMPLETED", owner_id)
        logger.info("[WORKFLOW] Completed job=%s doc=%s", job_id, resource_id)

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        logger.error("[WORKFLOW] Failed job=%s: %s", job_id, exc)
        await _handle_job_failure(job_id, owner_id, str(exc))


async def _execute_agent_run(
    job_id: UUID,
    document_id: Optional[UUID],
    owner_id: UUID,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """Run an agent execution (``agent_run`` job).

    Delegates to ``AgentExecutor`` from ``agent_executor_service.py``.
    Expects ``agent_id`` and ``input_text`` in payload.
    """
    if not payload or "agent_id" not in payload:
        await _mark_job_terminal(
            job_id, "FAILED", owner_id,
            "agent_run job requires payload.agent_id",
        )
        return

    logger.info("[AGENT_RUN] Starting agent job=%s", job_id)

    try:
        agent_id: int = payload["agent_id"]
        input_text: str = payload.get("input_text", "")
        session_id: Optional[str] = payload.get("session_id")

        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)

            executor = AgentExecutor(db)
            execution_id: Optional[int] = await executor.create_execution(
                agent_id=agent_id,
                user_id=owner_id,
                input_text=input_text,
                session_id=session_id,
            )

            if execution_id is not None:
                await db.execute(
                    text("""
                        UPDATE processing_jobs
                        SET payload = jsonb_set(
                            COALESCE(payload, '{}'::jsonb),
                            '{agent_result}',
                            :result::jsonb
                        ),
                        updated_at = now()
                        WHERE id = :job_id
                    """),
                    {
                        "job_id": job_id,
                        "result": json.dumps({"execution_id": execution_id}),
                    },
                )
                await db.commit()

        await _mark_job_terminal(job_id, "COMPLETED", owner_id)
        logger.info("[AGENT_RUN] Completed job=%s execution=%s", job_id, execution_id)

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        logger.error("[AGENT_RUN] Failed job=%s: %s", job_id, exc)
        await _handle_job_failure(job_id, owner_id, str(exc))


async def _execute_agent_research(
    job_id: UUID,
    document_id: Optional[UUID],
    owner_id: UUID,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """Run a research agent (``agent_research`` job).

    Same pattern as ``_execute_agent_run`` but with a fixed ``agent_id``
    for the research agent or delegated by payload.
    """
    research_agent_id: int = (payload or {}).get("agent_id", 1)  # default research agent
    research_input: str = (payload or {}).get("input_text", "Perform research on the given context.")

    logger.info("[AGENT_RESEARCH] Starting research job=%s", job_id)

    try:
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)

            executor = AgentExecutor(db)
            execution_id: Optional[int] = await executor.create_execution(
                agent_id=research_agent_id,
                user_id=owner_id,
                input_text=research_input,
                session_id=payload.get("session_id") if payload else None,
            )

            if execution_id is not None:
                await db.execute(
                    text("""
                        UPDATE processing_jobs
                        SET payload = jsonb_set(
                            COALESCE(payload, '{}'::jsonb),
                            '{agent_result}',
                            :result::jsonb
                        ),
                        updated_at = now()
                        WHERE id = :job_id
                    """),
                    {
                        "job_id": job_id,
                        "result": json.dumps({"execution_id": execution_id}),
                    },
                )
                await db.commit()

        await _mark_job_terminal(job_id, "COMPLETED", owner_id)
        logger.info("[AGENT_RESEARCH] Completed job=%s execution=%s", job_id, execution_id)

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        logger.error("[AGENT_RESEARCH] Failed job=%s: %s", job_id, exc)
        await _handle_job_failure(job_id, owner_id, str(exc))


async def _execute_agent_kg(
    job_id: UUID,
    document_id: Optional[UUID],
    owner_id: UUID,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """Run a knowledge-graph agent (``agent_kg`` job).

    Delegates to ``AgentExecutor`` from ``agent_executor_service.py``.
    Expects payload with knowledge-graph related parameters.
    """
    kg_agent_id: int = (payload or {}).get("agent_id", 2)  # default KG agent
    kg_input: str = (payload or {}).get(
        "input_text", "Extract and build knowledge graph from the document."
    )

    logger.info("[AGENT_KG] Starting knowledge-graph job=%s", job_id)

    try:
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)

            executor = AgentExecutor(db)
            execution_id: Optional[int] = await executor.create_execution(
                agent_id=kg_agent_id,
                user_id=owner_id,
                input_text=kg_input,
                session_id=payload.get("session_id") if payload else None,
            )

            if execution_id is not None:
                await db.execute(
                    text("""
                        UPDATE processing_jobs
                        SET payload = jsonb_set(
                            COALESCE(payload, '{}'::jsonb),
                            '{agent_result}',
                            :result::jsonb
                        ),
                        updated_at = now()
                        WHERE id = :job_id
                    """),
                    {
                        "job_id": job_id,
                        "result": json.dumps({"execution_id": execution_id}),
                    },
                )
                await db.commit()

        await _mark_job_terminal(job_id, "COMPLETED", owner_id)
        logger.info("[AGENT_KG] Completed job=%s execution=%s", job_id, execution_id)

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        logger.error("[AGENT_KG] Failed job=%s: %s", job_id, exc)
        await _handle_job_failure(job_id, owner_id, str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# Error Handling & Retry Logic
# ═══════════════════════════════════════════════════════════════════════════════

async def _handle_job_failure(job_id: UUID, owner_id: UUID, error: str) -> None:
    """Decide whether to retry or fail a job.

    If ``retry_count < max_retries``:
        1. Transition to RETRYING
        2. Immediately re-enqueue to QUEUED for re-claiming
    Otherwise:
        Transition to FAILED (terminal).

    This function is idempotent — if the job is already in a terminal state,
    the UPDATE is a no-op.
    """
    try:
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)

            # ── Read current retry state ───────────────────────────────────
            row = await db.execute(
                text("""
                    SELECT retry_count, max_retries
                    FROM processing_jobs
                    WHERE id = :job_id
                """),
                {"job_id": job_id},
            )
            job_row = row.one_or_none()
            if job_row is None:
                logger.warning("[HANDLE_FAILURE] Job %s not found — skipping", job_id)
                return

            retry_count: int = job_row.retry_count
            max_retries: int = job_row.max_retries

            if retry_count < max_retries:
                # ── RETRY path ─────────────────────────────────────────────
                new_retry_count = retry_count + 1
                await db.execute(
                    text("""
                        UPDATE processing_jobs
                        SET job_state   = 'RETRYING',
                            retry_count = :retry_count,
                            last_error  = :error,
                            worker_id   = NULL,
                            claimed_at  = NULL,
                            updated_at  = now()
                        WHERE id = :job_id
                    """),
                    {
                        "job_id": job_id,
                        "retry_count": new_retry_count,
                        "error": error,
                    },
                )
                await db.commit()

                # Immediately re-enqueue to QUEUED so the next poll cycle
                # can pick it up (with backoff handled by the retry_count).
                await db.execute(
                    text("""
                        UPDATE processing_jobs
                        SET job_state = 'QUEUED', updated_at = now()
                        WHERE id = :job_id
                    """),
                    {"job_id": job_id},
                )
                await db.commit()

                logger.info(
                    "[HANDLE_FAILURE] Job %s retry %d/%d after error: %s",
                    job_id, new_retry_count, max_retries, error,
                )

            else:
                # ── FAIL path (exhausted retries) ──────────────────────────
                await db.execute(
                    text("""
                        UPDATE processing_jobs
                        SET job_state     = 'FAILED',
                            last_error    = :error,
                            completed_at  = now(),
                            worker_id     = NULL,
                            claimed_at    = NULL,
                            updated_at    = now()
                        WHERE id = :job_id
                    """),
                    {"job_id": job_id, "error": error},
                )
                await db.commit()
                logger.error(
                    "[HANDLE_FAILURE] Job %s FAILED after %d/%d retries: %s",
                    job_id, retry_count, max_retries, error,
                )

    except Exception as exc:
        logger.error("[HANDLE_FAILURE] Failed for job %s: %s", job_id, exc, exc_info=True)


async def _mark_job_terminal(
    job_id: UUID,
    state: str,
    owner_id: UUID,
    error: Optional[str] = None,
) -> None:
    """Mark a job as reaching a terminal state.

    Terminal states: ``COMPLETED``, ``FAILED``, ``CANCELLED``.

    Args:
        job_id: The job to mark.
        state: One of the terminal state values.
        owner_id: For RLS context.
        error: Optional error message (only written for FAILED/CANCELLED).
    """
    if state not in _TERMINAL_STATES:
        logger.warning("[MARK_TERMINAL] %s is not a terminal state — ignoring", state)
        return

    try:
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)

            await db.execute(
                text("""
                    UPDATE processing_jobs
                    SET job_state     = :state,
                        completed_at  = now(),
                        last_error    = COALESCE(:error, last_error),
                        worker_id     = NULL,
                        claimed_at    = NULL,
                        updated_at    = now()
                    WHERE id = :job_id
                      AND job_state NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')
                """),
                {
                    "job_id": job_id,
                    "state": state,
                    "error": error,
                },
            )
            await db.commit()

        logger.info("[MARK_TERMINAL] Job %s → %s", job_id, state)

    except Exception as exc:
        logger.error("[MARK_TERMINAL] Failed for job %s: %s", job_id, exc, exc_info=True)


async def _reclaim_job(
    job_id: UUID,
    owner_id: UUID,
    reason: str,
) -> None:
    """Reset a CLAIMED or PROCESSING job back to QUEUED.

    Used during graceful shutdown to ensure jobs are not orphaned.
    Also used when a job's task is cancelled mid-flight.

    Args:
        job_id: The job to reclaim.
        owner_id: For RLS context.
        reason: Short explanation stored in ``last_error``.
    """
    try:
        async with AsyncSessionLocal() as db:
            await set_rls_context(db, owner_id)
            await db.execute(
                text("""
                    UPDATE processing_jobs
                    SET job_state   = 'QUEUED',
                        worker_id   = NULL,
                        claimed_at  = NULL,
                        last_error  = :reason,
                        updated_at  = now()
                    WHERE id = :job_id
                      AND job_state IN ('CLAIMED', 'PROCESSING')
                """),
                {"job_id": job_id, "reason": reason},
            )
            await db.commit()
    except Exception as exc:
        logger.error("[RECLAIM_JOB] Failed for job %s: %s", job_id, exc, exc_info=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Heartbeat
# ═══════════════════════════════════════════════════════════════════════════════

async def _heartbeat_loop() -> None:
    """Periodically refresh ``claimed_at`` for all PROCESSING jobs.

    This heartbeat acts as a **liveness signal**.  The ``reclaim_orphaned_jobs()``
    function checks ``claimed_at`` vs. ``now()`` — any job ``CLAIMED`` longer
    than the heartbeat timeout (60 s) is considered orphaned and reset to
    QUEUED.

    The loop runs every ``_HEARTBEAT_INTERVAL`` (15 s) and touches only jobs
    owned by **this** worker.
    """
    logger.info("[HEARTBEAT] Started (interval=%ss)", _HEARTBEAT_INTERVAL)

    while not _shutdown_event.is_set():
        try:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)

            async with AsyncSessionLocal() as db:
                # No RLS context needed — the UPDATE only touches jobs
                # owned by this worker (worker_id filter), which is
                # allowed by the processing_jobs RLS bypass policy.
                # Defensive: ensure worker_id is a non-empty string before querying
                w_id = str(_WORKER_ID).strip()
                if not w_id:
                    logger.warning("[HEARTBEAT] Empty worker_id — skipping heartbeat")
                    continue

                result = await db.execute(
                    text("""
                        UPDATE processing_jobs
                        SET claimed_at = now(),
                            updated_at = now()
                        WHERE worker_id = :worker_id
                          AND job_state = 'PROCESSING'
                    """),
                    {"worker_id": w_id},
                )
                await db.commit()  # Persist the heartbeat timestamp
                if result.rowcount > 0:
                    logger.debug(
                        "[HEARTBEAT] Refreshed %d PROCESSING job(s) for worker %s",
                        result.rowcount, w_id,
                    )

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("[HEARTBEAT] Error: %s", exc, exc_info=True)

    logger.info("[HEARTBEAT] Stopped")


# ═══════════════════════════════════════════════════════════════════════════════
# Dead Worker Reclamation
# ═══════════════════════════════════════════════════════════════════════════════

async def _reclaim_loop() -> None:
    """Periodically call ``reclaim_orphaned_jobs()`` to detect dead workers.

    This is a **safety net** — it runs independently of the heartbeat and
    resets CLAIMED jobs whose ``claimed_at`` exceeds the timeout back to
    QUEUED so that other workers can pick them up.

    In a multi-worker deployment, **every** worker runs this loop, but the
    database function is idempotent — only the first caller to process a
    given orphaned job will actually reclaim it.
    """
    logger.info("[RECLAIM] Started (interval=%ss, timeout=%s)", _RECLAIM_INTERVAL, _RECLAIM_TIMEOUT)

    while not _shutdown_event.is_set():
        try:
            await asyncio.sleep(_RECLAIM_INTERVAL)

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("SELECT reclaim_orphaned_jobs(:timeout)"),
                    {"timeout": _RECLAIM_TIMEOUT},
                )
                await db.commit()  # Persist the reclamation
                count = result.scalar()
                if count and count > 0:
                    logger.info("[RECLAIM] Reclaimed %d orphaned job(s)", count)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("[RECLAIM] Error: %s", exc, exc_info=True)

    logger.info("[RECLAIM] Stopped")


# ═══════════════════════════════════════════════════════════════════════════════
# Main Poller Loop
# ═══════════════════════════════════════════════════════════════════════════════

async def _poll_cycle() -> bool:
    """Execute a single poll cycle: claim → dispatch → execute.

    Returns:
        ``True`` if a job was claimed, ``False`` if no job was available.
    """
    try:
        # ── Claim ──────────────────────────────────────────────────────────
        async with AsyncSessionLocal() as db:
            job_data = await _call_claim_next_job(db, _SUPPORTED_JOB_TYPES)
            await db.commit()  # Persist the claim — without this, session close rolls it back

        if job_data is None:
            return False  # No eligible job

        raw_job_id: Any = job_data["id"]
        job_id: UUID = UUID(raw_job_id) if isinstance(raw_job_id, str) else raw_job_id

        logger.info("[POLL_CYCLE] Claimed job=%s type=%s", job_id, job_data.get("job_type"))

        # ── Acquire semaphore ──────────────────────────────────────────────
        await _semaphore.acquire()

        # ── Dispatch ───────────────────────────────────────────────────────
        task = asyncio.create_task(_execute_and_release(job_data))
        _active_jobs[job_id] = task

        # Remove from _active_jobs when the task completes (for any reason).
        task.add_done_callback(lambda _t: _active_jobs.pop(job_id, None))

        return True

    except Exception as exc:
        logger.error("[POLL_CYCLE] Error: %s", exc, exc_info=True)
        return False


async def _execute_and_release(job_data: dict[str, Any]) -> None:
    """Execute a job and release the semaphore when done (finally-safe).

    This is the **only** function that should release the semaphore,
    ensuring we never leak a semaphore acquisition.
    """
    try:
        await _execute_job(job_data)
    finally:
        try:
            _semaphore.release()
        except (RuntimeError, ValueError) as exc:
            # Semaphore may have been closed or released too many times;
            # log and suppress so the poller loop isn't killed.
            logger.warning("[EXECUTE_AND_RELEASE] Semaphore release error: %s", exc)


async def _poller_loop() -> None:
    """Main poller loop — runs indefinitely until ``_shutdown_event`` is set.

    Behaviour:
        1. Call ``_poll_cycle()``
        2. If a job was claimed, immediately try again (don't sleep)
        3. If no job was available, sleep ``_POLL_IDLE_INTERVAL`` (1 s)
        4. On unexpected error, sleep ``_POLL_ERROR_INTERVAL`` (5 s) as backoff
    """
    logger.info("[POLLER] Starting poller loop (worker_id=%s, semaphore=%d)", _WORKER_ID, _semaphore._value)

    while not _shutdown_event.is_set():
        try:
            claimed = await _poll_cycle()
            if not claimed:
                await asyncio.sleep(_POLL_IDLE_INTERVAL)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("[POLLER] Unexpected error: %s", exc, exc_info=True)
            await asyncio.sleep(_POLL_ERROR_INTERVAL)

    logger.info("[POLLER] Poller loop stopped (worker_id=%s)", _WORKER_ID)


# ═══════════════════════════════════════════════════════════════════════════════
# Lifecycle Management
# ═══════════════════════════════════════════════════════════════════════════════

async def _reset_in_progress_jobs() -> int:
    """Reset all CLAIMED and PROCESSING jobs owned by this worker to QUEUED.

    Called during graceful shutdown to prevent job orphaning.
    Only affects jobs where ``worker_id = _WORKER_ID``.

    Returns:
        Number of jobs reset.
    """
    count = 0
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("""
                    UPDATE processing_jobs
                    SET job_state   = 'QUEUED',
                        worker_id   = NULL,
                        claimed_at  = NULL,
                        last_error  = 'Worker shutdown: job reset to QUEUED',
                        updated_at  = now()
                    WHERE worker_id = :worker_id
                      AND job_state IN ('CLAIMED', 'PROCESSING')
                """),
                {"worker_id": _WORKER_ID},
            )
            await db.commit()
            count = result.rowcount
            if count > 0:
                logger.info("[SHUTDOWN] Reset %d in-progress job(s) to QUEUED", count)

    except Exception as exc:
        logger.error("[SHUTDOWN] Failed to reset in-progress jobs: %s", exc, exc_info=True)

    return count


async def start_poller() -> None:
    """Start the job poller and its ancillary loops (idempotent).

    Creates three background tasks:
    1. **Poller loop** — claims and dispatches jobs
    2. **Heartbeat loop** — refreshes ``claimed_at`` every 15 s
    3. **Reclaim loop** — calls ``reclaim_orphaned_jobs()`` every 60 s

    Safe to call multiple times — subsequent calls are no-ops if the
    poller is already running.

    Should be called during application startup, e.g.::

        # In app/main.py startup event:
        from app.services.job_poller import start_poller
        await start_poller()
    """
    global _poller_task, _heartbeat_task, _reclaim_task

    if _poller_task is not None and not _poller_task.done():
        logger.info("[POLLER] Already running (task is active)")
        return

    # Reset the shutdown event so loops can start fresh.
    _shutdown_event.clear()

    try:
        _poller_task = asyncio.create_task(
            _poller_loop(), name="job_poller_loop"
        )
        _heartbeat_task = asyncio.create_task(
            _heartbeat_loop(), name="job_poller_heartbeat"
        )
        _reclaim_task = asyncio.create_task(
            _reclaim_loop(), name="job_poller_reclaim"
        )

        logger.info(
            "[POLLER] Started (worker_id=%s, semaphore=%d, supported_types=%s)",
            _WORKER_ID,
            _semaphore._value,
            _SUPPORTED_JOB_TYPES,
        )

    except Exception as exc:
        logger.error("[POLLER] Failed to start: %s", exc, exc_info=True)
        raise


async def stop_poller() -> None:
    """Gracefully shut down the job poller.

    Order of operations:
    1. Set the shutdown event (signals all loops to stop)
    2. Wait for active jobs to finish (up to ``_SHUTDOWN_WAIT_TIMEOUT``)
    3. Cancel any remaining in-flight tasks
    4. Reset CLAIMED/PROCESSING jobs back to QUEUED

    Safe to call even if the poller was never started.
    """
    logger.info("[POLLER] Stopping poller...")
    _shutdown_event.set()

    # ── Cancel ancillary loops ─────────────────────────────────────────────
    for task_ref, name in [
        (_heartbeat_task, "heartbeat"),
        (_reclaim_task, "reclaim"),
    ]:
        if task_ref is not None and not task_ref.done():
            task_ref.cancel()
            logger.debug("[POLLER] Cancelled %s task", name)

    # ── Wait for active jobs ───────────────────────────────────────────────
    if _active_jobs:
        active_count = len(_active_jobs)
        logger.info("[POLLER] Waiting for %d active job(s) (timeout=%ss)...", active_count, _SHUTDOWN_WAIT_TIMEOUT)

        try:
            done, pending = await asyncio.wait(
                list(_active_jobs.values()),
                timeout=_SHUTDOWN_WAIT_TIMEOUT,
            )
            if pending:
                logger.warning(
                    "[POLLER] %d job(s) still running after timeout — cancelling", len(pending)
                )
                for task in pending:
                    task.cancel()

                # Give cancelled tasks a moment to clean up
                await asyncio.sleep(0.5)

        except Exception as exc:
            logger.error("[POLLER] Error during shutdown wait: %s", exc, exc_info=True)

    # ── Cancel poller task ─────────────────────────────────────────────────
    if _poller_task is not None and not _poller_task.done():
        _poller_task.cancel()
        logger.debug("[POLLER] Cancelled poller task")

    # ── Reset in-progress jobs ─────────────────────────────────────────────
    await _reset_in_progress_jobs()

    logger.info("[POLLER] Stopped")


# ═══════════════════════════════════════════════════════════════════════════════
# Health Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def poller_running() -> bool:
    """Check whether the poller background task is currently active.

    Returns:
        ``True`` if the poller task exists and is not done.
    """
    return _poller_task is not None and not _poller_task.done()


def active_job_count() -> int:
    """Return the number of jobs currently being executed.

    Returns:
        Count of entries in ``_active_jobs``.
    """
    return len(_active_jobs)


def current_worker_id() -> str:
    """Return this worker's unique identifier.

    The identifier is ``worker-{hostname}-{pid}`` and uniquely identifies
    this process across the cluster.

    Returns:
        The worker ID string.
    """
    return _WORKER_ID


# ═══════════════════════════════════════════════════════════════════════════════
# Sync Wrappers (backward compatibility)
# ═══════════════════════════════════════════════════════════════════════════════

def create_job_sync(
    job_type: str,
    *,
    document_id: Optional[UUID] = None,
    owner_id: Optional[UUID] = None,
    priority: int = 0,
    **kwargs: Any,
) -> Optional[UUID]:
    """Synchronous wrapper around ``create_job()``.

    Intended for callers that are not in an async context (e.g., synchronous
    background threads).  Creates a temporary event loop if one does not exist.

    Prefer ``await create_job()`` in async contexts.

    Args:
        Same as ``create_job()``, but ``document_id`` and ``owner_id`` are
        keyword-only (except ``job_type`` which is positional).

    Returns:
        The UUID of the created job, or ``None`` on failure.
    """
    coro = create_job(
        job_type,
        document_id=document_id,
        owner_id=owner_id,
        priority=priority,
        **kwargs,
    )

    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            # We are inside a running event loop — schedule and return a
            # sentinel.  The caller should use await instead.
            asyncio.ensure_future(coro)
            logger.warning(
                "[CREATE_JOB_SYNC] Running event loop detected — "
                "use await create_job() instead of create_job_sync()"
            )
            return None

        # Should not reach here (get_running_loop raises if no loop),
        # but handle gracefully.
        return asyncio.run(coro)

    except RuntimeError:
        # No event loop in this thread — create one.
        return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════════════════════
# Module Exports
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Core API
    "create_job",
    "cancel_job",
    "get_job",
    "list_jobs",
    # Lifecycle
    "start_poller",
    "stop_poller",
    # Health
    "poller_running",
    "active_job_count",
    "current_worker_id",
    # Utilities
    "set_rls_context",
    "create_job_sync",
]
