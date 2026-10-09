"""Exercise the production Import Linter policy against real Python module trees."""

import configparser
import os
import subprocess
import sys
from pathlib import Path

import grimp
import pytest

API_ROOT = Path(__file__).parents[2]
SOURCE = API_ROOT / "src/caliburn"
POLICY = API_ROOT / ".importlinter"


def run_linter(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from importlinter.cli import lint_imports_command; lint_imports_command()",
            "--config",
            str(POLICY),
            "--no-cache",
            "--no-logo",
        ],
        cwd=directory,
        env={**os.environ, "PYTHONPATH": str(directory), "PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )


@pytest.fixture
def package_tree(tmp_path: Path) -> Path:
    # Preserve actual package topology, but only supply the imports under test.
    # The fixture never executes product modules or edits the working source tree.
    for source in SOURCE.rglob("*.py"):
        target = tmp_path / "caliburn" / source.relative_to(SOURCE)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    return tmp_path


def write_module(directory: Path, module: str, code: str) -> None:
    directory.joinpath("caliburn", *module.split(".")).with_suffix(".py").write_text(
        code, encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("imports", "broken_contract"),
    [
        ({"features.work_memory.models": "import sqlalchemy"}, "Domain values"),
        (
            {
                "features.job_description.models": "from . import work_queries",
                "features.job_description.work_queries": "import sqlalchemy",
            },
            "Domain values",
        ),
        (
            {
                "features.work_memory.service": (
                    "from caliburn.features.job_description import task_persistence"
                )
            },
            "job_description: persistence belongs",
        ),
        (
            {
                "features.work_memory.service": (
                    "from ..job_description.task_persistence import TaskRecord"
                )
            },
            "job_description: persistence belongs",
        ),
        (
            {
                "features.work_memory.service": (
                    "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n"
                    "    from ..job_description import source_persistence"
                )
            },
            "job_description: persistence belongs",
        ),
        (
            {
                "features.job_description.models": "from .boundary_probe import value",
                "features.job_description.boundary_probe": (
                    "from .task_persistence import TaskRecord as value"
                ),
                "features.job_description.task_persistence": "import sqlalchemy",
            },
            "Domain values",
        ),
        ({"features.work_memory.stage_changes": "import openai"}, "Domain values"),
        ({"features.job_description.item_results": "import fastapi"}, "Domain values"),
        (
            {"features.job_description.service": "from caliburn.contracts import validation"},
            "features: dependencies point",
        ),
        (
            {"workflows.memory_batch": "from caliburn.contracts import generated"},
            "workflows: dependencies point",
        ),
        ({"adapters.database": "from caliburn import settings"}, "adapters: dependencies point"),
        (
            {"agent_execution.nodes": "from caliburn.features.work_memory import models"},
            "agent_execution: dependencies point",
        ),
        ({"transport.http.jd": "import sqlalchemy"}, "Transport delegates persistence"),
        ({"transport.http.jd": "from caliburn import bootstrap"}, "transport: dependencies point"),
        (
            {"features.job_description.service": "from caliburn import app_composition"},
            "Product layers do not import",
        ),
        (
            {"workflows.memory_batch": "from caliburn.diagnostics import inspection"},
            "Product layers do not import",
        ),
        (
            {"agents.job_consultant.prompt": "from ..work_situation_analyst import prompt"},
            "job_consultant: roles cannot",
        ),
        (
            {"agents.memory_analysis.runner": "from ..work_situation_analyst import prompt"},
            "memory_analysis: roles cannot",
        ),
        ({"bootstrap": "import jd_relational"}, "Retired standalone authorities"),
    ],
)
def test_policy_rejects_illegal_import_graph(
    package_tree: Path, imports: dict[str, str], broken_contract: str
) -> None:
    for module, code in imports.items():
        write_module(package_tree, module, code)
    result = run_linter(package_tree)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Broken contracts" in result.stdout, result.stdout
    assert broken_contract in result.stdout.split("Broken contracts", 1)[1], result.stdout


def test_policy_allows_owned_persistence_workflows_and_shared_role_assembly(
    package_tree: Path,
) -> None:
    imports = {
        "transport.http.jd": "from caliburn.workflows import jd_reads",
        "workflows.jd_reads": "from caliburn.features.job_description import task_persistence",
        "features.job_description.service": "from . import task_persistence",
        "features.job_description.task_persistence": "import sqlalchemy",
        "transport.model_tools.memory_reads": "from caliburn.contracts import validation",
        "agents.work_situation_analyst.runner": "from ..memory_analysis import runner",
        "agents.work_understanding_analyst.runner": "from ..memory_analysis import runner",
        "diagnostics.projection": "from caliburn.features.executions import history_models",
    }
    for module, code in imports.items():
        write_module(package_tree, module, code)
    result = run_linter(package_tree)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 broken" in result.stdout


def test_policy_inventory_covers_split_values_and_private_persistence() -> None:
    policy = configparser.ConfigParser()
    policy.read(POLICY, encoding="utf-8")
    pure_modules = set(policy["importlinter:contract:pure-domain"]["source_modules"].split())
    protected_modules = {
        module
        for section in policy.values()
        if section.get("type") == "protected"
        for module in section["protected_modules"].split()
    }
    for path in (SOURCE / "features").rglob("*.py"):
        module = "caliburn." + ".".join(path.relative_to(SOURCE).with_suffix("").parts)
        if path.stem == "models" or path.stem.endswith(("_models", "_changes")):
            assert module in pure_modules, f"Declare the domain boundary for {module}"
        if path.stem == "persistence" or path.stem.endswith("_persistence"):
            assert module in protected_modules, f"Declare the persistence owner for {module}"


def test_graph_includes_every_product_module() -> None:
    graph = grimp.build_graph("caliburn", include_external_packages=True, cache_dir=None)
    expected = set()
    for path in SOURCE.rglob("*.py"):
        parts = path.relative_to(SOURCE.parent).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        expected.add(".".join(parts))
    assert expected <= graph.modules, sorted(expected - graph.modules)


def test_backend_import_boundaries() -> None:
    result = run_linter(API_ROOT / "src")
    assert result.returncode == 0, result.stdout + result.stderr
