"""真 PostgreSQL 下 Plan 工具的同批讀寫與模型可修正拒絕。"""

import asyncio
from uuid import UUID, uuid4

import httpx2
from sqlalchemy import Engine

from caliburn.modules.plan.application.results import PlanView
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from tests.integration.agent.plan_plugin_support import (
    ScriptedPlanModel,
    edit_call,
    open_plan_agent,
    read_call,
    tool_outputs,
)
from tests.integration.agent.stream_support import consume


def test_plan_tools_advance_same_batch_state_and_preserve_noop_version(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    turn_id = uuid4()
    model = ScriptedPlanModel(
        [
            [
                read_call("before"),
                edit_call("edit", "@@\n+# 訪談計畫\n+確認工作範圍\n*** End of File"),
                read_call("after"),
                edit_call("noop", "@@\n-確認工作範圍\n+確認工作範圍"),
            ],
            None,
        ]
    )

    async def run() -> None:
        async with open_plan_agent(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(model)
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=turn_id, input="安排訪談"
                )
            )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert not saved.next
            assert saved.values.get("plan_turn_id") == turn_id
            assert saved.values.get("plan_turn_start_version") == 1
            assert saved.values["plan_version"] == 2
            assert {key for key in saved.values if key.startswith("plan_")} == {
                "plan_turn_id",
                "plan_turn_start_version",
                "plan_version",
            }

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert SqlAlchemyPlanQueries(pg_engine).get_current(
        workspace_id=jd_workspace_id
    ) == PlanView(jd_workspace_id, 2, "# 訪談計畫\n確認工作範圍")
    assert tool_outputs(model.requests[1]) == {
        "before": {"plan": None},
        "edit": {
            "status": "updated",
            "diff": (
                "--- body_before\n+++ body_after\n@@ -0,0 +1,2 @@\n"
                "+# 訪談計畫\n+確認工作範圍\n\\ No newline at end of file\n"
            ),
        },
        "after": {"plan": "# 訪談計畫\n確認工作範圍"},
        "noop": {"status": "unchanged"},
    }
    tools = {tool["name"]: tool for tool in model.requests[0]["tools"]}
    assert set(tools) == {"read_interview_plan", "edit_interview_plan"}
    assert tools["read_interview_plan"]["parameters"]["properties"] == {}
    edit_schema = tools["edit_interview_plan"]["parameters"]
    assert set(edit_schema["properties"]) == {"diff"}
    assert edit_schema["required"] == ["diff"]
    assert edit_schema["additionalProperties"] is False


def test_unread_and_invalid_patch_rejections_can_be_repaired_in_the_same_batch(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    model = ScriptedPlanModel(
        [
            [
                edit_call("unread", "@@\n+不應寫入\n*** End of File"),
                read_call("before"),
                edit_call("invalid", "not a patch"),
                edit_call("repaired", "@@\n+確認本人範圍\n*** End of File"),
                read_call("after"),
            ],
            None,
        ]
    )

    async def run() -> None:
        async with open_plan_agent(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(model)
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="整理安排"
                )
            )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert not saved.next
            assert saved.values["plan_version"] == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    outputs = tool_outputs(model.requests[1])
    for call_id, code in (
        ("unread", "source_not_available"),
        ("invalid", "invalid_patch"),
    ):
        assert outputs[call_id]["status"] == "rejected"
        assert outputs[call_id]["code"] == code
        assert outputs[call_id]["message"]
        assert outputs[call_id]["next_action"]
    assert outputs["before"] == {"plan": None}
    assert outputs["repaired"]["status"] == "updated"
    assert outputs["after"] == {"plan": "確認本人範圍"}
    assert SqlAlchemyPlanQueries(pg_engine).get_current(
        workspace_id=jd_workspace_id
    ) == PlanView(jd_workspace_id, 2, "確認本人範圍")


def test_out_of_order_hunks_explain_repair_and_preserve_original_until_corrected(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    initial_body = "目前焦點\n核對交接\n工作方向\n盤點"
    model = ScriptedPlanModel(
        [
            [
                read_call("before"),
                edit_call(
                    "initial",
                    "@@\n+目前焦點\n+核對交接\n+工作方向\n+盤點\n*** End of File",
                ),
                edit_call(
                    "reversed", "@@\n-盤點\n+盤點差異\n@@\n-核對交接\n+核對本人範圍"
                ),
                read_call("unchanged"),
                edit_call(
                    "ordered", "@@\n-核對交接\n+核對本人範圍\n@@\n-盤點\n+盤點差異"
                ),
            ],
            None,
        ]
    )

    async def run() -> None:
        async with open_plan_agent(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(model)
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="調整安排"
                )
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    outputs = tool_outputs(model.requests[1])
    assert outputs["reversed"]["code"] == "patch_context_not_found"
    assert "第 2 段" in outputs["reversed"]["message"]
    assert "原文先後" in outputs["reversed"]["next_action"]
    assert outputs["unchanged"] == {"plan": initial_body}
    assert outputs["ordered"]["status"] == "updated"
    assert SqlAlchemyPlanQueries(pg_engine).get_current(
        workspace_id=jd_workspace_id
    ) == PlanView(jd_workspace_id, 3, "目前焦點\n核對本人範圍\n工作方向\n盤點差異")
    edit = next(
        tool
        for tool in model.requests[0]["tools"]
        if tool["name"] == "edit_interview_plan"
    )
    assert "原文先後" in edit["parameters"]["properties"]["diff"]["description"]
