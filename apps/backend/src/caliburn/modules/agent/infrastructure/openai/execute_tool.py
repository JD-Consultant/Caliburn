"""一次執行一個工具；位置由當批已接回的結果推導。"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast

from langchain_core.messages import AIMessage, ToolCall, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.config import get_config
from langgraph.errors import GraphBubbleUp
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import AsyncToolCallWrapper, ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.infrastructure.diagnostics import log_failure
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.state import (
    AgentLimitError,
    AgentState,
    request_items,
)


def completed_tool_count(state: AgentState) -> int:
    """當批結果只接在最新 SDK output 後方，不另存 operation 游標。"""
    count = 0
    for item in reversed(request_items(state["model_request"])):
        if not isinstance(item, dict) or item.get("type") != "function_call_output":
            break
        count += 1
    return count


def has_pending_tools(state: AgentState) -> bool:
    response = state["model_response"]
    assert response is not None
    return completed_tool_count(state) < sum(
        item.type == "function_call" for item in response.output
    )


logger = logging.getLogger(__name__)


class OpenAIToolNode:
    def __init__(
        self,
        tools: tuple[StructuredTool, ...],
        max_tool_calls: int,
        plugin_fields: set[str],
        *,
        wrap_tool_call: tuple[AsyncToolCallWrapper, ...] = (),
    ):
        self._tools = {tool.name: tool for tool in tools}
        self._max_tool_calls = max_tool_calls
        self._wrappers = wrap_tool_call
        self._node = ToolNode(
            list(tools),
            handle_tool_errors=False,
            awrap_tool_call=self._wrap_tool_call if wrap_tool_call else None,
        )
        self._plugin_fields = plugin_fields

    async def _wrap_tool_call(
        self,
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[object]]],
    ) -> ToolMessage | Command[object]:
        async def invoke(
            index: int, current: ToolCallRequest
        ) -> ToolMessage | Command[object]:
            if index == len(self._wrappers):
                return await execute(current)
            executed = False

            async def next_wrapper(
                updated: ToolCallRequest,
            ) -> ToolMessage | Command[object]:
                nonlocal executed
                if executed:
                    raise ValueError("Tool wrappers may execute at most once")
                executed = True
                return await invoke(index + 1, updated)

            return await self._wrappers[index](current, next_wrapper)

        return await invoke(0, request)

    async def __call__(
        self, state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        try:
            return await self._execute(state, get_config())
        except GraphBubbleUp:
            raise
        except Exception as error:
            log_failure(
                logger,
                event="agent.tool.failed",
                error=error,
                execution=runtime.execution_info,
            )
            raise

    async def _execute(self, state: AgentState, config: RunnableConfig) -> AgentState:
        request = state["model_request"]
        tools = {
            declaration["name"]: self._tools[declaration["name"]]
            for declaration in request.get("tools", ())
            if declaration["type"] == "function"
        }
        response = state["model_response"]
        assert response is not None
        calls = [item for item in response.output if item.type == "function_call"]
        if len(calls) > self._max_tool_calls:
            raise AgentLimitError("Tool call limit exceeded")
        pending: list[ToolCall] = []
        seen: set[str] = set()
        # 先驗完整批次的協定；Pydantic 欄位驗證仍由 StructuredTool 負責。
        for call in calls:
            if call.status not in (None, "completed"):
                raise ValueError("Function call is not completed")
            if (
                not isinstance(call.call_id, str)
                or not call.call_id
                or call.call_id in seen
            ):
                raise ValueError("Function call requires a unique call_id")
            seen.add(call.call_id)
            if call.name not in tools:
                raise ValueError(f"Unknown function: {call.name}")
            pending.append(
                {
                    "type": "tool_call",
                    "name": call.name,
                    "id": call.call_id,
                    # strict 工具契約由 SDK 解析，欄位驗證交給 StructuredTool。
                    "args": cast(dict[str, Any], call.parsed_arguments),
                }
            )
        items = list(request_items(request))
        tool_call = pending[completed_tool_count(state)]
        call_id = tool_call["id"]
        assert call_id is not None
        raw = await self._node.ainvoke(
            {**state, "messages": [AIMessage(content="", tool_calls=[tool_call])]},
            config=config,
        )
        update, output = _tool_result(raw, call_id, self._plugin_fields)
        items.append(
            {
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            }
        )
        return cast(
            AgentState,
            {
                **update,
                "model_request": {**request, "input": cast(ResponseInputParam, items)},
            },
        )


def _tool_result(
    raw: object, call_id: str, plugin_fields: set[str]
) -> tuple[dict[str, object], str]:
    """集中歸一官方 ToolNode 的普通訊息／單一 Command 容器。"""
    if isinstance(raw, list):
        if len(raw) != 1:
            raise ValueError("Agent tool bridge requires exactly one tool result")
        raw = raw[0]
    if isinstance(raw, Command):
        if raw.graph is not None or raw.goto or raw.resume is not None:
            raise ValueError("Tool Command cannot change Core routing")
        raw = raw.update
    if not isinstance(raw, dict):
        raise ValueError("Agent tool bridge requires a State update")
    update = dict(raw)
    messages = update.pop("messages", None)
    if not isinstance(messages, list) or len(messages) != 1:
        raise ValueError("Agent tool bridge requires one ToolMessage")
    message = messages[0]
    if not isinstance(message, ToolMessage) or message.tool_call_id != call_id:
        raise ValueError("ToolMessage must match the current call_id")
    if not isinstance(message.content, str):
        raise ValueError("Agent tool bridge requires text output")
    if unknown := update.keys() - plugin_fields:
        raise ValueError(
            "Tool Command cannot update undeclared or Core fields: "
            f"{', '.join(sorted(unknown))}"
        )
    return update, message.content
