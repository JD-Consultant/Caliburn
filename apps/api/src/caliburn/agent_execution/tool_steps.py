"""One durable native model/tool Step; product completion and control remain outside it."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, TypedDict
from uuid import UUID, uuid4, uuid5

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from openai.types.responses import Response, ResponseFunctionToolCall
from openai.types.responses.response_input_item_param import FunctionCallOutput

from caliburn.adapters.response_serialization import (
    NativeItems,
    NativeSnapshot,
    function_result_item,
    require_result_order,
    response_input_items,
    restore_response,
    snapshot_response,
)
from caliburn.agent_execution.response_steps import ResponseAction, inspect_response_step


class ResponseStepState(TypedDict, total=False):
    input_items: NativeItems
    response_snapshot: NativeSnapshot
    operation_seed: UUID
    prepared_tool: object | None
    tool_results: list[FunctionCallOutput]
    next_action: Literal["continue", "deliver_answer"] | None


@dataclass(frozen=True, slots=True)
class ResponseStepRuntime:
    """Injected I/O, not persisted State. The tool owner validates its prepared command type."""

    request_model: Callable[[NativeItems], Awaitable[Response]]
    prepare_tool: Callable[[ResponseFunctionToolCall, UUID], Awaitable[object]]
    execute_tool: Callable[[object], Awaitable[str]]


async def run_response_step(
    checkpointer: BaseCheckpointSaver[str],
    *,
    thread_id: str,
    input_items: NativeItems | None,
    runtime: ResponseStepRuntime,
    max_tool_calls: int,
) -> ResponseStepState:
    """Start a fresh Step or resume it with None; callers still own single-writer eligibility.

    A Step uses one dedicated thread identity. A completed Step may be read/resumed but
    not restarted with new input. A role's outer loop carries its resulting window forward.
    """
    if not thread_id:
        raise ValueError("A durable Step requires a nonempty thread identity")
    graph = _build_response_step(checkpointer, max_tool_calls=max_tool_calls)
    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 2 * max_tool_calls + 8,
    }
    saved = await graph.aget_state(config)
    if input_items is not None and saved.created_at is not None:
        raise ValueError("This Step already exists; resume with None instead of new input")
    if input_items is None and saved.created_at is None:
        raise ValueError("There is no saved Step to resume")
    initial_state: ResponseStepState | None = (
        {"input_items": input_items} if input_items is not None else None
    )
    result = await graph.ainvoke(
        initial_state,
        config,
        context=runtime,
        durability="sync",
        version="v2",
    )
    return result.value


def _build_response_step(
    checkpointer: BaseCheckpointSaver[str],
    *,
    max_tool_calls: int,
) -> CompiledStateGraph[
    ResponseStepState, ResponseStepRuntime, ResponseStepState, ResponseStepState
]:
    """Internal graph; production callers use run_response_step for enforced invocation rules."""
    if type(max_tool_calls) is not int or max_tool_calls < 1:
        raise ValueError("Configure a positive per-response tool bound")

    async def request_model(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        response = await runtime.context.request_model(state["input_items"])
        return {
            "response_snapshot": snapshot_response(response),
            "operation_seed": uuid4(),
            "prepared_tool": None,
            "tool_results": [],
            "next_action": None,
        }

    async def prepare_tool(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        # Inspection is after R's node boundary so unsupported output is still recoverable.
        calls = inspect_response_step(restore_response(state["response_snapshot"])).calls
        if len(calls) > max_tool_calls:
            raise ValueError("The response exceeds this execution's configured tool bound")
        require_result_order(calls, state["tool_results"])
        if len(state["tool_results"]) == len(calls):
            return {"prepared_tool": None}
        call = calls[len(state["tool_results"])]
        operation_id = uuid5(state["operation_seed"], call.call_id)
        prepared = await runtime.context.prepare_tool(call, operation_id)
        if isinstance(prepared, str):
            return {
                "prepared_tool": None,
                "tool_results": [*state["tool_results"], function_result_item(call, prepared)],
            }
        if prepared is None:
            raise ValueError("A tool must return a prepared command or a definite observation")
        return {"prepared_tool": prepared}

    async def execute_tool(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        calls = inspect_response_step(restore_response(state["response_snapshot"])).calls
        require_result_order(calls, state["tool_results"])
        prepared = state["prepared_tool"]
        if prepared is None or len(state["tool_results"]) == len(calls):
            raise ValueError("There is no saved command waiting for execution")
        call = calls[len(state["tool_results"])]
        output = await runtime.context.execute_tool(prepared)
        if not isinstance(output, str):
            raise TypeError("The tool owner must return a definite string observation")
        return {
            "prepared_tool": None,
            "tool_results": [*state["tool_results"], function_result_item(call, output)],
        }

    def route_prepared(
        state: ResponseStepState,
    ) -> Literal["prepare_tool", "execute_tool", "finish_step"]:
        if state["prepared_tool"] is not None:
            return "execute_tool"
        calls = inspect_response_step(restore_response(state["response_snapshot"])).calls
        return "prepare_tool" if len(state["tool_results"]) < len(calls) else "finish_step"

    def finish_step(state: ResponseStepState) -> ResponseStepState:
        response = restore_response(state["response_snapshot"])
        step = inspect_response_step(response)
        require_result_order(step.calls, state["tool_results"])
        if len(state["tool_results"]) != len(step.calls) or state["prepared_tool"] is not None:
            raise ValueError("A complete Step cannot have unresolved tool results")
        return {
            "input_items": [
                *state["input_items"],
                *response_input_items(response),
                *(dict(item) for item in state["tool_results"]),
            ],
            "next_action": "deliver_answer"
            if step.action == ResponseAction.DELIVER_ANSWER
            else "continue",
        }

    graph = StateGraph(ResponseStepState, context_schema=ResponseStepRuntime)
    graph.add_node("request_model", request_model)
    graph.add_node("prepare_tool", prepare_tool)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("finish_step", finish_step)
    graph.add_edge(START, "request_model")
    graph.add_edge("request_model", "prepare_tool")
    graph.add_conditional_edges("prepare_tool", route_prepared)
    graph.add_edge("execute_tool", "prepare_tool")
    graph.add_edge("finish_step", END)
    return graph.compile(checkpointer=checkpointer)
