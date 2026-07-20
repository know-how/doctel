"""
database.py — DocTel Database Layer

Provides:
- PostgreSQL connection pooling via asyncpg
- Health verification at startup
- Transaction-safe operations
"""

from __future__ import annotations

import logging
import time
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

logger = logging.getLogger(__name__)

# ── Connection Pool Configuration ──────────────────────────────────────────

def _build_engine() -> AsyncEngine:
    """Create the async engine with PostgreSQL connection pooling."""
    driver = settings.db_url.split("://")[0] if "://" in settings.db_url else settings.db_url
    engine_kwargs = {
        "echo": False,
        "pool_size": 20,
        "max_overflow": 10,
        "pool_recycle": 3600,
        "pool_timeout": 30,
    }

    logger.info("Driver: %s pool_size=%s max_overflow=%s", driver, engine_kwargs["pool_size"], engine_kwargs["max_overflow"])
    return create_async_engine(settings.db_url, **engine_kwargs)


engine = _build_engine()

Base = declarative_base()

# Import config models so they register with Base.metadata
from app.db import config_models  # noqa: F401
# Import enterprise models for Vision 2.0 schema expansion
from app.db import enterprise_models  # noqa: F401
# Import persistent job processing model
from app.db import job_models  # noqa: F401

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# ── Health Verification ─────────────────────────────────────────────────────

class DatabaseHealth:
    """Tracks database connection health status."""

    def __init__(self):
        self.connected: bool = False
        self.tables_exist: bool = False
        self.migrations_complete: bool = False
        self.last_checked: Optional[float] = None
        self.error: Optional[str] = None
        self.latency_ms: Optional[float] = None
        self.pool_size: Optional[int] = None
        self.active_connections: Optional[int] = None

    @property
    def healthy(self) -> bool:
        return self.connected and self.tables_exist and self.migrations_complete

    def to_dict(self) -> dict:
        return {
            "connected": self.connected,
            "tables_exist": self.tables_exist,
            "migrations_complete": self.migrations_complete,
            "healthy": self.healthy,
            "last_checked": self.last_checked,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "pool_size": self.pool_size,
            "active_connections": self.active_connections,
        }


db_health = DatabaseHealth()


async def verify_database_health() -> DatabaseHealth:
    """Verify database connectivity, tables, and migrations."""
    start = time.monotonic()
    db_health.last_checked = time.time()

    # 1. Check connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_health.connected = True
        db_health.error = None
    except Exception as e:
        db_health.connected = False
        db_health.error = f"Connection failed: {e}"
        db_health.latency_ms = (time.monotonic() - start) * 1000
        logger.error("Database health check FAILED: %s", e)
        return db_health

    db_health.latency_ms = round((time.monotonic() - start) * 1000, 2)

    # 2. Check tables exist
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
            ))
            row = result.fetchone()
            table_count = row[0] if row else 0
        db_health.tables_exist = table_count >= 21
        if not db_health.tables_exist:
            db_health.error = f"Only {table_count} tables found (expected >= 21)"
    except Exception as e:
        db_health.tables_exist = False
        db_health.error = f"Table check failed: {e}"

    # 3. Track pool info
    try:
        pool = engine.pool
        if hasattr(pool, 'size'):
            db_health.pool_size = pool.size()
        if hasattr(pool, 'checkedin'):
            db_health.active_connections = pool.checkedin()
    except Exception:
        pass

    db_health.migrations_complete = db_health.tables_exist

    # ── Print full verification to console ────────────────────────────────
    print("=" * 60)
    print("  DATABASE HEALTH VERIFICATION")
    print("=" * 60)
    print(f"  Connected:      {db_health.connected}")
    print(f"  Tables exist:   {db_health.tables_exist} (expected >= 21)")
    print(f"  Migrations OK:  {db_health.migrations_complete}")
    print(f"  Latency:        {db_health.latency_ms} ms")
    print(f"  Pool size:      {db_health.pool_size}")
    print(f"  Active conns:   {db_health.active_connections}")
    print(f"  Error:          {db_health.error or 'None'}")
    print(f"  Overall health: {'[OK] HEALTHY' if db_health.healthy else '[FAIL] UNHEALTHY'}")
    print("=" * 60)

    logger.info(
        "Database health: connected=%s tables=%s latency=%sms",
        db_health.connected, db_health.tables_exist, db_health.latency_ms,
    )
    if db_health.connected and db_health.tables_exist:
        logger.info("Database Connected Successfully")
    return db_health

