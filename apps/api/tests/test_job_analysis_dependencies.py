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

FORBIDDEN_ROOTS = (
    "app.interview",
    "app.interview_vnext",
    "app.job_authoring",
    "evals",
    "job_analysis_contract",
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
