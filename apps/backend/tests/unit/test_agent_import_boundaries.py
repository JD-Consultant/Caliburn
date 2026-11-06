"""新 Agent 邊界必須由實際匯入圖攔截反向依賴。"""

from pathlib import Path

import pytest

from tests.unit.test_import_boundaries import check_imports


@pytest.mark.parametrize(
    "module, source, contract",
    [
        (
            "modules/agent/application/agent_service.py",
            "\nimport fastapi\n",
            "Agent application owns coordination without business storage "
            "or HTTP BROKEN",
        ),
        (
            "modules/agent/presentation/api/router.py",
            "\nfrom caliburn.modules.agent.agent import Agent\n",
            "Agent HTTP only calls application capabilities BROKEN",
        ),
        (
            "modules/agent/agent.py",
            "\nfrom caliburn.modules.agent.application import agent_service\n",
            "Agent Core entry does not depend on application or HTTP BROKEN",
        ),
    ],
)
def test_agent_architecture_rejects_reverse_dependencies(
    tmp_path: Path, module: str, source: str, contract: str
) -> None:
    result = check_imports(tmp_path, module, source)
    assert result.returncode == 1
    assert contract in result.stdout
