"""Change embedding column from vector(768) to Text to match ORM

The AgentMemory ORM model defines embedding as Column(Text, nullable=True),
but the previous migration (d5e6f7a8b9c0) FIRST created it as vector(768).
The ORM comment says "stored as Text in the ORM — future migration can
promote to vector(768) when semantic search is implemented."

Since the agent_memory_service.py never writes embeddings (it always passes
None), the vector(768) type causes DatatypeMismatchError on every INSERT
(NULL::varchar cannot cast to vector).  Reverting to Text keeps the ORM
and DB in sync until pgvector similarity search is actually implemented.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-23 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change embedding from vector(768) to Text to match the ORM model."""
    op.execute(
        "ALTER TABLE agent_memory ALTER COLUMN embedding TYPE TEXT "
        "USING embedding::text"
    )
    # Also revert the sequence default if any — vector columns don't have
    # defaults, but Text columns can use the Python/ORM default None.
    op.execute(
        "ALTER TABLE agent_memory ALTER COLUMN embedding "
        "DROP DEFAULT"
    )


def downgrade() -> None:
    """Restore embedding to vector(768) for pgvector compatibility."""
    # First ensure the pgvector extension is available
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        "ALTER TABLE agent_memory ALTER COLUMN embedding TYPE vector(768) "
        "USING embedding::vector(768)"
    )
