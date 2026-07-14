"""Alembic environment for DocTel.

This configures Alembic to work with the async SQLAlchemy models by
translating the async DB URL (aiomysql) to a sync one (pymysql) that
Alembic can use.
"""
from logging.config import fileConfig
import re

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Patch the DB URL: Alembic needs a sync driver ──────────────────────
# The project uses mysql+aiomysql:// for async; Alembic needs mysql+pymysql://
# for synchronous migrations.  We do this transparently so the .ini file
# can keep the async URL as documentation.
raw_url = config.get_main_option("sqlalchemy.url", "")
sync_url = re.sub(r"mysql\+aiomysql://", "mysql+pymysql://", raw_url)
sync_url = re.sub(r"postgresql\+asyncpg://", "postgresql+psycopg2://", sync_url)
config.set_main_option("sqlalchemy.url", sync_url)

# ── Import the application's SQLAlchemy metadata ───────────────────────
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.db.database import Base as DatabaseBase

# Import ALL model modules so every table registers with Base.metadata.
# Without this, Alembic autogenerate cannot resolve foreign keys like
# agent_executions.user_id → users.id.
from app.db import models           # noqa: E402, F401 — User, Project, Message, …
from app.db import enterprise_models  # noqa: E402, F401 — AgentExecution, …
from app.db import config_models      # noqa: E402, F401 — Lookup, PromptSuggestion, …

# target_metadata tells autogenerate which tables/columns to compare
target_metadata = DatabaseBase.metadata

# ── Offline migration (--sql flag) ─────────────────────────────────────

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

# ── Online migration (default) ─────────────────────────────────────────

def run_migrations_online() -> None:
    """Run migrations directly against the database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
