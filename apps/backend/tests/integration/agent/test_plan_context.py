"""Plan 投影與版本沿完整 Context 窗口接續；使用真業務庫與原生保存。"""

import asyncio
import json
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine

from caliburn.modules.plan.application.plans import initialize_plan, patch_plan
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.plan_context_support import assert_turn_input
from tests.integration.agent.plan_plugin_support import (
    edit_call,
    read_call,
    tool_outputs,
)
from tests.integration.agent.stream_support import consume
from tests.integration.agent.test_memory_flow import (
    OfflineMemoryModel,
    complete,
    open_memory_flow,
)


def plan_materials(request: dict[str, Any]) -> list[dict[str, Any]]:
    materials = []
    for item in request["input"]:
        if item.get("role") != "user" or not isinstance(item.get("content"), str):
            continue
        try:
            value = json.loads(item["content"])
        except json.JSONDecodeError:
            continue
        if (
            isinstance(value, dict)
            and value.get("data_kind") == "consultant_interview_plan"
        ):
            materials.append(value)
    return materials


@pytest.mark.parametrize("initial_body", [None, ""])
def test_injected_empty_plan_can_be_edited_and_same_version_continues(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    initial_body: str | None,
) -> None:
    factory = partial(SqlAlchemyPlanUnitOfWork, create_session_factory(pg_engine))
    original = initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    if initial_body == "":
        patch_plan(
            workspace_id=jd_workspace_id,
            expected_version=1,
            diff="@@\n+暫存安排\n*** End of File",
            uow_factory=factory,
        )
        original = patch_plan(
            workspace_id=jd_workspace_id,
            expected_version=2,
            diff="@@\n-暫存安排",
            uow_factory=factory,
        ).plan
    assert original.body == initial_body
    assert original.version is not None
    initial_version = original.version
    first_reply = complete("第一輪成功")
    model = OfflineMemoryModel(
        [
            [edit_call("create", "@@\n+輪前安排\n*** End of File")],
            first_reply,
            [edit_call("continue", "@@\n-輪前安排\n+後續安排")],
            complete("第二輪成功"),
        ]
    )
    next_turn = uuid4()

    async def run() -> None:
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True
        ) as (agent, _, _):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="建立安排"
                )
            )
            first = await agent.aget_state(workspace_id=jd_workspace_id)
            assert first.values["plan_turn_start_version"] == initial_version
            assert first.values["plan_version"] == initial_version + 1
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=next_turn, input="繼續安排"
                )
            )
            second = await agent.aget_state(workspace_id=jd_workspace_id)
            assert second.values["plan_turn_start_version"] == initial_version + 1
            assert second.values["plan_version"] == initial_version + 2
            prefix = [
                *model.requests[1]["input"],
                *first_reply,
            ]
            assert model.requests[2]["input"][: len(prefix)] == prefix
            assert_turn_input(
                model.requests[2]["input"][len(prefix) :],
                engine=pg_engine,
                workspace_id=jd_workspace_id,
                turn_id=next_turn,
                text="繼續安排",
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert plan_materials(model.requests[0]) == [
        {"data_kind": "consultant_interview_plan", "plan": initial_body}
    ]
    assert plan_materials(model.requests[2]) == plan_materials(model.requests[0])
    assert tool_outputs(model.requests[1])["create"]["status"] == "updated"
    assert tool_outputs(model.requests[3])["continue"]["status"] == "updated"
    assert (
        SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=jd_workspace_id).body
        == "後續安排"
    )


def test_same_window_keeps_observed_version_when_current_plan_changes(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyPlanUnitOfWork, create_session_factory(pg_engine))
    initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+模型已見安排\n*** End of File",
        uow_factory=factory,
    )
    model = OfflineMemoryModel(
        [
            complete("已看到安排"),
            [edit_call("stale", "@@\n-模型已見安排\n+錯誤覆蓋")],
            [read_call("refresh")],
            [edit_call("updated", "@@\n-外部更新安排\n+核對後安排")],
            complete("完成"),
        ]
    )

    async def run() -> None:
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True
        ) as (agent, _, _):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="查看安排"
                )
            )
            patch_plan(
                workspace_id=jd_workspace_id,
                expected_version=2,
                diff="@@\n-模型已見安排\n+外部更新安排",
                uow_factory=factory,
            )
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="繼續修改"
                )
            )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert saved.values["plan_turn_start_version"] == 3
            assert saved.values["plan_version"] == 4

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert tool_outputs(model.requests[2])["stale"]["code"] == "target_stale"
    assert tool_outputs(model.requests[3])["refresh"] == {"plan": "外部更新安排"}
    assert tool_outputs(model.requests[4])["updated"]["status"] == "updated"
    assert plan_materials(model.requests[1]) == [
        {"data_kind": "consultant_interview_plan", "plan": "模型已見安排"}
    ]
