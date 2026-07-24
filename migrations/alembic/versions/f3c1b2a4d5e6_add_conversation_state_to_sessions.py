"""Add conversation_state column to sessions table

Revision ID: f3c1b2a4d5e6
Revises: 8e2f1a3b4c5d
Create Date: 2026-07-16 21:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3c1b2a4d5e6"
down_revision: Union[str, Sequence[str], None] = "8e2f1a3b4c5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add conversation_state column to sessions table."""
    op.add_column(
        "sessions",
        sa.Column(
            "conversation_state",
            sa.Text(),
            nullable=True,
            comment="JSON blob tracking entities_seen, topic_history, last_turn_summary",
        ),
    )


def downgrade() -> None:
    """Remove conversation_state column from sessions table."""
    op.drop_column("sessions", "conversation_state")
