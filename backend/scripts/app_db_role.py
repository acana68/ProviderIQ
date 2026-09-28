"""Let the runtime role (provideriq_app) log in, with the password from DATABASE_URL.

The migrations create the role and its grants, but without LOGIN or a password: those
are secrets and don't belong in migrations. This sets them, connecting as the owner role
(MIGRATION_DATABASE_URL). It's idempotent, and the Docker entrypoint runs it on every
start, so a new APP_DB_PASSWORD in .env takes effect on the next restart.

Run from backend/ after `alembic upgrade head`:  python -m scripts.app_db_role

The password is hashed (SCRAM-SHA-256) here, so the server and its logs only ever see
the hash. Nothing about the password is printed.
"""

import sys

from psycopg import sql
from sqlalchemy import make_url, text

from app.core.config import Settings, get_settings
from app.database.session import create_db_engine

# Created and granted by the e5f1a2b7c9d4 migration.
APP_ROLE = "provideriq_app"


class AppRoleError(Exception):
    pass


def app_role_password(settings: Settings) -> str | None:
    """The password to give APP_ROLE, or None when the app and the migrations use the
    same role (MIGRATION_DATABASE_URL unset), so there's nothing to set up."""
    app_url = make_url(settings.database_url)
    owner_url = make_url(settings.owner_database_url)
    if app_url.username == owner_url.username:
        return None
    if app_url.username != APP_ROLE:
        raise AppRoleError(
            f"DATABASE_URL must connect as {APP_ROLE}, the role the migrations grant to"
        )
    if not app_url.password:
        raise AppRoleError(
            f"DATABASE_URL has no password for {APP_ROLE} (set APP_DB_PASSWORD in .env)"
        )
    return str(app_url.password)


def set_login_password(settings: Settings, password: str) -> None:
    engine = create_db_engine(settings, settings.owner_database_url)
    try:
        with engine.begin() as connection:
            if not connection.scalar(
                text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": APP_ROLE}
            ):
                raise AppRoleError(f"role {APP_ROLE} doesn't exist (run: alembic upgrade head)")
            driver = connection.connection.driver_connection
            verifier = driver.pgconn.encrypt_password(
                password.encode(), APP_ROLE.encode(), b"scram-sha-256"
            )
            # ALTER ROLE takes no bind parameters; Literal quotes the hash safely.
            statement = sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(APP_ROLE), sql.Literal(verifier.decode())
            )
            with driver.cursor() as cursor:
                cursor.execute(statement)
    finally:
        engine.dispose()


def main() -> None:
    settings = get_settings()
    try:
        password = app_role_password(settings)
        if password is None:
            print("DATABASE_URL uses the owner role; no runtime role to set up.")
            return
        set_login_password(settings, password)
    except AppRoleError as exc:
        sys.exit(f"Runtime role setup failed: {exc}")
    print(f"{APP_ROLE} can log in with the password in DATABASE_URL.")


if __name__ == "__main__":
    main()
