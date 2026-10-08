"""Small AST checks for the high-value dependency rules in code-organization.md."""

import ast
import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[2] / "src/caliburn"

# Layers import downward only (code-organization.md §2). Each key lists the top-level packages
# that sit above it and therefore must never be imported by it. `bootstrap` is the root: nothing
# imports it. `memory_analysis` is the B1/B2 common assembly that both role packages may use.
ABOVE = {
    "adapters": {
        "features",
        "agent_execution",
        "workflows",
        "transport",
        "agents",
        "settings",
        "bootstrap",
    },
    "features": {"workflows", "transport", "agents", "bootstrap"},
    "agent_execution": {"workflows", "transport", "bootstrap"},
    "workflows": {"transport", "agents", "bootstrap"},
    "transport": {"agents", "bootstrap"},
    "agents": {"bootstrap"},
}
COMMON_AGENT_ASSEMBLY = "memory_analysis"


def violations(module: str, code: str) -> list[str]:
    found = []
    source = module.split(".")
    for node in ast.walk(ast.parse(code)):
        targets: list[str] = []
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = importlib.util.resolve_name(
                    "." * node.level + base, module.rpartition(".")[0]
                )
            targets = [f"{base}.{alias.name}" for alias in node.names]
        for target in targets:
            dependency = target.split(".")
            forbidden = dependency[0] in {"jd_relational", "caliburn_memory"}
            is_feature = source[:2] == ["caliburn", "features"] and len(source) > 3
            pure_values = source[3] == "models" if is_feature else False
            pure_values |= module in {
                "caliburn.features.job_description.areas",
                "caliburn.features.job_description.tasks",
                "caliburn.features.job_description.task_changes",
                "caliburn.features.work_memory.changes",
                "caliburn.features.work_memory.revisions",
                "caliburn.features.work_memory.candidates",
            }
            if pure_values:
                forbidden |= dependency[0] in {"fastapi", "sqlalchemy", "langgraph", "openai"}
                forbidden |= target.startswith("caliburn.contracts.generated.")
            if source[:2] == ["caliburn", "agent_execution"]:
                forbidden |= dependency[:2] in [["caliburn", "agents"], ["caliburn", "features"]]
            if source[:2] == ["caliburn", "transport"]:
                forbidden |= dependency[0] in {"sqlalchemy", "psycopg"}
            if len(source) > 1 and dependency[:1] == ["caliburn"] and len(dependency) > 1:
                forbidden |= dependency[1] in ABOVE.get(source[1], ())
                # 組裝選項與 bootstrap 同層，領域或 transport 不得反向匯入。
                forbidden |= dependency[1] == "app_composition" and source[1] in ABOVE
            for group in ("features", "agents"):
                if (
                    len(source) > 2
                    and len(dependency) > 3
                    and source[:2] == dependency[:2] == ["caliburn", group]
                    and source[2] != dependency[2]
                ):
                    if group == "agents":
                        forbidden |= dependency[2] != COMMON_AGENT_ASSEMBLY
                    else:
                        forbidden |= dependency[3] == "persistence"
            if forbidden:
                found.append(f"{module}:{node.lineno} cannot import {target}")
    return found


@pytest.mark.parametrize(
    ("module", "code"),
    [
        ("caliburn.features.work_memory.models", "from sqlalchemy import Column"),
        ("caliburn.features.job_description.tasks", "import fastapi"),
        ("caliburn.features.job_description.task_changes", "import sqlalchemy"),
        ("caliburn.features.work_memory.changes", "import sqlalchemy"),
        ("caliburn.features.work_memory.revisions", "import sqlalchemy"),
        ("caliburn.features.work_memory.candidates", "import sqlalchemy"),
        (
            "caliburn.features.work_memory.models",
            "from caliburn.contracts.generated import health_status",
        ),
        ("caliburn.agent_execution.nodes", "from caliburn.agents.job_consultant import prompt"),
        ("caliburn.agent_execution.nodes", "from caliburn.features.work_memory import persistence"),
        ("caliburn.transport.http.jd", "import sqlalchemy"),
        ("caliburn.agents.job_consultant.prompt", "from ..work_situation_analyst import prompt"),
        ("caliburn.features.job_description.queries", "from ..work_memory import persistence"),
        ("caliburn.bootstrap", "import jd_relational"),
        ("caliburn.bootstrap", "import caliburn_memory"),
        ("caliburn.bootstrap", "from caliburn_memory import publication"),
        # Upward imports: a lower layer must not reach a layer that is composed on top of it.
        ("caliburn.workflows.memory_batch", "from caliburn.transport.model_tools import contracts"),
        ("caliburn.workflows.memory_batch", "from caliburn.agents.job_consultant import runner"),
        ("caliburn.features.job_description.service", "from caliburn.workflows import jd_reads"),
        ("caliburn.adapters.database", "from caliburn.features.executions import models"),
        ("caliburn.adapters.database", "from caliburn.settings import DatabaseSettings"),
        ("caliburn.agent_execution.tool_steps", "from caliburn.workflows import model_requests"),
        ("caliburn.transport.http.jd", "from caliburn.agents.job_consultant import runner"),
        ("caliburn.transport.http.jd", "from caliburn import bootstrap"),
        ("caliburn.features.job_description.service", "from caliburn import app_composition"),
        (
            "caliburn.agents.job_consultant.runner",
            "from caliburn.app_composition import AppComposition",
        ),
        # The common B1/B2 assembly is shared, but the two roles never reach each other.
        (
            "caliburn.agents.work_situation_analyst.runner",
            "from caliburn.agents.work_understanding_analyst import instructions",
        ),
        (
            "caliburn.agents.memory_analysis.runner",
            "from caliburn.agents.work_situation_analyst import instructions",
        ),
    ],
)
def test_forbidden_dependency_is_detected(module: str, code: str) -> None:
    assert violations(module, code)


def test_explicit_service_collaboration_is_allowed() -> None:
    assert not violations(
        "caliburn.workflows.memory_batch", "from caliburn.features.work_memory import service"
    )
    assert not violations(
        "caliburn.agents.job_consultant.tools", "from caliburn.features.work_memory import queries"
    )


def test_both_memory_roles_may_use_the_common_analysis_assembly() -> None:
    for role in ("work_situation_analyst", "work_understanding_analyst"):
        assert not violations(
            f"caliburn.agents.{role}.runner", "from caliburn.agents.memory_analysis import runner"
        )
    assert not violations(
        "caliburn.workflows.memory_batch",
        "from caliburn.workflows.memory_analysis.results import MemoryAnalysisResult",
    )


def test_backend_import_boundaries() -> None:
    found = []
    for path in SOURCE.rglob("*.py"):
        relative = path.relative_to(SOURCE.parent).with_suffix("")
        module = ".".join(relative.parts)
        found.extend(violations(module, path.read_text(encoding="utf-8")))
    assert not found, "\n".join(found)
