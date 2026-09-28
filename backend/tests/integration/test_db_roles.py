"""The runtime role the API connects as (provideriq_app, created by the migrations): it can
read the app's tables and add search_logs rows, and nothing else.

Each test switches to the role with SET LOCAL ROLE inside its own rolled-back
transaction, so it needs no password and leaves nothing behind.
"""

import psycopg.errors
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from scripts.app_db_role import APP_ROLE

APP_TABLES = {
    "specialties",
    "conditions",
    "cities",
    "providers",
    "provider_conditions",
    "dataset_metadata",
    "search_logs",
}
TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def _as_app_role(session: Session) -> Session:
    session.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
    return session


def _assert_denied(session: Session, statement: str) -> None:
    with pytest.raises(ProgrammingError) as exc_info:
        session.execute(text(statement))

    assert isinstance(exc_info.value.orig, psycopg.errors.InsufficientPrivilege)


def test_runtime_role_is_unprivileged(db_session: Session) -> None:
    attributes = db_session.execute(
        text(
            "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolreplication "
            "FROM pg_roles WHERE rolname = :role"
        ),
        {"role": APP_ROLE},
    ).one()

    assert not any(attributes)


def test_runtime_role_has_exactly_the_expected_table_privileges(db_session: Session) -> None:
    # Every table in public, including any added later: a new table fails this test until
    # a migration decides what the runtime role may do with it.
    tables = db_session.scalars(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    ).all()
    granted = {
        table: {
            privilege
            for privilege in TABLE_PRIVILEGES
            if db_session.scalar(
                text("SELECT has_table_privilege(:role, :table, :privilege)"),
                {"role": APP_ROLE, "table": f"public.{table}", "privilege": privilege},
            )
        }
        for table in tables
    }

    expected = {table: {"SELECT"} for table in APP_TABLES}
    expected["search_logs"] = {"SELECT", "INSERT"}
    expected["alembic_version"] = set()
    assert granted == expected


@pytest.mark.parametrize("table", sorted(APP_TABLES))
def test_runtime_role_can_read(db_session: Session, table: str) -> None:
    _as_app_role(db_session).execute(text(f"SELECT count(*) FROM {table}"))


def test_runtime_role_can_log_a_search(db_session: Session) -> None:
    _as_app_role(db_session).execute(
        text(
            "INSERT INTO search_logs (source, priority, result_count, latency_ms) "
            "VALUES ('manual', 'balanced', 0, 1.0)"
        )
    )


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO providers (first_name, last_name) VALUES ('Mallory', 'Example')",
        "UPDATE providers SET quality_score = 100",
        "DELETE FROM providers",
        "TRUNCATE providers",
        "INSERT INTO specialties (slug, name) VALUES ('x', 'X')",
        "UPDATE search_logs SET result_count = 0",
        "DELETE FROM search_logs",
        "UPDATE dataset_metadata SET source = 'cms_nj'",
    ],
)
def test_runtime_role_cannot_change_data(db_session: Session, statement: str) -> None:
    _assert_denied(_as_app_role(db_session), statement)


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE public.mallory (id int)",
        "CREATE TABLE staging.mallory (id int)",
        "CREATE SCHEMA mallory",
        "ALTER TABLE providers ADD COLUMN mallory int",
        "DROP TABLE providers",
        "CREATE INDEX mallory ON providers (last_name)",
        "CREATE FUNCTION public.mallory() RETURNS int LANGUAGE sql AS 'SELECT 1'",
    ],
)
def test_runtime_role_cannot_run_ddl(db_session: Session, statement: str) -> None:
    _assert_denied(_as_app_role(db_session), statement)


def test_runtime_role_cannot_grant_itself_more(db_session: Session) -> None:
    # Postgres only warns ("no privileges were granted") when a non-owner grants.
    _as_app_role(db_session).execute(text(f"GRANT INSERT ON providers TO {APP_ROLE}"))

    assert not db_session.scalar(
        text("SELECT has_table_privilege(:role, 'providers', 'INSERT')"), {"role": APP_ROLE}
    )


def test_runtime_role_cannot_read_the_pipeline_staging_schema(db_session: Session) -> None:
    _assert_denied(
        _as_app_role(db_session),
        "SELECT count(*) FROM staging.load_log",
    )


def test_api_search_works_as_the_runtime_role(client: TestClient, seeded_db: Session) -> None:
    # The whole search path (reference lookups, the provider query, the search log) with
    # only the runtime role's grants.
    _as_app_role(seeded_db)
    before = seeded_db.scalar(text("SELECT count(*) FROM search_logs"))

    response = client.post("/api/v1/search", json={})

    assert response.status_code == 200
    assert response.json()["total"] > 0
    assert seeded_db.scalar(text("SELECT current_user")) == APP_ROLE
    assert seeded_db.scalar(text("SELECT count(*) FROM search_logs")) == before + 1
