"""Merge migration heads — reconcile concurrent branches

Branch A: adcde6adea61 → 8e2f1a3b4c5d → f3c1b2a4d5e6 (conversation_state)
Branch B: adcde6adea61 → 8e2f1a3b4c5d → f7d2e3a4b5c6 → a1b2c3d4e5f6 → b2c3d4e5f6a7 (worker_id fix → doc_type)

This merge unifies the two heads so that `alembic upgrade head` works cleanly.

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7, f3c1b2a4d5e6
Create Date: 2026-07-23 09:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = ("b2c3d4e5f6a7", "f3c1b2a4d5e6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge the two concurrent migration branches."""
    pass


def downgrade() -> None:
    """Undo the merge (no-op — individual migrations handle their own revert)."""
    pass
