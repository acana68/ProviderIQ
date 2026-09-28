from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import REPO_ROOT, Settings, _repo_root


def test_repo_root_is_three_levels_above_the_config_package() -> None:
    assert (REPO_ROOT / "backend" / "app" / "core" / "config.py").is_file()


def test_repo_root_of_a_deep_path(tmp_path: Path) -> None:
    config_file = tmp_path / "repo" / "backend" / "app" / "core" / "config.py"

    assert _repo_root(config_file) == (tmp_path / "repo").resolve()


def test_repo_root_of_a_shallow_path_does_not_crash(tmp_path: Path) -> None:
    anchor = Path(tmp_path.anchor)

    # Two levels and one level below the filesystem root: fewer than three parents.
    assert _repo_root(anchor / "app" / "config.py") == anchor.resolve()
    assert _repo_root(anchor / "config.py") == anchor.resolve()


def test_data_source_defaults_to_synthetic_and_ignores_case() -> None:
    base = {"_env_file": None, "database_url": "postgresql+psycopg://localhost/x"}

    assert Settings(**base).data_source == "synthetic"
    assert Settings(**base, data_source="CMS_NJ").data_source == "cms_nj"
    with pytest.raises(ValidationError):
        Settings(**base, data_source="cms_ny")


def test_migrations_use_the_app_url_unless_given_their_own() -> None:
    base = {"_env_file": None, "database_url": "postgresql+psycopg://app@localhost/x"}
    owner = "postgresql+psycopg://owner@localhost/x"

    assert Settings(**base).owner_database_url == base["database_url"]
    assert Settings(**base, migration_database_url=owner).owner_database_url == owner


@pytest.mark.parametrize(
    ("environment", "enabled"), [("dev", True), ("test", True), ("prod", False)]
)
def test_api_docs_are_off_in_prod(environment: str, enabled: bool) -> None:
    settings = Settings(
        _env_file=None, database_url="postgresql+psycopg://localhost/x", environment=environment
    )

    assert settings.docs_enabled is enabled