async def init_db() -> DatabaseHealth:
    """Initialize database: apply schema, seed admin, verify health."""
    from .models import User
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _auto_migrate_columns(conn)
        await _seed_lookup_tables(conn)

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(username="admin", ec_number="admin", email="", display_name="Admin", role="admin")
            session.add(admin)
            await session.commit()

    # Repair PostgreSQL sequences that may drift after data migration
    await _repair_sequences()
    await verify_database_health()
    return db_health


async def _repair_sequences():
    """Repair known PostgreSQL sequences that may drift from MAX(id).

    During MySQL -> PostgreSQL migration, sequences start at 1 while tables
    already contain rows with IDs >= 1.  This function resets each known
    auto-increment sequence to MAX(id)+1 so INSERTs don't hit PK conflicts.

    Safe to call on every restart — ALTER SEQUENCE is idempotent.
    """
    tables_seq = {
        "ai_models": "ai_models_id_seq",
        "system_config": "system_config_id_seq",
        "task_mappings": "task_mappings_id_seq",
        "health_records": "health_records_id_seq",
        "sync_logs": "sync_logs_id_seq",
        "audit_logs": "audit_logs_id_seq",
    }
    try:
        async with engine.connect() as conn:
            for table, seq in tables_seq.items():
                try:
                    result = await conn.execute(
                        text(f"SELECT MAX(id) FROM {table}")
                    )
                    row = result.fetchone()
                    max_id = row[0] if row and row[0] is not None else 0
                    next_val = max_id + 1
                    await conn.execute(
                        text(f"ALTER SEQUENCE {seq} RESTART WITH {next_val}")
                    )
                    logger.debug("Sequence %s reset to %d (MAX=%s)", seq, next_val, max_id)
                except Exception as e:
                    logger.warning("Could not repair sequence %s: %s", seq, e)
            await conn.commit()
        logger.info("PostgreSQL sequences repaired")
    except Exception as e:
        logger.warning("Could not repair sequences: %s", e)


async def _auto_migrate_columns(conn):
    """Add columns that may be missing because create_all does not ALTER existing tables.

    Each statement uses IF NOT EXISTS / IF NOT NULL so it is safe to re-run.
    """
    stmts = [
        # Processing control v1 (added to Document model after table creation)
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_state VARCHAR(20) DEFAULT 'UPLOADED'",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_step VARCHAR(50) DEFAULT ''",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS pause_requested BOOLEAN DEFAULT FALSE",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS cancel_requested BOOLEAN DEFAULT FALSE",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS checkpoint TEXT DEFAULT NULL",
        # Embedding governance v1 (added to Document model after table creation)
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_provider VARCHAR(128) DEFAULT NULL",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMPTZ DEFAULT NULL",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_version VARCHAR(32) DEFAULT NULL",
        # Embedding governance v1 (added to Embedding model after table creation)
        "ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS model_name VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS provider VARCHAR(128) DEFAULT NULL",
        "ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS dimensions INTEGER DEFAULT NULL",
        # Processing control indexes
        "CREATE INDEX IF NOT EXISTS idx_documents_processing_state ON documents(processing_state)",
        "CREATE INDEX IF NOT EXISTS idx_documents_pause_requested ON documents(pause_requested) WHERE pause_requested = TRUE",
        "CREATE INDEX IF NOT EXISTS idx_documents_cancel_requested ON documents(cancel_requested) WHERE cancel_requested = TRUE",
    ]
    for stmt in stmts:
        try:
            await conn.execute(text(stmt))
        except Exception as e:
            logger.warning("Auto-migration: %s — %s", stmt[:80], e)

    # Migrate existing status values to processing_state for rows that still have NULL
    try:
        await conn.execute(text("""
            UPDATE documents
            SET processing_state = CASE status
                WHEN 'uploaded'   THEN 'UPLOADED'
                WHEN 'ingesting'  THEN 'PROCESSING'
                WHEN 'embedded'   THEN 'PROCESSING'
                WHEN 'summarized' THEN 'PROCESSING'
                WHEN 'completed'  THEN 'COMPLETED'
                WHEN 'failed'     THEN 'FAILED'
                ELSE 'UPLOADED'
            END
            WHERE processing_state IS NULL
        """))
        await conn.execute(text("""
            UPDATE documents
            SET processing_step = ingest_step
            WHERE processing_step IS NULL OR processing_step = ''
        """))
    except Exception as e:
        logger.warning("Auto-migration: data backfill — %s", e)


