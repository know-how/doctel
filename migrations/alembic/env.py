"""Alembic environment for DocTel."""
from logging.config import fileConfig
import re

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

raw_url = config.get_main_option("sqlalchemy.url", "")
sync_url = re.sub(r"postgresql\+asyncpg://", "postgresql+psycopg2://", raw_url)
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
from app.db import job_models         # noqa: E402, F401 — ProcessingJob, …

# target_metadata tells autogenerate which tables/columns to compare
target_metadata = DatabaseBase.metadata

EXCLUDE_TABLES = {
    'document_chunks', 'access_control', 'audit_log',
    'audit_log_2026_07', 'audit_log_2026_08',
    'audit_outbox', 'audit_outbox_2026_07', 'audit_outbox_2026_08',
    'outbox_processor_state', 'superuser_access_log',
    'workspaces', 'workspace_members', 'permissions',
    'role_permissions', 'user_roles', 'tags', 'document_tags',
    'api_keys', 'user_sessions', 'embedding_models',
    'agent_registry', 'agent_artifacts',
    'agent_sessions', 'agent_run_log', 'workflows',
    'workflow_versions', 'workflow_runs', 'workflow_steps',
    'workflow_events', 'tool_execution_log',
    'event_bus', 'event_delivery_log', 'event_subscriptions',
    'model_registry', 'search_queries', 'search_clicks',
    'search_feedback', 'conversation_state', 'model_calls',
    'prompt_versions', 'classification_policies',
    'governance_quality_scores', 'documents_legacy',
    'processing_jobs',
}


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in EXCLUDE_TABLES:
        return False
    return True


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
        include_object=include_object,
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
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
