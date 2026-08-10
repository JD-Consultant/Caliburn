"""Static guards for the current-only API and engine boundaries."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


API_DIR = Path(__file__).parents[1]
ROOT = API_DIR / "app" / "job_analysis"
DOMAIN_ROOT = ROOT / "domain"
COMPOSITION_SURFACES = (
    API_DIR / "app" / "api" / "job_analysis_deps.py",
    API_DIR / "app" / "api" / "routes" / "job_analysis.py",
    API_DIR / "app" / "adapters" / "job_analysis_postgres",
)


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
    return found


def _surface_files(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    files: list[Path] = []
    for root in roots:
        assert root.exists(), f"missing current composition root: {root}"
        files.extend(root.rglob("*.py") if root.is_dir() else [root])
    return tuple(sorted(files, key=lambda path: path.as_posix()))


def test_only_current_api_route_modules_exist():
    route_names = {path.name for path in (API_DIR / "app" / "api" / "routes").glob("*.py")}
    assert route_names == {"__init__.py", "job_analysis.py"}


def test_current_composition_does_not_import_removed_paths():
    forbidden = (
        "app.interview",
        "app.interview_vnext",
        "app.job_authoring",
        "app.core",
        "app.services",
        "app.schemas",
        "indexer_contract",
        "ocs_contract",
    )
    violations = []
    for path in _surface_files(COMPOSITION_SURFACES):
        for line, module in _imports(path):
            if any(module == root or module.startswith(f"{root}.") for root in forbidden):
                violations.append(f"{path.relative_to(API_DIR)}:{line} imports {module}")
    assert violations == []


def test_job_analysis_domain_imports_only_stdlib_pydantic_or_itself():
    violations = []
    for path in DOMAIN_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            root = module.split(".", 1)[0]
            allowed = (
                root in sys.stdlib_module_names
                or root == "pydantic"
                or module == "app.job_analysis.domain"
                or module.startswith("app.job_analysis.domain.")
            )
            if not allowed:
                violations.append(f"{path.relative_to(DOMAIN_ROOT)}:{line} imports {module}")
    assert violations == []


def test_job_analysis_never_imports_persistence_or_web_frameworks():
    forbidden = {"alembic", "asyncpg", "fastapi", "psycopg", "sqlalchemy", "starlette"}
    violations = []
    for path in ROOT.rglob("*.py"):
        for line, module in _imports(path):
            if module.split(".", 1)[0] in forbidden:
                violations.append(f"{path.relative_to(ROOT)}:{line} imports {module}")
    assert violations == []
