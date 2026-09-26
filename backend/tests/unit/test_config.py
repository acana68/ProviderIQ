from pathlib import Path

from app.core.config import REPO_ROOT, _repo_root


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
