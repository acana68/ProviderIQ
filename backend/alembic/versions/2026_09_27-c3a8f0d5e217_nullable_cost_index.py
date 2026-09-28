"""nullable cost_index: CMS spending per patient can be unreported

Revision ID: c3a8f0d5e217
Revises: b7e4c2a91d3f
Create Date: 2026-09-27 20:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3a8f0d5e217"
down_revision: str | None = "b7e4c2a91d3f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NULL: CMS suppressed the clinician's medical amounts, or they had too few patients
    # (pipeline/sql/06_providers.sql). The cost_index > 0 CHECK stays; it passes for NULL.
    op.alter_column("providers", "cost_index", nullable=True)


def downgrade() -> None:
    # Only CMS rows can be NULL, and the old schema can't hold them.
    op.execute("DELETE FROM providers WHERE cost_index IS NULL")
    op.alter_column("providers", "cost_index", nullable=False)
