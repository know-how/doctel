"""Add reasoning column to messages table

Revision ID: adcde6adea61
Revises: 
Create Date: 2026-07-10 16:18:46.066626

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "adcde6adea61"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the missing ``reasoning`` column to the ``messages`` table.

    This column already exists in the SQLAlchemy ``Message`` model
    (``app/db/models.py``) but was never added to the physical MySQL table,
    causing ``pymysql.err.OperationalError (1054)`` when the ORM includes it
    in INSERT / SELECT statements.
    """
    op.add_column(
        "messages",
        sa.Column(
            "reasoning",
            sa.Text,
            nullable=True,
            comment="Raw reasoning / chain-of-thought text from the LLM",
        ),
    )


def downgrade() -> None:
    """Remove the ``reasoning`` column, reverting to the pre-migration schema."""
    op.drop_column("messages", "reasoning")
