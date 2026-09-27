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
