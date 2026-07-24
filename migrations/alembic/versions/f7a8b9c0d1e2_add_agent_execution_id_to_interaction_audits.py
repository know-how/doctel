"""Add agent_execution_id FK to interaction_audits table.

The ORM defines InteractionAudit.agent_execution_id as a ForeignKey
to agent_executions.id, but the database table is missing this column
(pre-enterprise schema). This migration adds it.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-07-23 14:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add agent_execution_id FK column (nullable)
    op.add_column(
        "interaction_audits",
        sa.Column(
            "agent_execution_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    # Create FK constraint
    op.create_foreign_key(
        "fk_interaction_audits_agent_execution_id",
        "interaction_audits",
        "agent_executions",
        ["agent_execution_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Create index for the new FK
    op.create_index(
        "idx_interaction_audits_agent_execution",
        "interaction_audits",
        ["agent_execution_id"],
    )


def downgrade() -> None:
    # Drop index first
    op.drop_index("idx_interaction_audits_agent_execution", table_name="interaction_audits")

    # Drop FK constraint
    op.drop_constraint(
        "fk_interaction_audits_agent_execution_id",
        "interaction_audits",
        type_="foreignkey",
    )

    # Drop column
    op.drop_column("interaction_audits", "agent_execution_id")
