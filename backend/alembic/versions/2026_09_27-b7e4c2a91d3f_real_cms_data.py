"""real CMS data: staging schema, NPI and data source on providers, nullable metrics

Revision ID: b7e4c2a91d3f
Revises: 623b10afb234
Create Date: 2026-09-27 06:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e4c2a91d3f"
down_revision: str | None = "623b10afb234"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Metrics a data source may not publish. Their CHECK constraints stay: a CHECK passes
# for NULL, so they still bound every value that is present.
NULLABLE_METRICS = ("years_experience", "quality_score", "complication_rate", "readmission_rate")


def upgrade() -> None:
    # The CMS pipeline (backend/pipeline/) loads raw downloads here, as text, and runs
    # its SQL transforms here. The app never reads it.
    op.execute("CREATE SCHEMA IF NOT EXISTS staging")

    op.add_column("providers", sa.Column("npi", sa.String(length=10), nullable=True))
    op.add_column(
        "providers",
        sa.Column("data_source", sa.String(length=10), server_default="synthetic", nullable=False),
    )
    op.add_column(
        "providers",
        sa.Column(
            "quality_imputed",
            sa.Boolean(),
            sa.Computed("quality_score IS NULL", persisted=True),
            nullable=False,
        ),
    )
    op.create_unique_constraint(op.f("uq_providers_npi"), "providers", ["npi"])
    op.create_check_constraint(
        op.f("ck_providers_data_source_valid"), "providers", "data_source IN ('synthetic', 'cms')"
    )
    op.create_check_constraint(op.f("ck_providers_npi_format"), "providers", "npi ~ '^[0-9]{10}$'")
    op.create_check_constraint(
        op.f("ck_providers_npi_matches_source"),
        "providers",
        "(data_source = 'cms') = (npi IS NOT NULL)",
    )
    for column in NULLABLE_METRICS:
        op.alter_column("providers", column, nullable=True)
    # NULL = unknown (CMS doesn't publish it). The old default of true would quietly
    # mark every clinician inserted without a value as accepting new patients.
    op.alter_column("providers", "accepting_new_patients", nullable=True, server_default=None)

    op.create_table(
        "dataset_metadata",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=True),
        sa.Column("vintage", sa.Text(), nullable=True),
        sa.Column(
            "seeded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_dataset_metadata_single_row")),
        sa.CheckConstraint(
            "source IN ('synthetic', 'cms_nj')", name=op.f("ck_dataset_metadata_source_valid")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataset_metadata")),
    )


def downgrade() -> None:
    op.drop_table("dataset_metadata")
    # The old schema can't hold CMS rows (NULL metrics, no NPI column), so they go.
    op.execute("DELETE FROM providers WHERE data_source = 'cms'")
    for column in NULLABLE_METRICS:
        op.alter_column("providers", column, nullable=False)
    op.alter_column(
        "providers", "accepting_new_patients", nullable=False, server_default=sa.text("true")
    )
    op.drop_constraint(op.f("ck_providers_npi_matches_source"), "providers", type_="check")
    op.drop_constraint(op.f("ck_providers_npi_format"), "providers", type_="check")
    op.drop_constraint(op.f("ck_providers_data_source_valid"), "providers", type_="check")
    op.drop_constraint(op.f("uq_providers_npi"), "providers", type_="unique")
    op.drop_column("providers", "quality_imputed")
    op.drop_column("providers", "data_source")
    op.drop_column("providers", "npi")
    op.execute("DROP SCHEMA IF EXISTS staging CASCADE")
