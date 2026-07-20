"""
job_models.py — Persistent Processing-Job Model

Maps to the ``processing_jobs`` table in PostgreSQL.
Defines ``ProcessingJob`` ORM model and the ``VALID_JOB_TYPES`` /
``VALID_JOB_STATES`` constants consumed by ``job_poller.py``,
``bootstrap_service.py``, and the Alembic migration environment.
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Boolean,
    Uuid, text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

VALID_JOB_TYPES: frozenset = frozenset({
    "document_ingest",
    "embedding",
    "image_process",
    "audio_transcribe",
    "video_transcribe",
    "workflow",
    "agent_run",
    "agent_research",
    "agent_kg",
})
"""All recognised processing-job types."""

VALID_JOB_STATES: frozenset = frozenset({
    "PENDING",
    "QUEUED",
    "CLAIMED",
    "PROCESSING",
    "PAUSED",
    "RETRYING",
    "FAILED",
    "COMPLETED",
    "CANCELLED",
})
"""All valid job-lifecycle states (matches the DB CHECK constraint)."""


# ═══════════════════════════════════════════════════════════════════════════════
# ProcessingJob ORM Model
# ═══════════════════════════════════════════════════════════════════════════════

class ProcessingJob(Base):
    """A single background-processing job.

    Created by ``job_poller.create_job()``, claimed by the SECURITY DEFINER
    function ``claim_next_job()``, and executed by a worker dispatcher in
    ``job_poller._execute_job()``.
    """

    __tablename__ = "processing_jobs"
    __table_args__ = {"extend_existing": True}

    # ── Primary key ────────────────────────────────────────────────────────
    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
        index=True,
    )

    # ── Job identity ───────────────────────────────────────────────────────
    job_type  = Column(String(100), nullable=False, index=True)
    job_state = Column(String(50),  nullable=False, default="QUEUED", index=True)

    # ── Priority & ownership ───────────────────────────────────────────────
    priority   = Column(Integer, nullable=False, default=0)
    owner_id   = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    document_id = Column(Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    asset_id    = Column(Uuid(as_uuid=True), ForeignKey("knowledge_assets.id", ondelete="SET NULL"), nullable=True)

    # ── Worker tracking ────────────────────────────────────────────────────
    worker_id  = Column(String(200), nullable=True)

    # ── Retry / lifecycle ──────────────────────────────────────────────────
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)

    # ── Timestamps ─────────────────────────────────────────────────────────
    created_at   = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at   = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    claimed_at   = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # ── Error / diagnostics ────────────────────────────────────────────────
    last_error = Column(Text, nullable=True)

    # ── Control flags ──────────────────────────────────────────────────────
    pause_requested  = Column(Boolean, nullable=False, default=False)
    cancel_requested = Column(Boolean, nullable=False, default=False)

    # ── Checkpoint / progress ──────────────────────────────────────────────
    checkpoint = Column(Text, nullable=True)

    # ── Payload ────────────────────────────────────────────────────────────
    payload = Column("payload", Text, nullable=True)
    """JSON-encoded payload stored as TEXT (cast to jsonb at INSERT time)."""

    # ── Relationships (read-only direction; reverse relations not defined
    #    on User/Document yet) ──────────────────────────────────────────────
    owner    = relationship("User")
    document = relationship("Document")

    def __repr__(self) -> str:
        return (
            f"<ProcessingJob id={self.id} type={self.job_type} "
            f"state={self.job_state}>"
        )
