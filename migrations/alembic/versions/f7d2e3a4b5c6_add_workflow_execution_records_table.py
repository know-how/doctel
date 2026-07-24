"""Add workflow_execution_records table

Revision ID: f7d2e3a4b5c6
Revises: 8e2f1a3b4c5d
Create Date: 2026-07-23 07:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7d2e3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "8e2f1a3b4c5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the workflow_execution_records table.

    Stores autonomous workflow execution results persistently so they
    survive server restarts and are visible across workers.
    """
    op.create_table(
        "workflow_execution_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("execution_id", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("workflow_type", sa.String(64), nullable=False, index=True),
        sa.Column("objective", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, default="pending", index=True),
        # pending | running | completed | failed

        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_id", sa.String(128), nullable=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("project_ids_json", sa.Text, default="[]"),

        # Execution data (JSON-serialized)
        sa.Column("steps_json", sa.Text, default="[]"),
        sa.Column("deliverables_json", sa.Text, default="{}"),
        sa.Column("merged_entities_json", sa.Text, default="[]"),
        sa.Column("merged_actions_json", sa.Text, default="[]"),
        sa.Column("merged_decisions_json", sa.Text, default="[]"),
        sa.Column("merged_risks_json", sa.Text, default="[]"),
        sa.Column("merged_workflows_json", sa.Text, default="[]"),
        sa.Column("execution_summary", sa.Text, default=""),
        sa.Column("error_message", sa.Text, default=""),

        # Timing
        sa.Column("total_duration_ms", sa.Float, default=0.0),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),

        # Provenance
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),

        # Indexes
        sa.Index("idx_wfexec_status_created", "status", "created_at"),
        sa.Index("idx_wfexec_type_status", "workflow_type", "status"),
        sa.Index("idx_wfexec_session", "session_id"),
    )


def downgrade() -> None:
    """Drop the workflow_execution_records table."""
    op.drop_table("workflow_execution_records")
