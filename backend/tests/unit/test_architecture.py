"""Import boundaries that are design rules, enforced:

- The ranking engine and geo helpers are pure Python: no database, no web framework.
- The AI package never touches repositories or the database (docs/architecture.md). The
  LLM can only return criteria; it has no path to data.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"

# group name -> (modules, packages they must not import, directly or indirectly)
BOUNDARIES: dict[str, tuple[list[Path], tuple[str, ...]]] = {
    "ranking": (
        sorted((APP_DIR / "services" / "ranking").rglob("*.py"))
        + [APP_DIR / "services" / "geo.py"],
        ("sqlalchemy", "fastapi", "app.database"),
    ),
    "ai": (
        sorted((APP_DIR / "ai").rglob("*.py")),
        ("sqlalchemy", "fastapi", "app.database", "app.repositories", "app.models"),
    ),
}

CASES = [
    pytest.param(path, forbidden, id=f"{group}:{path.relative_to(APP_DIR).as_posix()}")
    for group, (paths, forbidden) in BOUNDARIES.items()
    for path in paths
]


def _is_forbidden(module: str, forbidden: tuple[str, ...]) -> bool:
    return any(module == name or module.startswith(f"{name}.") for name in forbidden)


def _module_name(path: Path) -> str:
    """app/services/ranking/__init__.py -> app.services.ranking"""
    return ".".join(path.relative_to(BACKEND_DIR).with_suffix("").parts).removesuffix(".__init__")


def _imported_modules(path: Path) -> list[tuple[int, str]]:
    """(line, absolute module name) for every import statement in the file."""
    package = list(path.relative_to(BACKEND_DIR).with_suffix("").parts[:-1])
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            # Resolve relative imports ("from ..database import x") against the package.
            base = package[: len(package) - node.level + 1] if node.level else []
            module = ".".join(base + (node.module.split(".") if node.module else []))
            found.append((node.lineno, module))
            # "from app import database" imports app.database too.
            found += [(node.lineno, f"{module}.{alias.name}") for alias in node.names]
    return found


@pytest.mark.parametrize("group", BOUNDARIES)
def test_boundary_covers_real_modules(group: str) -> None:
    paths, _ = BOUNDARIES[group]
    assert len(paths) >= 4
    assert all(path.exists() for path in paths)


@pytest.mark.parametrize(("path", "forbidden"), CASES)
def test_module_does_not_import_forbidden_packages(path: Path, forbidden: tuple[str, ...]) -> None:
    violations = [
        f"{path.name}:{line} imports {module}"
        for line, module in _imported_modules(path)
        if _is_forbidden(module, forbidden)
    ]

    assert not violations, violations


@pytest.mark.parametrize("group", BOUNDARIES)
def test_importing_does_not_load_forbidden_packages_indirectly(group: str) -> None:
    """Catches indirect imports too, e.g. ranking -> app.models -> sqlalchemy.

    Runs in a fresh interpreter, because this test process has already imported everything.
    """
    paths, forbidden = BOUNDARIES[group]
    code = (
        "import importlib, sys\n"
        f"for name in {[_module_name(path) for path in paths]!r}:\n"
        "    importlib.import_module(name)\n"
        f"forbidden = {forbidden!r}\n"
        "print('\\n'.join(sorted(m for m in sys.modules\n"
        "    if any(m == f or m.startswith(f + '.') for f in forbidden))))\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND_DIR, capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == ""
