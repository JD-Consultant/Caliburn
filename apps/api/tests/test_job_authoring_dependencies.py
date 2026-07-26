"""Import/dependency guards for the Job Authoring Core (plan §14.9, §4, §6.2).

The pure core imports only the standard library, Pydantic, and its own package.
The whole package never imports the legacy ``app.interview`` editor, the OCS
contract, or any agent framework; the interview vNext domain never depends back
on authoring. These lock structure, so a warm pytest process is not enough —
one case re-checks a clean import in a cold interpreter.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

API_DIR = Path(__file__).parents[1]
JA_ROOT = API_DIR / "app" / "job_authoring"
VNEXT_DOMAIN = API_DIR / "app" / "interview_vnext" / "domain"
APP_ROOT = API_DIR / "app"

# The pure core (plan §4): stdlib + Pydantic + same package only.
PURE_CORE = (
    "contracts.py",
    "commands.py",
    "canonical.py",
    "transitions.py",
    "digest.py",
    "errors.py",
    "schema_exports.py",
    "write_schemas.py",
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


def test_pure_core_imports_only_stdlib_pydantic_or_itself() -> None:
    violations: list[str] = []
    for name in PURE_CORE:
        for line, module in _imports(JA_ROOT / name):
            root = module.split(".", 1)[0]
            allowed = (
                root in sys.stdlib_module_names
                or root == "pydantic"
                or module == "app.job_authoring"
                or module.startswith("app.job_authoring.")
            )
            if not allowed:
                violations.append(f"{name}:{line} imports {module}")
    assert violations == []


def test_pure_core_never_imports_persistence_or_provider_or_interview() -> None:
    forbidden_roots = {
        "sqlalchemy",
        "alembic",
        "asyncpg",
        "psycopg",
        "fastapi",
        "anthropic",
        "openai",
    }
    violations: list[str] = []
    for name in PURE_CORE:
        for line, module in _imports(JA_ROOT / name):
            root = module.split(".", 1)[0]
            if (
                root in forbidden_roots
                or module == "app.interview"
                or module.startswith("app.interview.")
                or module.startswith("app.interview_vnext")
                or root == "ocs_contract"
            ):
                violations.append(f"{name}:{line} imports {module}")
    assert violations == []


def test_authoring_package_never_imports_legacy_editor_or_agent_frameworks() -> None:
    forbidden_roots = {"langchain", "langgraph", "pydantic_ai"}
    violations: list[str] = []
    for path in JA_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            if (
                module.split(".", 1)[0] in forbidden_roots
                or module == "app.interview"
                or module.startswith("app.interview.")
            ):
                rel = path.relative_to(JA_ROOT)
                violations.append(f"{rel}:{line} imports {module}")
    assert violations == []


def test_interview_vnext_domain_never_imports_job_authoring() -> None:
    violations: list[str] = []
    for path in VNEXT_DOMAIN.rglob("*.py"):
        for line, module in _imports(path):
            if module == "app.job_authoring" or module.startswith("app.job_authoring."):
                rel = path.relative_to(VNEXT_DOMAIN)
                violations.append(f"{rel}:{line} imports {module}")
    assert violations == []


def test_authoring_never_imports_eval_adapter() -> None:
    violations: list[str] = []
    for path in JA_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            if module == "evals" or module.startswith("evals."):
                rel = path.relative_to(JA_ROOT)
                violations.append(f"{rel}:{line} imports {module}")
    assert violations == []


def test_pure_core_imports_cleanly_in_a_cold_process() -> None:
    script = (
        "from app.job_authoring import canonical, contracts, commands\n"
        "from app.job_authoring import transitions, digest, errors\n"
        "from app.job_authoring import schema_exports, write_schemas\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=API_DIR,
        env={**os.environ, "PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        timeout=180,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 0, proc.stderr