async def _seed_lookup_tables(conn):
    """Seed lookup tables (task_types, roles, departments, model_statuses) if empty."""
    # ── Seed task_types ──────────────────────────────────────────────────
    result = await conn.execute(text("SELECT COUNT(*) as cnt FROM task_types"))
    row = result.one_or_none()
    if row and row[0] == 0:
        await conn.execute(text("""
            INSERT INTO task_types (code, name, description, display_order, is_active) VALUES
            ('chat', 'Chat', 'General conversational AI chat', 1, TRUE),
            ('summary', 'Summary', 'Document and text summarization', 2, TRUE),
            ('extraction', 'Extraction', 'Information extraction from documents', 3, TRUE),
            ('classification', 'Classification', 'Document and content classification', 4, TRUE),
            ('comparison', 'Comparison', 'Compare documents or content', 5, TRUE),
            ('vision', 'Vision', 'Image understanding and analysis', 6, TRUE),
            ('embedding', 'Embedding', 'Text embedding generation', 7, TRUE),
            ('rag', 'RAG', 'Retrieval-Augmented Generation', 8, TRUE),
            ('code_generation', 'Code Generation', 'Generate and analyze code', 9, TRUE)
        """))
        logger.info("Seeded task_types table (%d rows)", 9)

    # ── Seed roles ───────────────────────────────────────────────────────
    result = await conn.execute(text("SELECT COUNT(*) as cnt FROM roles"))
    row = result.one_or_none()
    if row and row[0] == 0:
        await conn.execute(text("""
            INSERT INTO roles (code, name, description, is_system, is_active) VALUES
            ('super_admin', 'Super Administrator', 'Full system access and control', TRUE, TRUE),
            ('admin', 'Administrator', 'System administration privileges', TRUE, TRUE),
            ('manager', 'Manager', 'Department or team management', TRUE, TRUE),
            ('engineer', 'Engineer', 'Technical engineering staff', TRUE, TRUE),
            ('power_user', 'Power User', 'Advanced user with extended permissions', TRUE, TRUE),
            ('general_user', 'General User', 'Standard system user', TRUE, TRUE),
            ('guest', 'Guest', 'Limited access guest user', TRUE, TRUE)
        """))
        logger.info("Seeded roles table (%d rows)", 7)

    # ── Seed departments ─────────────────────────────────────────────────
    result = await conn.execute(text("SELECT COUNT(*) as cnt FROM departments"))
    row = result.one_or_none()
    if row and row[0] == 0:
        await conn.execute(text("""
            INSERT INTO departments (code, name, description, is_active) VALUES
            ('ict', 'ICT', 'Information and Communication Technology', TRUE),
            ('generation', 'Generation', 'Power Generation Department', TRUE),
            ('transmission', 'Transmission', 'Power Transmission Department', TRUE),
            ('distribution', 'Distribution', 'Power Distribution Department', TRUE),
            ('projects', 'Projects', 'Projects and Infrastructure', TRUE),
            ('operations', 'Operations', 'Operations and Maintenance', TRUE),
            ('finance', 'Finance', 'Finance and Accounting', TRUE),
            ('human_resources', 'Human Resources', 'HR and Personnel Management', TRUE),
            ('procurement', 'Procurement', 'Procurement and Supply Chain', TRUE),
            ('customer_services', 'Customer Services', 'Customer Support and Services', TRUE)
        """))
        logger.info("Seeded departments table (%d rows)", 10)

    # ── Seed model_statuses ───────────────────────────────────────────────
    result = await conn.execute(text("SELECT COUNT(*) as cnt FROM model_statuses"))
    row = result.one_or_none()
    if row and row[0] == 0:
        await conn.execute(text("""
            INSERT INTO model_statuses (code, name, description, is_selectable, is_visible, display_order) VALUES
            ('active', 'Active', 'Model is active and available for use', TRUE, TRUE, 1),
            ('inactive', 'Inactive', 'Model is temporarily inactive', FALSE, FALSE, 2),
            ('installed', 'Installed', 'Model is installed locally', TRUE, TRUE, 3),
            ('downloading', 'Downloading', 'Model is currently being downloaded', FALSE, TRUE, 4),
            ('error', 'Error', 'Model has an error state', FALSE, TRUE, 5),
            ('maintenance', 'Maintenance', 'Model is under maintenance', FALSE, TRUE, 6),
            ('retired', 'Retired', 'Model has been retired', FALSE, FALSE, 7)
        """))
        logger.info("Seeded model_statuses table (%d rows)", 7)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
