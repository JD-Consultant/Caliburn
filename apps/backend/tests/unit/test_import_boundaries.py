"""以真正匯入圖確認架構規則能攔截錯誤依賴。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "module, added_source, contract",
    [
        pytest.param(
            "modules/agent/agent.py",
            "\nfrom caliburn.modules.model_references import contracts\n",
            "Agent remains independent of model references BROKEN",
            id="agent_model_references",
        ),
        pytest.param(
            "modules/model_references/persistence.py",
            "\nfrom caliburn.modules.agent import state\n",
            "Model references do not depend on business modules or Agent BROKEN",
            id="model_references_agent",
        ),
        pytest.param(
            "bundles/job_description/reading.py",
            "\nfrom caliburn.modules.model_references import persistence\n",
            "Bundles use public model reference contracts BROKEN",
            id="bundle_reference_storage",
        ),
        pytest.param(
            "bundles/job_reference/tools.py",
            "\nfrom caliburn.modules.occupation_reference.infrastructure.qdrant "
            "import store\n",
            "Job Reference Bundle uses public reference and plugin contracts BROKEN",
            id="reference_bundle_private_storage",
        ),
        pytest.param(
            "bundles/job_reference/tools.py",
            "\nfrom caliburn.modules.occupation_reference.presentation.api "
            "import projection\n",
            "Job Reference Bundle uses public reference and plugin contracts BROKEN",
            id="reference_bundle_http_projection",
        ),
        pytest.param(
            "modules/occupation_reference/application/search.py",
            "\nfrom caliburn.modules.agent import state\n",
            (
                "Occupation reference owns public sources "
                "without Agent or employee state BROKEN"
            ),
            id="occupation_reference_agent",
        ),
        pytest.param(
            "modules/occupation_reference/application/search.py",
            "\nfrom qdrant_client import QdrantClient\n",
            "Application depends on domain and owned ports BROKEN",
            id="occupation_reference_application_storage",
        ),
        pytest.param(
            "modules/agent/infrastructure/langgraph/agent_graph.py",
            "\nfrom caliburn.modules.occupation_reference.application import search\n",
            "Agent loop does not depend on business or transport BROKEN",
            id="agent_occupation_reference",
        ),
        pytest.param(
            "modules/memory/application/service.py",
            "\nfrom caliburn.modules.agent import state\n",
            "Memory does not depend on Agent or Bundles BROKEN",
            id="memory_agent",
        ),
        pytest.param(
            "modules/memory/infrastructure/persistence/repository.py",
            "\nfrom caliburn.modules.interview.infrastructure.persistence "
            "import orm_models\n",
            "Memory uses public Workspace and Interview persistence queries BROKEN",
            id="memory_private_interview",
        ),
        pytest.param(
            "bundles/memory/__init__.py",
            "\nfrom caliburn.modules.memory.infrastructure.persistence "
            "import repository\n",
            "Memory Bundle uses public module and plugin contracts BROKEN",
            id="memory_bundle_storage",
        ),
        pytest.param(
            "modules/agent/infrastructure/langgraph/agent_graph.py",
            "\nfrom caliburn.modules.memory.application import service\n",
            "Agent loop does not depend on business or transport BROKEN",
            id="agent_memory",
        ),
        pytest.param(
            "bundles/plan/__init__.py",
            "\nfrom caliburn.modules.plan.infrastructure.persistence "
            "import repository\n",
            "Plan Bundle uses public module and plugin contracts BROKEN",
            id="plan_bundle_private_storage",
        ),
        pytest.param(
            "bundles/plan/__init__.py",
            "\nfrom caliburn.modules.agent.infrastructure.openai import execute_tool\n",
            "Plan Bundle uses public module and plugin contracts BROKEN",
            id="plan_bundle_core_adapter",
        ),
        pytest.param(
            "modules/interview/application/recording.py",
            "\nfrom caliburn.modules.agent import state\n",
            "Interview owns dialogue without Agent or Bundles BROKEN",
            id="interview_agent",
        ),
        pytest.param(
            "modules/agent/infrastructure/langgraph/agent_graph.py",
            "\nfrom caliburn.modules.interview.application import recording\n",
            "Agent loop does not depend on business or transport BROKEN",
            id="agent_interview",
        ),
        pytest.param(
            "modules/plan/infrastructure/persistence/repository.py",
            "\nfrom caliburn.modules.workspace.infrastructure.persistence "
            "import orm_models\n",
            "Plan uses public Workspace persistence queries BROKEN",
            id="plan_private_workspace_orm",
        ),
        pytest.param(
            "modules/plan/application/plans.py",
            "\nfrom caliburn.modules.agent import state\n",
            "Plan does not depend on Agent or Bundles BROKEN",
            id="plan_agent",
        ),
        pytest.param(
            "modules/plan/application/plans.py",
            "\nfrom caliburn.bundles.human_questions import create_bundle\n",
            "Plan does not depend on Agent or Bundles BROKEN",
            id="plan_bundle",
        ),
        (
            "modules/plan/domain/plan.py",
            "\nfrom sqlalchemy import select\n",
            "Domain does not depend on application or technical adapters BROKEN",
        ),
        (
            "modules/plan/application/plans.py",
            "\nfrom caliburn.modules.plan.infrastructure.persistence import queries\n",
            "Application depends on domain and owned ports BROKEN",
        ),
        (
            "modules/plan/presentation/api/router.py",
            "\nfrom caliburn.modules.plan.infrastructure.persistence import queries\n",
            "HTTP does not know concrete storage BROKEN",
        ),
        (
            "modules/agent/agent.py",
            "\nfrom caliburn.modules.plan.domain import plan\n",
            "Agent Core entry does not depend on application or HTTP BROKEN",
        ),
        (
            "modules/agent/application/agent_service.py",
            "\nfrom caliburn.modules.plan.application import plans\n",
            "Agent application owns coordination without business storage "
            "or HTTP BROKEN",
        ),
        (
            "modules/job_description/domain/models/job_description.py",
            "\nfrom sqlalchemy import select\n",
            "Domain does not depend on application or technical adapters BROKEN",
        ),
        (
            "modules/workspace/domain/workspace.py",
            "\nfrom ..application import workspace_service\n",
            "Domain does not depend on application or technical adapters BROKEN",
        ),
        (
            "modules/workspace/application/workspace_service.py",
            "\nfrom typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n    import sqlalchemy\n",
            "Application depends on domain and owned ports BROKEN",
        ),
        (
            "modules/workspace/application/workspace_service.py",
            "\nfrom langgraph.graph import StateGraph\n",
            "Application depends on domain and owned ports BROKEN",
        ),
        (
            "modules/workspace/application/workspace_service.py",
            "\nimport openai\n",
            "Application depends on domain and owned ports BROKEN",
        ),
        (
            "modules/workspace/presentation/api/router.py",
            "\nfrom caliburn.shared.infrastructure.persistence import database\n",
            "HTTP does not know concrete storage BROKEN",
        ),
        (
            "shared/presentation/api/errors.py",
            "\nfrom caliburn.modules.workspace.domain import workspace\n",
            "Shared code does not depend on business modules BROKEN",
        ),
        (
            "shared/infrastructure/persistence/database.py",
            "\nfrom caliburn.modules.workspace.domain import workspace\n",
            "Shared code does not depend on business modules BROKEN",
        ),
        (
            "modules/agent/infrastructure/langgraph/agent_graph.py",
            "\nfrom caliburn.modules.job_description.application "
            "import job_description_results\n",
            "Agent loop does not depend on business or transport BROKEN",
        ),
        (
            "modules/agent/infrastructure/langgraph/agent_graph.py",
            "\nimport fastapi\n",
            "Agent loop does not depend on business or transport BROKEN",
        ),
        (
            "modules/agent/infrastructure/langgraph/agent_graph.py",
            "\nfrom caliburn.bundles.human_questions import create_bundle\n",
            "Agent loop does not depend on business or transport BROKEN",
        ),
        pytest.param(
            "modules/agent/application/agent_service.py",
            "\nfrom caliburn.modules.human_questions.questions import Question\n",
            "Agent application owns coordination without business storage "
            "or HTTP BROKEN",
            id="agent_application_questions",
        ),
        pytest.param(
            "modules/agent/presentation/api/schemas.py",
            "\nfrom caliburn.modules.human_questions.questions import Question\n",
            "Agent HTTP only calls application capabilities BROKEN",
            id="agent_http_questions",
        ),
        pytest.param(
            "modules/agent/application/agent_service.py",
            "\nfrom caliburn.bundles.human_questions import create_bundle\n",
            "Agent application owns coordination without business storage "
            "or HTTP BROKEN",
            id="agent_application_bundle",
        ),
        pytest.param(
            "modules/agent/presentation/api/schemas.py",
            "\nfrom caliburn.bundles.human_questions import create_bundle\n",
            "Agent HTTP only calls application capabilities BROKEN",
            id="agent_http_bundle",
        ),
        pytest.param(
            "modules/human_questions/questions.py",
            "\nfrom caliburn.bundles.human_questions import create_bundle\n",
            "Human questions only interpret supplied data BROKEN",
            id="human_questions_bundle",
        ),
        pytest.param(
            "modules/human_questions/questions.py",
            "\nfrom caliburn.modules.agent.application import views\n",
            "Human questions only interpret supplied data BROKEN",
            id="human_questions_application",
        ),
        pytest.param(
            "modules/human_questions/questions.py",
            "\nfrom caliburn.modules.agent.presentation.api import schemas\n",
            "Human questions only interpret supplied data BROKEN",
            id="human_questions_http",
        ),
        pytest.param(
            "modules/human_questions/questions.py",
            "\nfrom langgraph.checkpoint.base import BaseCheckpointSaver\n",
            "Human questions only interpret supplied data BROKEN",
            id="human_questions_saver",
        ),
        pytest.param(
            "modules/agent/infrastructure/langgraph/agent_graph.py",
            "\nfrom caliburn.modules.human_questions.questions import Question\n",
            "Agent loop does not depend on business or transport BROKEN",
            id="agent_loop_questions",
        ),
        pytest.param(
            "modules/agent/agent.py",
            "\nfrom caliburn.modules.human_questions.questions import Question\n",
            "Agent Core entry does not depend on application or HTTP BROKEN",
            id="agent_core_questions",
        ),
        (
            "modules/agent/infrastructure/openai/call_model.py",
            "\nfrom caliburn.modules.workspace.domain import workspace\n",
            "Model adapter does not depend on business or transport BROKEN",
        ),
        (
            "modules/agent/infrastructure/openai/execute_tool.py",
            "\nfrom caliburn.modules.job_description.application "
            "import job_description_results\n",
            "Model adapter does not depend on business or transport BROKEN",
        ),
        (
            "modules/agent/infrastructure/openai/call_model.py",
            "\nfrom caliburn.modules.agent.infrastructure.langgraph "
            "import agent_graph\n",
            "Model adapter does not depend on business or transport BROKEN",
        ),
        (
            "modules/agent/plugins/contracts.py",
            "\nfrom caliburn.modules.agent import bootstrap\n",
            "Agent contracts and preparation do not depend on business "
            "or adapters BROKEN",
        ),
        (
            "modules/agent/plugins/services.py",
            "\nfrom caliburn.modules.agent.plugins import contracts\n",
            "Internal packages and modules are acyclic BROKEN",
        ),
        (
            "modules/agent/state.py",
            "\nfrom caliburn.modules.agent import bootstrap\n",
            "Internal packages and modules are acyclic BROKEN",
        ),
        (
            "modules/agent/plugins/hooks.py",
            "\nfrom caliburn.modules.workspace.domain import workspace\n",
            "Agent contracts and preparation do not depend on business "
            "or adapters BROKEN",
        ),
    ],
)
def test_architecture_gate_rejects_forbidden_dependencies(
    tmp_path: Path, module: str, added_source: str, contract: str
) -> None:
    """實際匯入圖須攔截跨層、型別註記及共用層反向引用業務的依賴。"""
    result = check_imports(tmp_path, module, added_source)
    assert result.returncode == 1, result.stdout + result.stderr
    assert contract in result.stdout


def test_model_adapter_can_use_native_graph_runtime(tmp_path: Path) -> None:
    """模型 adapter 可用框架 Runtime，仍不依賴本地 Graph 組裝。"""
    result = check_imports(
        tmp_path,
        "modules/agent/infrastructure/openai/call_model.py",
        "\nfrom langgraph.runtime import Runtime\n",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_plan_can_compose_public_workspace_query(tmp_path: Path) -> None:
    """Plan 可透過 Workspace 公開 selectable 間接使用其持久資料。"""
    result = check_imports(
        tmp_path,
        "modules/plan/infrastructure/persistence/queries.py",
        "\nfrom caliburn.modules.workspace.infrastructure.persistence.public_queries "
        "import select_workspace_id\n",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def check_imports(
    tmp_path: Path, module: str, added_source: str
) -> subprocess.CompletedProcess[str]:
    package = tmp_path / "caliburn"
    shutil.copytree(
        BACKEND_ROOT / "src/caliburn",
        package,
        ignore=shutil.ignore_patterns("data", "__pycache__"),
    )
    target = package / module
    target.write_text(
        target.read_text(encoding="utf-8") + added_source, encoding="utf-8"
    )
    executable = Path(sys.executable).parent / (
        "lint-imports.exe" if os.name == "nt" else "lint-imports"
    )
    env = {**os.environ, "PYTHONPATH": str(tmp_path), "PYTHONUTF8": "1"}
    return subprocess.run(
        [
            str(executable),
            "--config",
            str(BACKEND_ROOT / ".importlinter"),
            "--no-cache",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
