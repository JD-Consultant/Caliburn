"""One durable native model/tool Step; product completion and control remain outside it."""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass, field
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
    ensure_active: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class HeldModelResponse:
    """Process-local recovery handoff, never a replacement for a durable checkpoint.

    Only pass this object back to the same Step. Do not serialize it into logs or
    product history. Its operation seed is retained along with the exact native R.
    """

    thread_id: str
    input_items: NativeItems = field(repr=False)
    update: ResponseStepState = field(repr=False)


class ResponseStepSaveError(RuntimeError):
    """No tools started from this R; the caller can retry saving the held original."""

    def __init__(self, recovery: HeldModelResponse) -> None:
        super().__init__(
            "The original model result is held; reconcile its checkpoint before retrying"
        )
        self.recovery = recovery


async def run_response_step(
    checkpointer: BaseCheckpointSaver[str],
    *,
    thread_id: str,
    input_items: NativeItems | None,
    runtime: ResponseStepRuntime,
    max_tool_calls: int,
    recovery: HeldModelResponse | None = None,
) -> ResponseStepState:
    """Start a fresh Step or resume it with None; callers still own single-writer eligibility.

    A Step uses one dedicated thread identity. A completed Step may be read/resumed but
    not restarted with new input. A role's outer loop carries its resulting window forward.
    """
    if not thread_id:
        raise ValueError("A durable Step requires a nonempty thread identity")
    if recovery is not None and (recovery.thread_id != thread_id or input_items is not None):
        raise ValueError("A held response can only resume its original Step with None")
    # The small holder belongs to this invocation, not to the role or the saver.
    # Clearing it on entry to prepare means later tool/protocol errors cannot
    # accidentally be classified as model persistence errors.
    held = recovery

    def retain(input_items: NativeItems, update: ResponseStepState) -> None:
        nonlocal held
        held = HeldModelResponse(thread_id, deepcopy(input_items), deepcopy(update))

    def release() -> None:
        nonlocal held
        held = None

    graph = _build_response_step(
        checkpointer,
        max_tool_calls=max_tool_calls,
        retain_response=retain,
        release_response=release,
    )
    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 2 * max_tool_calls + 8,
    }
    await runtime.ensure_active()
    try:
        saved = await graph.aget_state(config)
    except Exception as error:
        if held is not None:
            raise ResponseStepSaveError(held) from error
        raise
    if input_items is not None and saved.created_at is not None:
        raise ValueError("This Step already exists; resume with None instead of new input")
    if input_items is None and saved.created_at is None:
        raise ValueError("There is no saved Step to resume")
    if recovery is not None:
        if "response_snapshot" in saved.values:
            if any(
                saved.values.get(key) != recovery.update[key]
                for key in ("response_snapshot", "operation_seed")
            ):
                raise ValueError("The saved Step contains a different model result")
            # A confirmed R (including native pending writes) wins. In particular,
            # never overwrite later prepared commands, observations or completed items.
            held = None
        else:
            if (
                saved.next != ("request_model",)
                or saved.values.get("input_items") != recovery.input_items
                or saved.values.get("tool_results")
                or saved.values.get("prepared_tool") is not None
                or saved.values.get("next_action") is not None
            ):
                raise ValueError("The held response does not match the saved request boundary")
            await runtime.ensure_active()
            try:
                await graph.aupdate_state(
                    config, deepcopy(recovery.update), as_node="request_model"
                )
            except Exception as error:
                raise ResponseStepSaveError(recovery) from error
    initial_state: ResponseStepState | None = (
        {"input_items": input_items} if input_items is not None else None
    )
    try:
        result = await graph.ainvoke(
            initial_state,
            config,
            context=runtime,
            durability="sync",
            version="v2",
        )
    except Exception as error:
        if held is not None:
            raise ResponseStepSaveError(held) from error
        raise
    await runtime.ensure_active()
    return result.value


def _build_response_step(
    checkpointer: BaseCheckpointSaver[str],
    *,
    max_tool_calls: int,
    retain_response: Callable[[NativeItems, ResponseStepState], None] | None = None,
    release_response: Callable[[], None] | None = None,
) -> CompiledStateGraph[
    ResponseStepState, ResponseStepRuntime, ResponseStepState, ResponseStepState
]:
    """Internal graph; production callers use run_response_step for enforced invocation rules."""
    if type(max_tool_calls) is not int or max_tool_calls < 1:
        raise ValueError("Configure a positive per-response tool bound")

    async def request_model(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        await runtime.context.ensure_active()
        response = await runtime.context.request_model(deepcopy(state["input_items"]))
        update: ResponseStepState = {
            "response_snapshot": snapshot_response(response),
            "operation_seed": uuid4(),
            "prepared_tool": None,
            "tool_results": [],
            "next_action": None,
        }
        if retain_response is not None:
            retain_response(state["input_items"], update)
        return update

    async def prepare_tool(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        if release_response is not None:
            release_response()
        await runtime.context.ensure_active()
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
        await runtime.context.ensure_active()
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

    async def finish_step(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        await runtime.context.ensure_active()
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
