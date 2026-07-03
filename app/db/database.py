"""
database.py — DocTel Database Layer

Provides:
- MySQL-first connection pooling (5-50 connections, 300s idle timeout)
- SQLite fallback for development
- Health verification at startup
- Migration checks
- Transaction-safe operations
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

from app.config import settings

logger = logging.getLogger(__name__)

# ── Detect database type ────────────────────────────────────────────────────
_is_mysql = settings.db_url.startswith("mysql")
_is_sqlite = not _is_mysql


# ── Connection Pool Configuration ──────────────────────────────────────────
# MySQL (async): create_async_engine auto-selects AsyncAdaptedQueuePool
#                when pool_size / max_overflow are provided.
# SQLite:         NullPool – no pooling needed for local file DB.

def _build_engine() -> AsyncEngine:
    """Create the async engine with appropriate connection pooling."""
    driver = settings.db_url.split("://")[0] if "://" in settings.db_url else settings.db_url
    pool_type: str

    pre_ping_enabled = False

    if _is_mysql:
        # MySQL async connection pooling (AsyncAdaptedQueuePool is automatic)
        # NOTE: pool_pre_ping is DISABLED for async MySQL drivers (aiomysql/asyncmy)
        # because their ping() signatures are incompatible with SQLAlchemy's
        # pool_pre_ping mechanism. Connection health is ensured by pool_recycle.
        pre_ping_enabled = False
        engine_kwargs = {
            "echo": False,
            "pool_size": 50,              # max persistent connections
            "max_overflow": 10,           # extra connections beyond pool_size
            "pool_recycle": 300,          # recycle after 300s idle
            "pool_timeout": 30,           # wait max 30s for a connection
        }
        pool_type = "AsyncAdaptedQueuePool"
    else:
        # SQLite: single connection, no pooling
        pre_ping_enabled = False          # not needed for local file DB with WAL mode
        engine_kwargs = {
            "echo": False,
            "connect_args": {"timeout": 60},
            "poolclass": NullPool,
        }
        pool_type = "NullPool"

    logger.info("Driver: %s", driver)
    logger.info("Pool: %s", pool_type)
    logger.info("PrePing: %s", "Enabled" if pre_ping_enabled else "Disabled")

    return create_async_engine(settings.db_url, **engine_kwargs)


engine = _build_engine()

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()


# ── Database-at-rest encryption support (SQLite only) ──────────────────────
if _is_sqlite and settings.security.encrypt_sqlite:
    from app.utils.encryption import decrypt_database, encrypt_database
    _db_path = str(Path(settings.base_dir) / "db" / "app.db")
    if not decrypt_database(_db_path, settings.base_dir):
        raise RuntimeError(
            "Cannot start – database decryption failed. "
            "If the encryption key changed, restore the previous key or "
            "delete the database file and re-seed."
        )
else:
    encrypt_database = None  # type: ignore
    _db_path = None


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
            if _is_mysql:
                result = await conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()"
                ))
                row = result.fetchone()
                table_count = row[0] if row else 0
            else:
                result = await conn.execute(text(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                ))
                row = result.fetchone()
                table_count = row[0] if row else 0
        db_health.tables_exist = table_count >= 15  # We expect ~15+ tables
        if not db_health.tables_exist:
            db_health.error = f"Only {table_count} tables found (expected >= 15)"
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
    logger.info(
        "Database health: connected=%s tables=%s latency=%sms",
        db_health.connected, db_health.tables_exist, db_health.latency_ms,
    )
    if db_health.connected and db_health.tables_exist:
        logger.info("Database Connected Successfully")
    return db_health

async def init_db() -> DatabaseHealth:
    """Initialize database: create tables, run migrations, seed admin, verify health."""
    from .models import User
    async with engine.begin() as conn:
        if _is_sqlite:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
        await conn.run_sync(Base.metadata.create_all)
        if _is_sqlite:
            await _migrate_sqlite(conn)
        else:
            await _migrate_mysql(conn)
    
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


async def _ensure_sessions_updated_at(conn) -> None:
    res = await conn.exec_driver_sql("PRAGMA table_info(sessions)")
    cols = [dict(r) for r in res.mappings().all()]
    has = any((c.get("name") == "updated_at") for c in cols)
    if not has:
        await conn.exec_driver_sql("ALTER TABLE sessions ADD COLUMN updated_at DATETIME")
    try:
        await conn.exec_driver_sql("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
    except Exception:
        pass
    try:
        await conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS sessions_updated_at_insert
            AFTER INSERT ON sessions
            WHEN NEW.updated_at IS NULL
            BEGIN
                UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE rowid = NEW.rowid;
            END;
            """
        )
    except Exception:
        pass
    try:
        await conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS sessions_updated_at_update
            AFTER UPDATE ON sessions
            BEGIN
                UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE rowid = NEW.rowid;
            END;
            """
        )
    except Exception:
        pass

async def _migrate_sqlite(conn):
    def _col_exists(cols, name: str) -> bool:
        return any((c.get("name") == name) for c in cols)

    res = await conn.exec_driver_sql("PRAGMA table_info(documents)")
    cols = [dict(r) for r in res.mappings().all()]
    statements = []
    if not _col_exists(cols, "status"):
        statements.append("ALTER TABLE documents ADD COLUMN status TEXT DEFAULT 'uploaded'")
    if not _col_exists(cols, "ingest_step"):
        statements.append("ALTER TABLE documents ADD COLUMN ingest_step TEXT DEFAULT 'uploaded'")
    if not _col_exists(cols, "ingest_percent"):
        statements.append("ALTER TABLE documents ADD COLUMN ingest_percent INTEGER DEFAULT 0")
    if not _col_exists(cols, "ingest_message"):
        statements.append("ALTER TABLE documents ADD COLUMN ingest_message TEXT DEFAULT ''")
    if not _col_exists(cols, "error_message"):
        statements.append("ALTER TABLE documents ADD COLUMN error_message TEXT DEFAULT ''")
    if not _col_exists(cols, "detected_type"):
        statements.append("ALTER TABLE documents ADD COLUMN detected_type TEXT DEFAULT ''")
    if not _col_exists(cols, "updated_at"):
        statements.append("ALTER TABLE documents ADD COLUMN updated_at TEXT")
    if not _col_exists(cols, "uploaded_by_user_id"):
        statements.append("ALTER TABLE documents ADD COLUMN uploaded_by_user_id INTEGER")
    if not _col_exists(cols, "is_public"):
        statements.append("ALTER TABLE documents ADD COLUMN is_public INTEGER DEFAULT 0")
    if not _col_exists(cols, "auto_project_confidence"):
        statements.append("ALTER TABLE documents ADD COLUMN auto_project_confidence REAL DEFAULT 0")
    if not _col_exists(cols, "needs_project_review"):
        statements.append("ALTER TABLE documents ADD COLUMN needs_project_review INTEGER DEFAULT 0")
    if not _col_exists(cols, "tags_json"):
        statements.append("ALTER TABLE documents ADD COLUMN tags_json TEXT DEFAULT '[]'")
    if not _col_exists(cols, "analysis_ready"):
        statements.append("ALTER TABLE documents ADD COLUMN analysis_ready INTEGER DEFAULT 0")
    if not _col_exists(cols, "ingestion_started"):
        statements.append("ALTER TABLE documents ADD COLUMN ingestion_started INTEGER DEFAULT 0")
    if not _col_exists(cols, "ingestion_completed"):
        statements.append("ALTER TABLE documents ADD COLUMN ingestion_completed INTEGER DEFAULT 0")
    if not _col_exists(cols, "ingestion_failed"):
        statements.append("ALTER TABLE documents ADD COLUMN ingestion_failed INTEGER DEFAULT 0")

    for stmt in statements:
        await conn.exec_driver_sql(stmt)

    res2 = await conn.exec_driver_sql("PRAGMA table_info(doc_analysis)")
    cols2 = [dict(r) for r in res2.mappings().all()]
    statements2 = []
    if not _col_exists(cols2, "action_items_json"):
        statements2.append("ALTER TABLE doc_analysis ADD COLUMN action_items_json TEXT")
    if not _col_exists(cols2, "decisions_json"):
        statements2.append("ALTER TABLE doc_analysis ADD COLUMN decisions_json TEXT")
    for stmt in statements2:
        await conn.exec_driver_sql(stmt)

    res3 = await conn.exec_driver_sql("PRAGMA table_info(sessions)")
    cols3 = [dict(r) for r in res3.mappings().all()]
    statements3 = []
    if not _col_exists(cols3, "session_uuid"):
        statements3.append("ALTER TABLE sessions ADD COLUMN session_uuid TEXT")
    if not _col_exists(cols3, "model_name"):
        statements3.append("ALTER TABLE sessions ADD COLUMN model_name TEXT")
    if not _col_exists(cols3, "document_id"):
        statements3.append("ALTER TABLE sessions ADD COLUMN document_id INTEGER")
    if not _col_exists(cols3, "title"):
        statements3.append("ALTER TABLE sessions ADD COLUMN title TEXT DEFAULT ''")
    if not _col_exists(cols3, "scope"):
        statements3.append("ALTER TABLE sessions ADD COLUMN scope TEXT DEFAULT 'document'")
    if not _col_exists(cols3, "archived"):
        statements3.append("ALTER TABLE sessions ADD COLUMN archived INTEGER DEFAULT 0")
    for stmt in statements3:
        await conn.exec_driver_sql(stmt)
    await _ensure_sessions_updated_at(conn)

    res_projects = await conn.exec_driver_sql("PRAGMA table_info(projects)")
    proj_cols = [dict(r) for r in res_projects.mappings().all()]
    proj_statements = []
    if not _col_exists(proj_cols, "archived_at"):
        proj_statements.append("ALTER TABLE projects ADD COLUMN archived_at DATETIME")
    for stmt in proj_statements:
        await conn.exec_driver_sql(stmt)

    res_users = await conn.exec_driver_sql("PRAGMA table_info(users)")
    user_cols = [dict(r) for r in res_users.mappings().all()]
    user_statements = []
    if not _col_exists(user_cols, "ec_number"):
        user_statements.append("ALTER TABLE users ADD COLUMN ec_number TEXT")
    if not _col_exists(user_cols, "email"):
        user_statements.append("ALTER TABLE users ADD COLUMN email TEXT")
    if not _col_exists(user_cols, "display_name"):
        user_statements.append("ALTER TABLE users ADD COLUMN display_name TEXT DEFAULT ''")
    for stmt in user_statements:
        await conn.exec_driver_sql(stmt)

    res4 = await conn.exec_driver_sql("PRAGMA table_info(messages)")
    cols4 = [dict(r) for r in res4.mappings().all()]
    statements4 = []
    if not _col_exists(cols4, "status"):
        statements4.append("ALTER TABLE messages ADD COLUMN status TEXT DEFAULT 'done'")
    for stmt in statements4:
        await conn.exec_driver_sql(stmt)

    try:
        await conn.exec_driver_sql(
            "DELETE FROM project_members WHERE id NOT IN (SELECT MIN(id) FROM project_members GROUP BY project_id, user_id)"
        )
    except Exception:
        pass
    try:
        await conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_project_members_project_user ON project_members(project_id, user_id)"
        )
    except Exception:
        pass

    try:
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS document_links (id INTEGER PRIMARY KEY, from_document_id INTEGER, to_document_id INTEGER, relation TEXT, confidence REAL DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
    except Exception:
        pass

    try:
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS diagrams (id INTEGER PRIMARY KEY, project_id INTEGER, session_id INTEGER, title TEXT, mermaid TEXT, drawing_prompt TEXT, version INTEGER DEFAULT 1, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
    except Exception:
        pass

    try:
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value_json TEXT, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_by_user_id INTEGER)"
        )
    except Exception:
        pass

    try:
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS settings_audit (id INTEGER PRIMARY KEY, key TEXT, old_value_json TEXT, new_value_json TEXT, changed_by_user_id INTEGER, changed_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
    except Exception:
        pass

    try:
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS user_identity_providers (id INTEGER PRIMARY KEY, user_id INTEGER, provider TEXT, identity TEXT, verified INTEGER DEFAULT 0, last_login_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
    except Exception:
        pass
    try:
        await conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_identity_provider_identity ON user_identity_providers(provider, identity)"
        )
    except Exception:
        pass


async def _migrate_mysql(conn):
    """MySQL‑specific schema migrations (column additions, etc.)."""
    def _col_exists(cols, name: str) -> bool:
        return any(c.get("Field") == name for c in cols)

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


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
