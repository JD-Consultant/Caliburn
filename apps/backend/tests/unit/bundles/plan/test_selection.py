"""Plan Plugin 的明示選取與依賴，不能默默啟用其他能力。"""

import asyncio
from uuid import UUID

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.bundles.plan.services import PLAN_QUERIES, PLAN_UOW_FACTORY
from caliburn.modules.agent.bootstrap import BundleConfig, load_plugins, open_agent
from caliburn.modules.plan.application.persistence import PlanUnitOfWork
from caliburn.modules.plan.application.results import PlanView
from tests.unit.modules.agent.offline_openai import MODEL_REQUEST, offline_client


class UnusedPlanQueries:
    def get_current(self, *, workspace_id: UUID) -> PlanView:
        raise AssertionError("Plugin 啟動不得讀取工作區正文")


def unused_uow() -> PlanUnitOfWork:
    raise AssertionError("Plugin 啟動不得開啟業務交易")


def unused_model(request: httpx2.Request) -> httpx2.Response:
    raise AssertionError("Plugin 啟動不得呼叫模型")


@pytest.mark.parametrize(
    ("selection", "missing"),
    [
        ((), None),
        (("plan_lifecycle",), None),
        (("plan_tools",), "plan_lifecycle"),
        (("plan_prompt",), "plan_tools"),
        (("plan_context",), "plan_lifecycle"),
        (("plan_tools", "plan_lifecycle"), None),
        (("plan_tools", "plan_prompt"), "plan_lifecycle"),
        (("plan_tools", "plan_context"), "plan_lifecycle"),
        (("plan_lifecycle", "plan_prompt"), "plan_tools"),
        (("plan_lifecycle", "plan_context"), None),
        (("plan_prompt", "plan_context"), "plan_tools"),
        (("plan_tools", "plan_lifecycle", "plan_prompt"), None),
        (("plan_tools", "plan_lifecycle", "plan_context"), None),
        (("plan_tools", "plan_prompt", "plan_context"), "plan_lifecycle"),
        (("plan_lifecycle", "plan_prompt", "plan_context"), "plan_tools"),
        (("plan_tools", "plan_lifecycle", "plan_prompt", "plan_context"), None),
    ],
)
def test_selected_plan_plugins_require_explicit_dependencies(
    selection: tuple[str, ...], missing: str | None
) -> None:
    bundles = (BundleConfig("caliburn.bundles.plan", plugins=selection),)
    plugins = load_plugins(bundles)
    assert {plugin.name for plugin in plugins} == set(selection)
    bindings = (
        PLAN_QUERIES.bind(UnusedPlanQueries()),
        PLAN_UOW_FACTORY.bind(unused_uow),
    )

    async def run() -> None:
        async with (
            offline_client(httpx2.MockTransport(unused_model)) as client,
            open_agent(
                agent_id="plan-selection",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=bundles,
                checkpointer=InMemorySaver(),
                external_services=bindings,
            ),
        ):
            pass

    if missing is None:
        asyncio.run(run())
    else:
        with pytest.raises(ValueError, match=missing):
            asyncio.run(run())
