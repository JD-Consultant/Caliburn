"""取消後從前成功窗口或新版 Memory 重建，Plan 恢復後可繼續編輯。"""

import asyncio
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine

from caliburn.modules.agent.infrastructure.openai.call_model import ModelResponseError
from caliburn.modules.plan.application.results import PlanView
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from tests.integration.agent.memory_reference_support import interview_ref
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
    tool,
)
from tests.integration.agent.test_plan_context import plan_materials


def test_cancelled_edit_cold_reopen_continues_previous_window_and_restored_plan(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    references = "\n\n- 訪談：`message_101`\n- 工作：[待確認](task_102)"
    initial_body = "輪前安排" + references
    first_reply = complete("成功輪回覆")
    model = OfflineMemoryModel(
        [
            [
                edit_call(
                    "initial",
                    "@@\n+" + initial_body.replace("\n", "\n+") + "\n*** End of File",
                )
            ],
            first_reply,
            [edit_call("cancelled", "@@\n-輪前安排\n+取消輪安排")],
            None,
            [edit_call("old_version", "@@\n-輪前安排\n+繼續安排")],
            [read_call("restored")],
            [edit_call("continue", "@@\n-輪前安排\n+繼續安排")],
            complete("新輪成功"),
        ]
    )
    queries = SqlAlchemyPlanQueries(pg_engine)
    cancelled, next_turn = uuid4(), uuid4()

    async def run() -> None:
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True
        ) as (agent, _, _):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="第一輪原話"
                )
            )
            first = await agent.aget_state(workspace_id=jd_workspace_id)
            assert first.values["plan_version"] == 2
            with pytest.raises(ModelResponseError):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=cancelled,
                        input="必須排除的取消輪原話",
                    )
                )
            assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
                jd_workspace_id, 3, "取消輪安排" + references
            )
            await agent.acancel_turn(workspace_id=jd_workspace_id, turn_id=cancelled)
            await agent.acancel_turn(workspace_id=jd_workspace_id, turn_id=cancelled)
            assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
                jd_workspace_id, 4, initial_body
            )
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True, initialize=False
        ) as (agent, _, _):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=next_turn,
                    input="重新開始原話",
                )
            )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert saved.values["plan_turn_id"] == next_turn
            assert saved.values["plan_turn_start_version"] == 4
            assert saved.values["plan_version"] == 5
            prefix = [
                *model.requests[1]["input"],
                *first_reply,
            ]
            assert model.requests[4]["input"][: len(prefix)] == prefix
            assert_turn_input(
                model.requests[4]["input"][len(prefix) :],
                engine=pg_engine,
                workspace_id=jd_workspace_id,
                turn_id=next_turn,
                text="重新開始原話",
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert tool_outputs(model.requests[5])["old_version"]["code"] == "target_stale"
    assert tool_outputs(model.requests[6])["restored"] == {"plan": initial_body}
    assert tool_outputs(model.requests[7])["continue"]["status"] == "updated"
    assert "取消輪" not in json.dumps(model.requests[4]["input"], ensure_ascii=False)
    assert (
        queries.get_current(workspace_id=jd_workspace_id).body
        == "繼續安排" + references
    )


def test_cancelled_first_turn_on_new_memory_rebuilds_and_edits_restored_version(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    references = "\n\n- [ ] 核對 message_101 與 task_102\n- 公版：`occupation_103`"
    initial_body = "換版前安排" + references
    model = OfflineMemoryModel(
        [
            [
                edit_call(
                    "initial",
                    "@@\n+" + initial_body.replace("\n", "\n+") + "\n*** End of File",
                ),
                tool("request_memory_consolidation", "request"),
            ],
            complete("舊版成功"),
            lambda request: [
                tool(
                    "create_work_situation",
                    "s",
                    title="盤點",
                    description="核對庫存",
                    body="逐筆核對。",
                    interview_references=[interview_ref(request, "盤點原話")],
                )
            ],
            complete(),
            [
                tool(
                    "create_work_understanding",
                    "u",
                    title="盤點責任",
                    description="本人核對",
                    body="本人核對差異。",
                    work_situation_references=["盤點"],
                )
            ],
            complete(),
            [edit_call("cancelled", "@@\n-換版前安排\n+新版取消安排")],
            None,
            [edit_call("renewed", "@@\n-換版前安排\n+換版後繼續安排")],
            complete("重新建立成功"),
        ]
    )
    first_turn, cancelled = uuid4(), uuid4()
    queries = SqlAlchemyPlanQueries(pg_engine)

    async def run() -> None:
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True
        ) as (agent, coordinator, _):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=first_turn, input="盤點原話"
                )
            )
            published = await coordinator.run(
                workspace_id=jd_workspace_id, turn_id=first_turn
            )
            assert published is not None
            assert tool_outputs(model.requests[3])["s"]["status"] == "created"
            assert tool_outputs(model.requests[5])["u"]["status"] == "created"
            assert {
                item.content.title: item.content.body for item in published.items
            } == {"盤點": "逐筆核對。", "盤點責任": "本人核對差異。"}
            with pytest.raises(ModelResponseError):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=cancelled,
                        input="取消新版原話",
                    )
                )
            assert (
                queries.get_current(workspace_id=jd_workspace_id).body
                == "新版取消安排" + references
            )
            await agent.acancel_turn(workspace_id=jd_workspace_id, turn_id=cancelled)
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True, initialize=False
        ) as (agent, _, _):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="新版繼續原話"
                )
            )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert saved.values["memory_published_version"] == published.version
            assert saved.values["plan_turn_start_version"] == 4
            assert saved.values["plan_version"] == 5

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    expected = [{"data_kind": "consultant_interview_plan", "plan": initial_body}]
    assert plan_materials(model.requests[6]) == expected
    assert plan_materials(model.requests[8]) == expected
    assert all(item.get("role") == "user" for item in model.requests[8]["input"])
    assert "取消新版原話" not in json.dumps(
        model.requests[8]["input"], ensure_ascii=False
    )
    assert tool_outputs(model.requests[9])["renewed"]["status"] == "updated"
    assert (
        queries.get_current(workspace_id=jd_workspace_id).body
        == "換版後繼續安排" + references
    )
