"""公開工具的查詢邊界：非阻塞查讀、版本更新與真實故障。"""

import asyncio
import json
from threading import current_thread, main_thread
from uuid import UUID

import pytest
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from caliburn.bundles.plan import create_bundle
from caliburn.bundles.plan.services import PLAN_QUERIES
from caliburn.bundles.plan.state import PlanToolState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.plan.application.errors import PlanDataError, PlanQueryError
from caliburn.modules.plan.application.results import PlanView


class ThreadCheckingQueries:
    def __init__(self, error: Exception | None = None):
        self.error = error

    def get_current(self, *, workspace_id: UUID) -> PlanView:
        assert current_thread() is not main_thread()
        if self.error is not None:
            raise self.error
        return PlanView(workspace_id, 7, "保留原文\n下一步")


def runtime_for(
    queries: ThreadCheckingQueries,
) -> ToolRuntime[AgentContext, PlanToolState]:
    return ToolRuntime(
        state={"workspace_id": UUID(int=20), "plan_version": None},
        context=AgentContext(PluginServices({PLAN_QUERIES: queries})),
        config={},
        stream_writer=lambda value: None,
        tool_call_id="read-1",
        store=None,
    )


def test_read_uses_worker_and_updates_version_with_paired_message() -> None:
    read = create_bundle({}).plugins[0].tools[0]
    runtime = runtime_for(ThreadCheckingQueries())

    result = asyncio.run(read.ainvoke({"runtime": runtime}))

    assert isinstance(result, Command)
    assert isinstance(result.update, dict)
    assert set(result.update) == {"plan_version", "messages"}
    assert result.update["plan_version"] == 7
    (message,) = result.update["messages"]
    assert isinstance(message, ToolMessage)
    assert message.tool_call_id == "read-1"
    assert isinstance(message.content, str)
    assert json.loads(message.content) == {"plan": "保留原文\n下一步"}
    assert runtime.state["plan_version"] is None


@pytest.mark.parametrize("error", [PlanQueryError(), PlanDataError()])
def test_read_does_not_disguise_query_or_data_failure_as_empty_plan(
    error: Exception,
) -> None:
    read = create_bundle({}).plugins[0].tools[0]

    with pytest.raises(type(error)):
        asyncio.run(
            read.ainvoke({"runtime": runtime_for(ThreadCheckingQueries(error))})
        )


def test_unread_edit_returns_repair_without_requiring_write_service() -> None:
    edit = create_bundle({}).plugins[0].tools[1]
    runtime = runtime_for(ThreadCheckingQueries())

    result = asyncio.run(
        edit.ainvoke({"diff": "@@\n+不能寫入\n*** End of File", "runtime": runtime})
    )

    assert isinstance(result, str)
    rejection = json.loads(result)
    assert rejection["status"] == "rejected"
    assert rejection["code"] == "source_not_available"
    assert "read_interview_plan" in rejection["next_action"]
    assert runtime.state["plan_version"] is None


@pytest.mark.parametrize("diff", ["", "x" * 16_001], ids=["empty", "oversized"])
def test_invalid_diff_length_is_rejected_before_unread_precondition(diff: str) -> None:
    edit = create_bundle({}).plugins[0].tools[1]
    runtime = runtime_for(ThreadCheckingQueries())

    result = asyncio.run(edit.ainvoke({"diff": diff, "runtime": runtime}))

    assert isinstance(result, str)
    assert json.loads(result)["code"] == "invalid_arguments"
    assert "1–16,000 字元" in json.loads(result)["next_action"]


@pytest.mark.parametrize("tool_index", [0, 1], ids=["read", "edit"])
@pytest.mark.parametrize(
    "extra_field", ["private_extra_field", "workspace_id", "version"]
)
def test_tool_rejects_extra_arguments_without_echoing_input(
    tool_index: int, extra_field: str
) -> None:
    tool = create_bundle({}).plugins[0].tools[tool_index]
    runtime = runtime_for(ThreadCheckingQueries())
    arguments: dict[str, object] = {
        "runtime": runtime,
        extra_field: "private argument value",
    }
    if tool_index == 1:
        arguments["diff"] = "@@\n+不能寫入\n*** End of File"

    result = asyncio.run(tool.ainvoke(arguments))

    assert isinstance(result, str)
    rejection = json.loads(result)
    assert rejection["status"] == "rejected"
    assert rejection["code"] == "invalid_arguments"
    assert extra_field not in result
    assert "private argument value" not in result
    assert runtime.state["plan_version"] is None
