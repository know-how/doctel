"""Fix worker_id column type — change from UUID to VARCHAR(200)

The ProcessingJob ORM model defines worker_id = Column(String(200)),
but the physical column may have been created as UUID in the original
raw SQL table definition. This migration ensures the column type matches
the model so that human-readable worker IDs (e.g. "worker-hostname-PID")
work correctly in the heartbeat and reclaim queries.

Revision ID: a1b2c3d4e5f6
Revises: f7d2e3a4b5c6
Create Date: 2026-07-23 08:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f7d2e3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change worker_id column from UUID to VARCHAR(200).

    The column is:
    - nullable=True (workers can be NULL before a job is claimed)
    - Used by _heartbeat_loop() to match on string-based worker IDs
    - Uses VARCHAR(200) to match the ORM model (String(200))
    """
    op.alter_column(
        "processing_jobs",
        "worker_id",
        type_=sa.String(200),
        existing_type=sa.Uuid(),
        nullable=True,
        postgresql_using="worker_id::varchar(200)",
    )


def downgrade() -> None:
    """Revert worker_id column back to UUID (drops non-UUID values)."""
    # First clear any non-null string values that won't cast to UUID
    op.execute(
        "UPDATE processing_jobs SET worker_id = NULL "
        "WHERE worker_id IS NOT NULL "
        "AND worker_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'"
    )
    op.alter_column(
        "processing_jobs",
        "worker_id",
        type_=sa.Uuid(),
        existing_type=sa.String(200),
        nullable=True,
        postgresql_using="worker_id::uuid",
    )
