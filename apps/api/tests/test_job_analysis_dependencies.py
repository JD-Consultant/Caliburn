"""Greenfield 邊界的結構檢查(計畫 §0、ADR 0040 決定 3)。

`app/job_analysis` 不得 import 舊 AI 路徑;宣示寫在文件裡會腐化,寫成 AST 測試才會在
有人真的接上去的那一刻紅燈。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


API_DIR = Path(__file__).parents[1]
ROOT = API_DIR / "app" / "job_analysis"
DOMAIN_ROOT = ROOT / "domain"
SHARED_API_DEPS = API_DIR / "app" / "api" / "deps.py"
JOB_ANALYSIS_COMPOSITION_SURFACES = (
    API_DIR / "app" / "api" / "job_analysis_deps.py",
    API_DIR / "app" / "api" / "routes" / "job_analysis.py",
    API_DIR / "app" / "adapters" / "job_analysis_postgres",
)

FORBIDDEN_ROOTS = (
    "app.interview",
    "app.interview_vnext",
    "app.job_authoring",
    "evals",
    "job_analysis_contract",
)

JOB_ANALYSIS_COMPOSITION_FORBIDDEN_ROOTS = (
    "app.interview",
    "app.interview_vnext",
    "app.job_authoring",
    "evals",
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


def _composition_surface_files(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    """Expand declared composition roots and fail loudly on a stale declaration."""

    files: list[Path] = []
    for root in roots:
        assert root.exists(), f"Declared composition surface root is missing: {root}"
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(root.rglob("*.py"))
        else:
            raise AssertionError(
                f"Declared composition surface root is neither a file nor directory: {root}"
            )
    return tuple(sorted(files, key=lambda path: path.as_posix()))


def test_shared_api_deps_does_not_own_job_analysis_composition():
    forbidden_roots = {
        "app.job_analysis",
        "app.adapters.job_analysis_postgres",
    }
    violations = [
        f"{SHARED_API_DEPS.relative_to(API_DIR)}:{line} imports {module}"
        for line, module in _imports(SHARED_API_DEPS)
        if module in forbidden_roots or any(
            module.startswith(f"{forbidden}.") for forbidden in forbidden_roots
        )
    ]
    assert violations == []


def test_job_analysis_composition_surfaces_never_import_legacy_paths():
    violations: list[str] = []
    for path in _composition_surface_files(JOB_ANALYSIS_COMPOSITION_SURFACES):
        for line, module in _imports(path):
            for forbidden in JOB_ANALYSIS_COMPOSITION_FORBIDDEN_ROOTS:
                if module == forbidden or module.startswith(f"{forbidden}."):
                    violations.append(
                        f"{path.relative_to(API_DIR)}:{line} imports {module}"
                    )
    assert violations == []


def test_job_analysis_never_imports_legacy_ai_paths():
    violations: list[str] = []
    for path in ROOT.rglob("*.py"):
        for line, module in _imports(path):
            for forbidden in FORBIDDEN_ROOTS:
                if module == forbidden or module.startswith(f"{forbidden}."):
                    violations.append(
                        f"{path.relative_to(ROOT)}:{line} imports {module}"
                    )
    assert violations == []


def test_domain_imports_only_stdlib_pydantic_or_itself():
    violations: list[str] = []
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
    """核心 package 只認 ports；DB adapter 住在 app/adapters，不得反向滲入。"""
    forbidden_roots = {
        "alembic",
        "asyncpg",
        "fastapi",
        "psycopg",
        "sqlalchemy",
        "starlette",
    }
    violations: list[str] = []
    for path in ROOT.rglob("*.py"):
        for line, module in _imports(path):
            if module.split(".", 1)[0] in forbidden_roots:
                violations.append(f"{path.relative_to(ROOT)}:{line} imports {module}")
    assert violations == []
