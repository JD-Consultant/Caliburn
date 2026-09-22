"""Structural guards for the greenfield professional consultant core."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path


API_DIR = Path(__file__).parents[1]
CORE_ROOT = API_DIR / "app" / "professional_consultant"
APP_ROOT = API_DIR / "app"
R1_EVAL_ROOT = API_DIR / "evals" / "professional_consultant" / "r1"


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
    return found


def test_core_imports_only_stdlib_pydantic_or_itself() -> None:
    violations: list[str] = []
    for path in CORE_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            root = module.split(".", 1)[0]
            allowed = (
                root in sys.stdlib_module_names
                or root == "pydantic"
                or module == "app.professional_consultant"
                or module.startswith("app.professional_consultant.")
            )
            if not allowed:
                violations.append(
                    f"{path.relative_to(CORE_ROOT)}:{line} imports {module}"
                )
    assert violations == []


def test_core_never_imports_legacy_vnext_or_forbidden_frameworks() -> None:
    forbidden_roots = {
        "sqlalchemy",
        "alembic",
        "asyncpg",
        "psycopg",
        "fastapi",
        "anthropic",
        "openai",
        "langchain",
        "langgraph",
        "pydantic_ai",
        "torch",
        "evals",
    }
    violations: list[str] = []
    for path in CORE_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            root = module.split(".", 1)[0]
            if (
                root in forbidden_roots
                or module == "app.interview"
                or module.startswith("app.interview.")
                or module == "app.interview_vnext"
                or module.startswith("app.interview_vnext.")
                or module == "app.job_authoring"
                or module.startswith("app.job_authoring.")
            ):
                violations.append(
                    f"{path.relative_to(CORE_ROOT)}:{line} imports {module}"
                )
    assert violations == []


def test_production_app_does_not_import_r1_eval_assets() -> None:
    violations: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            if module == "evals" or module.startswith("evals."):
                violations.append(
                    f"{path.relative_to(APP_ROOT)}:{line} imports {module}"
                )
    assert violations == []


def test_r1_eval_harness_never_imports_legacy_or_provider_frameworks() -> None:
    forbidden_roots = {
        "sqlalchemy",
        "alembic",
        "asyncpg",
        "psycopg",
        "fastapi",
        "anthropic",
        "openai",
        "langchain",
        "langgraph",
        "pydantic_ai",
        "torch",
    }
    violations: list[str] = []
    for path in R1_EVAL_ROOT.glob("*.py"):
        for line, module in _imports(path):
            root = module.split(".", 1)[0]
            if (
                root in forbidden_roots
                or module == "app.interview"
                or module.startswith("app.interview.")
                or module == "app.interview_vnext"
                or module.startswith("app.interview_vnext.")
                or module == "app.job_authoring"
                or module.startswith("app.job_authoring.")
            ):
                violations.append(
                    f"{path.relative_to(R1_EVAL_ROOT)}:{line} imports {module}"
                )
    assert violations == []


def test_contracts_and_verifier_import_cleanly_in_a_cold_process() -> None:
    script = (
        "from app.professional_consultant import contracts, prompts, runner\n"
        "from app.professional_consultant import schema_projection, verifier\n"
        "contracts.TaskDiscoveryOutput.model_json_schema()\n"
        "schema_projection.provider_schema_for(\n"
        "    prompts.OperationName.TASK_DISCOVERY,\n"
        "    schema_projection.SchemaProfile.LIGHT,\n"
        ")\n"
        "from evals.professional_consultant.r1 import ablation, capture, harness\n"
        "from evals.professional_consultant.r1 import minimal_harness\n"
        "from evals.professional_consultant.r1 import observed_provider\n"
        "from evals.professional_consultant.r1 import blind_projection, grader\n"
        "from evals.professional_consultant.r1 import grader_capture\n"
        "assert len(ablation.ABLATION_ARMS) == 6\n"
        "grader.blind_grader_prompt()\n"
        "grader.blind_grader_output_schema()\n"
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


def test_t2_public_runner_seams_are_exported_from_the_package() -> None:
    import app.professional_consultant as consultant

    assert consultant.run_task_discovery_once
    assert consultant.run_task_discovery_two_stage
    assert consultant.StructuredOutputProvider
    assert consultant.OperationRunError
