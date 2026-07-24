"""Add doc_type column to doc_analysis table

The DocAnalysis ORM model defines `doc_type = Column(String(50))`,
but the column was never added to the physical database table.
This migration adds it, matching the model definition.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-23 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add doc_type column to doc_analysis table.

    The column is:
    - VARCHAR(50) to match the ORM model
    - nullable=True with default None (backward-compatible with existing rows)
    - Comment documents the expected values: policy|frs|meeting|sop|generic
    """
    op.add_column(
        "doc_analysis",
        sa.Column(
            "doc_type",
            sa.String(50),
            nullable=True,
            default=None,
            comment="Detected document type: policy|frs|meeting|sop|generic",
        ),
    )


def downgrade() -> None:
    """Remove the doc_type column from doc_analysis."""
    op.drop_column("doc_analysis", "doc_type")
