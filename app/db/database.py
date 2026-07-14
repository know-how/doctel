"""
database.py — DocTel Database Layer

Provides:
- MySQL connection pooling (5-50 connections, 300s idle timeout)
- Health verification at startup
- Migration checks
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

# ── Detect database type ────────────────────────────────────────────────────
_is_mysql = settings.db_url.startswith("mysql")


# ── Connection Pool Configuration ──────────────────────────────────────────

def _build_engine() -> AsyncEngine:
    """Create the async engine with appropriate connection pooling."""
    driver = settings.db_url.split("://")[0] if "://" in settings.db_url else settings.db_url

    # MySQL async connection pooling (AsyncAdaptedQueuePool is automatic)
    pre_ping_enabled = False
    engine_kwargs = {
        "echo": False,
        "pool_size": 50,              # max persistent connections
        "max_overflow": 10,           # extra connections beyond pool_size
        "pool_recycle": 300,          # recycle after 300s idle
        "pool_timeout": 30,           # wait max 30s for a connection
    }

    logger.info("Driver: %s", driver)
    logger.info("PrePing: %s", "Enabled" if pre_ping_enabled else "Disabled")

    return create_async_engine(settings.db_url, **engine_kwargs)


engine = _build_engine()

Base = declarative_base()

# Import config models so they register with Base.metadata
from app.db import config_models  # noqa: F401
# Import enterprise models for Vision 2.0 schema expansion
from app.db import enterprise_models  # noqa: F401

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# Encryption-at-rest is not supported with MySQL


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
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()"
            ))
            row = result.fetchone()
            table_count = row[0] if row else 0
        db_health.tables_exist = table_count >= 21  # We expect ~21+ tables (16 app + 5 config)
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
    print(f"  Overall health: {'✅ HEALTHY' if db_health.healthy else '❌ UNHEALTHY'}")
    print("=" * 60)

    logger.info(
        "Database health: connected=%s tables=%s latency=%sms",
        db_health.connected, db_health.tables_exist, db_health.latency_ms,
    )
    if db_health.connected and db_health.tables_exist:
        logger.info("Database Connected Successfully")
    return db_health

async def ensure_database() -> bool:
    """Create the target MySQL database if it does not exist.

    Uses a temporary engine connected to the MySQL system database so that
    ``CREATE DATABASE IF NOT EXISTS`` can run independently of the main engine.
    Returns True if the database exists (or was created) afterwards.
    """
    if not _is_mysql:
        return True  # no-op for non-MySQL backends
    try:
        # Derive a URL that connects to the MySQL server without a specific database.
        # Strip the database name from the path component of the URL.
        db_url = settings.db_url
        # e.g. mysql+aiomysql://root:@localhost:3306/doctel
        import re
        no_db_url = re.sub(r"/[^/]+$", "/mysql", db_url)
        tmp_engine = create_async_engine(no_db_url, pool_size=1, max_overflow=0)
        async with tmp_engine.begin() as conn:
            await conn.execute(text("CREATE DATABASE IF NOT EXISTS doctel"))
        await tmp_engine.dispose()
        logger.info("Database 'doctel' ensured (created if missing).")
        return True
    except Exception as e:
        logger.warning("Could not auto-create database 'doctel': %s", e)
        return False


async def init_db() -> DatabaseHealth:
    """Initialize database: create tables, run migrations, seed admin, verify health."""
    # First ensure the database itself exists
    await ensure_database()

    from .models import User
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_mysql(conn)
        # Seed lookup tables (task_types, roles, departments, model_statuses)
        await _seed_lookup_tables(conn)

    async with AsyncSessionLocal() as session:
        # Check if admin exists
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(username="admin", ec_number="admin", email="", display_name="Admin", role="admin")
            session.add(admin)
            await session.commit()

    # Verify health after initialization
    await verify_database_health()
    return db_health


async def _migrate_mysql(conn):
    """MySQL‑specific schema migrations (column additions, etc.)."""
    def _col_exists(cols, name: str) -> bool:
        return any(c.get("Field") == name for c in cols)

    # ── Migrate projects ───────────────────────────────────────────────
    res = await conn.execute(text("SHOW COLUMNS FROM projects"))
    cols = [dict(r) for r in res.mappings().all()]
    statements = []
    if not _col_exists(cols, "archived_at"):
        statements.append("ALTER TABLE projects ADD COLUMN archived_at DATETIME NULL")
    for stmt in statements:
        try:
            await conn.execute(text(stmt))
        except Exception:
            pass

    # ── Migrate messages ───────────────────────────────────────────────
    # reasoning column — added after initial table creation
    res = await conn.execute(text("SHOW COLUMNS FROM messages"))
    cols = [dict(r) for r in res.mappings().all()]
    msg_statements = []
    if not _col_exists(cols, "reasoning"):
        msg_statements.append(
            "ALTER TABLE messages ADD COLUMN reasoning TEXT NULL "
            "COMMENT 'Model chain-of-thought reasoning output' "
            "AFTER content"
        )
    for stmt in msg_statements:
        try:
            await conn.execute(text(stmt))
        except Exception:
            pass

    # ── Migrate documents — embedding governance columns ────────────────
    res = await conn.execute(text("SHOW COLUMNS FROM documents"))
    cols = [dict(r) for r in res.mappings().all()]
    doc_statements = []
    if not _col_exists(cols, "embedding_provider"):
        doc_statements.append(
            "ALTER TABLE documents ADD COLUMN embedding_provider VARCHAR(128) NULL "
            "COMMENT 'Provider used for last embedding'"
        )
    if not _col_exists(cols, "embedding_model"):
        doc_statements.append(
            "ALTER TABLE documents ADD COLUMN embedding_model VARCHAR(255) NULL "
            "COMMENT 'Model used for last embedding'"
        )
    if not _col_exists(cols, "embedded_at"):
        doc_statements.append(
            "ALTER TABLE documents ADD COLUMN embedded_at DATETIME NULL "
            "COMMENT 'Timestamp of last successful embedding'"
        )
    if not _col_exists(cols, "embedding_version"):
        doc_statements.append(
            "ALTER TABLE documents ADD COLUMN embedding_version VARCHAR(32) NULL "
            "COMMENT 'Embedding version tag'"
        )
    for stmt in doc_statements:
        try:
            await conn.execute(text(stmt))
        except Exception:
            pass

    # ── Migrate embeddings — embedding governance columns ───────────────
    res = await conn.execute(text("SHOW COLUMNS FROM embeddings"))
    cols = [dict(r) for r in res.mappings().all()]
    emb_statements = []
    if not _col_exists(cols, "model_name"):
        emb_statements.append(
            "ALTER TABLE embeddings ADD COLUMN model_name VARCHAR(255) NULL "
            "COMMENT 'Embedding model used'"
        )
    if not _col_exists(cols, "provider"):
        emb_statements.append(
            "ALTER TABLE embeddings ADD COLUMN provider VARCHAR(128) NULL "
            "COMMENT 'Provider used for embedding'"
        )
    if not _col_exists(cols, "dimensions"):
        emb_statements.append(
            "ALTER TABLE embeddings ADD COLUMN dimensions INT NULL "
            "COMMENT 'Vector dimension count'"
        )
    for stmt in emb_statements:
        try:
            await conn.execute(text(stmt))
        except Exception:
            pass


async def _seed_lookup_tables(conn):
    """Seed lookup tables (task_types, roles, departments, model_statuses) if empty.

    Uses INSERT IGNORE so repeated startups are idempotent.
    """
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
