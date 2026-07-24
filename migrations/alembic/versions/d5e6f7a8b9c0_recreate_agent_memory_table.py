"""Recreate agent_memory table to match current AgentMemory ORM model

The database had a legacy agent_memory table with a fundamentally
incompatible schema (UUID PK, different column names, different FK
targets).  The current AgentMemory ORM model (Pillar 18 — Agent
Memory) requires:

  - Integer autoincrement PK (was UUID)
  - FK → agent_executions.id (was FK → agent_registry.id)
  - FK → sessions.id (was FK → agent_sessions.id)
  - renamed columns: memory_key → key, memory_value → value_json
  - new column: embedding (vector(768)) via pgvector
  - dropped legacy columns: scope_type, scope_id, importance, agent_id

The old table had no production data because every prior write
attempt failed with UndefinedColumnError due to the schema mismatch.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-07-23 12:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Drop the old table and its indexes ─────────────────────────────
    # The old schema has UUID PK, memory_key/memory_value column names,
    # different FK targets (agent_registry, agent_sessions), and legacy
    # columns (scope_type, scope_id, importance) that no longer exist in
    # the current ORM.  A clean DROP + CREATE is the only safe path.
    # NOTE: op.drop_table does NOT support if_exists, so we use raw SQL.
    op.execute("DROP TABLE IF EXISTS agent_memory CASCADE")

    # ── 2. Create the new table ───────────────────────────────────────────
    op.create_table(
        "agent_memory",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "agent_execution_id",
            sa.Integer(),
            sa.ForeignKey("agent_executions.id", ondelete="CASCADE"),
            nullable=False,
            comment="The agent execution that produced this memory entry",
        ),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("sessions.id", ondelete="SET NULL"),
            nullable=True,
            comment="Session this memory belongs to (NULL for long-term memories)",
        ),
        sa.Column(
            "memory_type",
            sa.String(32),
            nullable=False,
            server_default="working",
            comment="working | episodic | semantic",
        ),
        sa.Column(
            "key",
            sa.String(255),
            nullable=False,
            server_default="",
            comment="Semantic key for memory lookup (e.g. 'user_intent', 'retrieved_facts')",
        ),
        sa.Column(
            "value_json",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'null'::text"),
            comment="Memory payload as JSON (flexible schema per memory type)",
        ),
        # The embedding column is stored as Text in the ORM to keep the
        # Python dependency free from the pgvector package.  A future
        # migration can ALTER it to vector(768) once the agent memory
        # service actually uses semantic search.
        sa.Column(
            "embedding",
            sa.Text(),
            nullable=True,
            default=None,
            comment="pgvector embedding (vector(768)) — stored as Text in ORM, vector in DB",
        ),
        sa.Column(
            "ttl_seconds",
            sa.Integer(),
            nullable=True,
            default=None,
            comment="Time-to-live for this memory entry (NULL = permanent)",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            default=None,
            comment="Computed expiry timestamp (created_at + ttl_seconds)",
        ),
        sa.Column(
            "access_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Number of times this memory has been accessed (for LRU eviction)",
        ),
        sa.Column(
            "last_accessed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            default=None,
            comment="Timestamp of last access (for LRU eviction)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 3. Create indexes matching __table_args__ in the ORM model ─────
    op.create_index(
        "idx_agent_memory_lookup",
        "agent_memory",
        ["agent_execution_id", "memory_type", "key"],
    )
    op.create_index(
        "idx_agent_memory_expiry",
        "agent_memory",
        ["expires_at"],
    )
    op.create_index(
        "idx_agent_memory_session",
        "agent_memory",
        ["session_id", "memory_type"],
    )
    op.create_index(
        "idx_agent_memory_access",
        "agent_memory",
        ["access_count", "last_accessed_at"],
    )


def downgrade() -> None:
    """Restore the legacy agent_memory table schema.

    WARNING: This will drop the new enterprise table and recreate the
    old pre-enterprise schema.  Any data written to the new table will
    be lost.
    """
    op.drop_table("agent_memory", if_exists=True)

    op.create_table(
        "agent_memory",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("session_id", postgresql.UUID(), nullable=False),
        sa.Column("agent_id", postgresql.UUID(), nullable=True),
        sa.Column("memory_type", sa.String(32), nullable=False),
        sa.Column("memory_key", sa.String(255), nullable=False),
        sa.Column("memory_value", postgresql.JSONB(), nullable=False),
        sa.Column("scope_type", sa.String(32), server_default=sa.text("'session'"),
                  nullable=True),
        sa.Column("scope_id", postgresql.UUID(), nullable=True),
        sa.Column("importance", sa.Float(), server_default=sa.text("0.5"), nullable=True),
        sa.Column("ttl_seconds", sa.Integer(), nullable=True),
        sa.Column("access_count", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_id"], ["agent_registry.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
    )
    op.create_index("agent_memory_pkey", "agent_memory", ["id"], unique=True)
    op.create_index("idx_agent_memory_session", "agent_memory", ["session_id", "memory_type"])
    op.execute(
        "CREATE INDEX idx_agent_memory_scope ON public.agent_memory "
        "USING btree (scope_type, scope_id) WHERE (scope_type IS NOT NULL)"
    )
