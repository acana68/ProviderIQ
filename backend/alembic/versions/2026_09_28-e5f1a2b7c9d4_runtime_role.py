"""runtime role: the app connects as provideriq_app, which can read and log searches only

Revision ID: e5f1a2b7c9d4
Revises: c3a8f0d5e217
Create Date: 2026-09-28 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f1a2b7c9d4"
down_revision: str | None = "c3a8f0d5e217"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Also in scripts/app_db_role.py, which gives the role its password.
APP_ROLE = "provideriq_app"
# Everything the API reads. A table added later gets no grant until a migration adds one
# (tests/integration/test_db_roles.py fails until it does).
READ_TABLES = (
    "specialties",
    "conditions",
    "cities",
    "providers",
    "provider_conditions",
    "dataset_metadata",
    "search_logs",
)


def upgrade() -> None:
    # Roles belong to the cluster, not a database, so the dev and test databases share
    # it. Created without LOGIN or a password: those are secrets, so they're set outside
    # migrations, by scripts/app_db_role.py.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN;
            END IF;
        END
        $$
        """
    )
    # Postgres 15+ already keeps CREATE on public from PUBLIC; this makes it explicit, so
    # the runtime role can never create objects whatever the server version.
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT ON {', '.join(READ_TABLES)} TO {APP_ROLE}")
    # One row per search. The ORM's INSERT ... RETURNING id is covered by SELECT above.
    op.execute(f"GRANT INSERT ON search_logs TO {APP_ROLE}")
    op.execute(f"GRANT USAGE ON SEQUENCE search_logs_id_seq TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON {', '.join(READ_TABLES)} FROM {APP_ROLE}")
    op.execute(f"REVOKE ALL ON SEQUENCE search_logs_id_seq FROM {APP_ROLE}")
    op.execute(f"REVOKE ALL ON SCHEMA public FROM {APP_ROLE}")
    # The role may still hold grants in another database (dev vs test); it's dropped only
    # once nothing references it.
    op.execute(
        f"""
        DO $$
        BEGIN
            DROP ROLE IF EXISTS {APP_ROLE};
        EXCEPTION WHEN dependent_objects_still_exist THEN
            RAISE NOTICE 'role {APP_ROLE} is still used in another database; kept';
        END
        $$
        """
    )
