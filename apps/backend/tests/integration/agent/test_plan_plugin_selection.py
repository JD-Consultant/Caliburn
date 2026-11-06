"""以公開組裝選 Plugin，替換 Prompt 不改工具與業務保存。"""

import asyncio
from functools import partial
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.bundles.plan.planning_instructions import INTERVIEW_PLAN_INSTRUCTIONS
from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from caliburn.modules.plan.application.plans import initialize_plan, patch_plan
from caliburn.modules.plan.application.results import PlanView
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.http_support import api_client
from tests.integration.agent.plan_plugin_support import (
    ScriptedPlanModel,
    edit_call,
    open_plan_agent,
    read_call,
    tool_outputs,
)
from tests.integration.agent.stream_support import consume
from tests.integration.agent.test_agent_http_cancellation import wait_for_idle
from tests.integration.agent.test_plan_context import plan_materials


def test_all_plan_plugins_disabled_leave_model_request_and_plan_storage_empty(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    model = ScriptedPlanModel([None])

    async def run() -> None:
        async with open_plan_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            plan_plugins=(),
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="只回答"
                )
            )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert not any(key.startswith("plan_") for key in saved.values)

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert model.requests[0]["tools"] == []
    assert INTERVIEW_PLAN_INSTRUCTIONS not in model.requests[0].get("instructions", "")
    assert model.requests[0]["input"] == [{"role": "user", "content": "只回答"}]
    assert SqlAlchemyPlanQueries(pg_engine).get_current(
        workspace_id=jd_workspace_id
    ) == PlanView(jd_workspace_id, None, None)


def test_replacement_prompt_keeps_same_plan_tools_and_successful_storage(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    alternate_prompt = "只根據本次已知資料更新工作計畫，保留未確認事項。"
    model = ScriptedPlanModel(
        [
            [
                read_call("before"),
                edit_call(
                    "updated", "@@\n+盤點只核對數量；金額未確認。\n*** End of File"
                ),
            ],
            None,
        ]
    )
    replacement = AgentBundle(
        plugins=(
            AgentPlugin(
                name="alternate_plan_prompt", prompt_sections=(alternate_prompt,)
            ),
        )
    )

    async def run() -> None:
        async with open_plan_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            plan_plugins=("plan_lifecycle", "plan_tools"),
            extra_bundles=(replacement,),
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="記下盤點範圍"
                )
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert model.requests[0]["instructions"] == alternate_prompt
    assert {tool["name"] for tool in model.requests[0]["tools"]} == {
        "read_interview_plan",
        "edit_interview_plan",
    }
    assert tool_outputs(model.requests[1])["updated"]["status"] == "updated"
    assert SqlAlchemyPlanQueries(pg_engine).get_current(
        workspace_id=jd_workspace_id
    ) == PlanView(jd_workspace_id, 2, "盤點只核對數量；金額未確認。")


@pytest.mark.parametrize(
    "selection",
    [
        (),
        ("plan_tools", "plan_lifecycle"),
        ("plan_lifecycle", "plan_context"),
        ("plan_tools", "plan_lifecycle", "plan_prompt", "plan_context"),
    ],
)
def test_host_window_uses_only_selected_plan_capabilities(
    pg_engine: Engine, checkpoint_conninfo: str, selection: tuple[str, ...]
) -> None:
    can_edit_context = "plan_tools" in selection and "plan_context" in selection
    model = ScriptedPlanModel(
        [
            [edit_call("from_context", "@@\n-已保存的盤點安排\n+核對後的盤點安排")],
            None,
        ]
        if can_edit_context
        else [None]
    )
    factory = partial(SqlAlchemyPlanUnitOfWork, create_session_factory(pg_engine))

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            bundles=(
                BundleConfig("caliburn.bundles.context", plugins=("window",)),
                BundleConfig("caliburn.bundles.plan", plugins=selection),
            ),
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "選取能力"})
            ).json()["workspace_id"]
            initialize_plan(workspace_id=UUID(workspace), uow_factory=factory)
            patch_plan(
                workspace_id=UUID(workspace),
                expected_version=1,
                diff="@@\n+已保存的盤點安排\n*** End of File",
                uow_factory=factory,
            )
            accepted = await client.post(
                f"/workspaces/{workspace}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "說明目前安排"},
            )
            assert accepted.status_code == 202, accepted.text
            turn = await wait_for_idle(client, accepted.headers["Location"])
            assert turn["status"] == "completed", turn
            assert (await client.get(f"/workspaces/{workspace}/plan")).json() == {
                "workspace_id": workspace,
                "version": 3 if can_edit_context else 2,
                "body": "核對後的盤點安排" if can_edit_context else "已保存的盤點安排",
            }

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    request = model.requests[0]
    assert plan_materials(request) == (
        [{"data_kind": "consultant_interview_plan", "plan": "已保存的盤點安排"}]
        if "plan_context" in selection
        else []
    )
    assert {tool["name"] for tool in request["tools"]} == (
        {"read_interview_plan", "edit_interview_plan"}
        if "plan_tools" in selection
        else set()
    )
    assert (INTERVIEW_PLAN_INSTRUCTIONS in request.get("instructions", "")) == (
        "plan_prompt" in selection
    )
    if can_edit_context:
        assert tool_outputs(model.requests[1])["from_context"]["status"] == "updated"


def test_host_can_cancel_existing_turn_after_all_plan_plugins_are_deselected(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    model = ScriptedPlanModel(
        [
            [
                read_call("read"),
                edit_call("edit", "@@\n+需要撤回的安排\n*** End of File"),
            ],
            [],
            None,
        ]
    )
    transport = httpx2.MockTransport(model)

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=(BundleConfig("caliburn.bundles.plan"),),
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "取消接續"})
            ).json()["workspace_id"]
            turns = f"/workspaces/{workspace}/agent/turns"
            plan = f"/workspaces/{workspace}/plan"
            accepted = await client.post(
                turns, json={"turn_id": str(uuid4()), "input": "稍後要取消的修改"}
            )
            assert accepted.status_code == 202, accepted.text
            location = accepted.headers["Location"]
            assert (await wait_for_idle(client, location))["status"] == "interrupted"
            assert (await client.get(plan)).json() == {
                "workspace_id": workspace,
                "version": 2,
                "body": "需要撤回的安排",
            }

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=(BundleConfig("caliburn.bundles.plan", plugins=()),),
        ) as client:
            cancelled = await client.post(location + "/cancel")
            assert cancelled.status_code == 204, cancelled.text
            restored = {
                "workspace_id": workspace,
                "version": 3,
                "body": None,
            }
            assert (await client.get(plan)).json() == restored
            assert (await client.post(location + "/cancel")).status_code == 204
            accepted = await client.post(
                turns, json={"turn_id": str(uuid4()), "input": "重新開始"}
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            assert (await client.get(plan)).json() == restored

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(model.requests) == 3
    assert model.requests[2]["tools"] == []
    assert INTERVIEW_PLAN_INSTRUCTIONS not in model.requests[2].get("instructions", "")
    assert model.requests[2]["input"] == [{"role": "user", "content": "重新開始"}]
