"""Add embedding governance fields to documents and embeddings tables

Revision ID: 8e2f1a3b4c5d
Revises: adcde6adea61
Create Date: 2026-07-10 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8e2f1a3b4c5d"
down_revision: Union[str, Sequence[str], None] = "adcde6adea61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add embedding metadata columns for governance tracking.

    This enables:
    - Tracking which embedding model/provider was used per document.
    - Detecting when the embedding model has changed (requires re-embedding).
    - Storing vector dimensions for compatibility validation.
    """
    # ── Document table ────────────────────────────────────────────────────
    op.add_column(
        "documents",
        sa.Column(
            "embedding_provider",
            sa.String(128),
            nullable=True,
            default=None,
            comment="Provider used for last embedding (e.g. ollama)",
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "embedding_model",
            sa.String(255),
            nullable=True,
            default=None,
            comment="Model used for last embedding (e.g. nomic-embed-text)",
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "embedded_at",
            sa.DateTime(timezone=True),
            nullable=True,
            default=None,
            comment="Timestamp of last successful embedding",
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "embedding_version",
            sa.String(32),
            nullable=True,
            default=None,
            comment="Embedding version tag; bumped when model changes",
        ),
    )

    # ── Embeddings table ──────────────────────────────────────────────────
    op.add_column(
        "embeddings",
        sa.Column(
            "model_name",
            sa.String(255),
            nullable=True,
            default=None,
            comment="Embedding model used (e.g. nomic-embed-text)",
        ),
    )
    op.add_column(
        "embeddings",
        sa.Column(
            "provider",
            sa.String(128),
            nullable=True,
            default=None,
            comment="Provider used for embedding (e.g. ollama)",
        ),
    )
    op.add_column(
        "embeddings",
        sa.Column(
            "dimensions",
            sa.Integer,
            nullable=True,
            default=None,
            comment="Vector dimension count",
        ),
    )


def downgrade() -> None:
    """Remove the embedding governance columns, reverting schema."""
    # ── Embeddings table ──────────────────────────────────────────────────
    op.drop_column("embeddings", "dimensions")
    op.drop_column("embeddings", "provider")
    op.drop_column("embeddings", "model_name")

    # ── Document table ────────────────────────────────────────────────────
    op.drop_column("documents", "embedding_version")
    op.drop_column("documents", "embedded_at")
    op.drop_column("documents", "embedding_model")
    op.drop_column("documents", "embedding_provider")
