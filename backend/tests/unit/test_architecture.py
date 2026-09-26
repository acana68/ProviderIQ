"""The ranking engine and geo helpers must stay pure Python: no database, no web framework."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = BACKEND_DIR / "app" / "services"
FORBIDDEN = ("sqlalchemy", "fastapi", "app.database")

# Every module in services/ranking/, plus these single modules.
PURE_MODULES = sorted((SERVICES_DIR / "ranking").rglob("*.py")) + [SERVICES_DIR / "geo.py"]


def _is_forbidden(module: str) -> bool:
    return any(module == name or module.startswith(f"{name}.") for name in FORBIDDEN)


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


def test_pure_modules_exist() -> None:
    assert len(PURE_MODULES) >= 4
    assert all(path.exists() for path in PURE_MODULES)


@pytest.mark.parametrize("path", PURE_MODULES, ids=_module_name)
def test_module_does_not_import_forbidden_packages(path: Path) -> None:
    violations = [
        f"{path.name}:{line} imports {module}"
        for line, module in _imported_modules(path)
        if _is_forbidden(module)
    ]

    assert not violations, violations


def test_importing_pure_modules_does_not_load_forbidden_packages_indirectly() -> None:
    """Catches indirect imports too, e.g. ranking -> app.models -> sqlalchemy.

    Runs in a fresh interpreter, because this test process has already imported everything.
    """
    code = (
        "import importlib, sys\n"
        f"for name in {[_module_name(path) for path in PURE_MODULES]!r}:\n"
        "    importlib.import_module(name)\n"
        f"forbidden = {FORBIDDEN!r}\n"
        "print('\\n'.join(sorted(m for m in sys.modules\n"
        "    if any(m == f or m.startswith(f + '.') for f in forbidden))))\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND_DIR, capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == ""
