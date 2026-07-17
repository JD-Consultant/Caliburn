from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1] / "app" / "interview_vnext"
DOMAIN_ROOT = ROOT / "domain"


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
    return found


def test_vnext_never_imports_v3_interview_internals():
    violations: list[str] = []
    for path in ROOT.rglob("*.py"):
        for line, module in _imports(path):
            if module == "app.interview" or module.startswith("app.interview."):
                violations.append(f"{path.relative_to(ROOT)}:{line} imports {module}")
    assert violations == []

def test_domain_imports_only_stdlib_pydantic_or_itself():
    violations: list[str] = []
    for path in DOMAIN_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            root = module.split(".", 1)[0]
            allowed = (
                root in sys.stdlib_module_names
                or root == "pydantic"
                or module == "app.interview_vnext.domain"
                or module.startswith("app.interview_vnext.domain.")
            )
            if not allowed:
                violations.append(f"{path.relative_to(DOMAIN_ROOT)}:{line} imports {module}")
    assert violations == []


def test_application_and_domain_never_import_persistence_frameworks():
    """V2-B §6:application ports 是純 Protocol/DTO;SQLAlchemy/driver 只准住
    persistence adapter。domain 一併鎖(比 stdlib+pydantic 白名單再多一道明示)。"""
    forbidden_roots = {"sqlalchemy", "alembic", "asyncpg", "psycopg"}
    violations: list[str] = []
    for relative_root in ("application", "domain"):
        for path in (ROOT / relative_root).rglob("*.py"):
            for line, module in _imports(path):
                if module.split(".", 1)[0] in forbidden_roots:
                    violations.append(f"{path.relative_to(ROOT)}:{line} imports {module}")
    assert violations == []


def test_neutral_llm_and_capture_contracts_do_not_import_provider_or_agent_sdks():
    forbidden_roots = {
        "anthropic",
        "openai",
        "langchain",
        "langgraph",
        "pydantic_ai",
    }
    violations: list[str] = []
    for relative_root in ("llm", "observability"):
        for path in (ROOT / relative_root).rglob("*.py"):
            for line, module in _imports(path):
                if module.split(".", 1)[0] in forbidden_roots:
                    violations.append(f"{path.relative_to(ROOT)}:{line} imports {module}")
    assert violations == []
