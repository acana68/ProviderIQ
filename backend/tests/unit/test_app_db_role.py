import pytest

from app.core.config import Settings
from scripts.app_db_role import APP_ROLE, AppRoleError, app_role_password

OWNER_URL = "postgresql+psycopg://provideriq:owner-pw@db:5432/provideriq"
APP_PASSWORD = "app-pw-not-a-real-secret"


def _settings(database_url: str, migration_database_url: str | None = OWNER_URL) -> Settings:
    return Settings(
        _env_file=None,
        database_url=database_url,
        migration_database_url=migration_database_url,
        ai_provider="none",
        anthropic_api_key=None,
    )


def test_password_comes_from_database_url() -> None:
    settings = _settings(f"postgresql+psycopg://{APP_ROLE}:{APP_PASSWORD}@db:5432/provideriq")

    assert app_role_password(settings) == APP_PASSWORD


@pytest.mark.parametrize("migration_database_url", [None, OWNER_URL])
def test_nothing_to_do_when_the_app_uses_the_owner_role(
    migration_database_url: str | None,
) -> None:
    assert app_role_password(_settings(OWNER_URL, migration_database_url)) is None


def test_the_app_must_use_the_granted_role() -> None:
    settings = _settings(f"postgresql+psycopg://someone:{APP_PASSWORD}@db:5432/provideriq")

    with pytest.raises(AppRoleError) as exc_info:
        app_role_password(settings)

    assert APP_ROLE in str(exc_info.value)
    assert APP_PASSWORD not in str(exc_info.value)


def test_a_missing_password_is_an_error() -> None:
    # What an unset APP_DB_PASSWORD produces in docker-compose.yml.
    settings = _settings(f"postgresql+psycopg://{APP_ROLE}:@db:5432/provideriq")

    with pytest.raises(AppRoleError, match="APP_DB_PASSWORD"):
        app_role_password(settings)
