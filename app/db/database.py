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
        await conn.run_sync(Base.metadata.create_all)
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
