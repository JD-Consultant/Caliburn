"""Durable native model/tool Steps; product completion and control remain outside them."""

from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Literal, TypedDict, cast
from uuid import UUID, uuid4, uuid5

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, Interrupt, interrupt
from openai.types.responses import Response, ResponseFunctionToolCall
from openai.types.responses.response_input_item_param import FunctionCallOutput

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import (
    NativeItems,
    NativeSnapshot,
    function_result_item,
    require_result_order,
    response_input_items,
    restore_response,
    snapshot_response,
)
from caliburn.agent_execution.context_windows import SavedContextWindow, read_context_checkpoint
from caliburn.agent_execution.request_capacity import (
    CompactionRequiredError,
    ModelCapacityLimits,
    ReceivedInputCount,
    RequestCapacityError,
    require_request_capacity,
    require_request_limits,
    validate_capacity_limits,
)
from caliburn.agent_execution.response_steps import ResponseAction, inspect_response_step
from caliburn.agent_execution.result_save_retries import ResultSaveRetryPolicy, retry_result_save


async def read_completed_response_history(
    checkpointer: BaseCheckpointSaver[str], *, thread_id: str, checkpoint_id: str | None = None
) -> SavedContextWindow:
    """Read an exact complete Graph result, without invoking or replaying any node.

    A final R is insufficient: its tools, Step save and control boundary must be done.
    This is not product completion; only the owning transaction may adopt this position.
    """
    saved = await read_context_checkpoint(
        checkpointer, thread_id=thread_id, checkpoint_id=checkpoint_id
    )
    values = saved.checkpoint["channel_values"]
    if values.get("next_action") != "deliver_answer":
        raise ValueError("The response history has not completed")

    async def read_only_pause() -> bool:
        raise RuntimeError("A history reader must never execute Graph controls")

    async def read_only_acknowledge() -> None:
        raise RuntimeError("A history reader must never execute Graph controls")

    controls = (
        ResponseLoopControls(read_only_pause, read_only_acknowledge)
        if values["pause_enabled"]
        else None
    )
    graph = _build_response_step(
        checkpointer,
        max_tool_calls=values["tool_call_limit"],
        max_model_steps=values["model_step_limit"],
        controls=controls,
    )
    # A checkpoint ID makes this a historical read, NOT ainvoke(checkpoint_id).
    snapshot = await graph.aget_state(saved.config)
    if snapshot.next or snapshot.tasks:
        raise ValueError("The response history has not completed its control boundary")
    return SavedContextWindow(saved.checkpoint["id"], deepcopy(values["input_items"]))


class ResponseStepState(TypedDict, total=False):
    request_id: UUID
    request_snapshot: NativeSnapshot
    input_items: NativeItems
    response_attempt_id: UUID | None
    response_snapshot: NativeSnapshot
    operation_seed: UUID | None
    prepared_tool: object | None
    tool_results: list[FunctionCallOutput]
    next_action: Literal["continue", "deliver_answer"] | None
    completed_steps: int
    model_step_limit: int | None
    tool_call_limit: int
    capacity_limits: ModelCapacityLimits
    input_count: ReceivedInputCount | None
    counted_request_id: UUID | None
    compacted_request_id: UUID | None
    request_admission: Literal["request_model", "compact_window"]
    pause_enabled: bool
    control_action: Literal["pause", "continue"]


@dataclass(frozen=True, slots=True)
class ReceivedModelResponse:
    """The original SDK result paired with the already-admitted outbound attempt."""

    response: Response = field(repr=False)
    attempt_id: UUID


@dataclass(frozen=True, slots=True)
class ResponseStepRuntime:
    """Injected I/O, not persisted State. The tool owner validates its prepared command type.

    compact_window binds run_context_compaction to the same work guard and capacity
    policy. Re-entry must reconcile that boundary before any new external request;
    inactive work can settle its saved C, but cannot send, adopt or return a new window.
    """

    request_model: Callable[[ResponseRequest, UUID], Awaitable[ReceivedModelResponse]]
    prepare_tool: Callable[[ResponseFunctionToolCall, UUID], Awaitable[object]]
    execute_tool: Callable[[object], Awaitable[str]]
    ensure_active: Callable[[], Awaitable[None]]
    account_response: Callable[[ReceivedModelResponse], Awaitable[None]]
    count_input: Callable[[ResponseRequest, UUID], Awaitable[ReceivedInputCount]]
    capacity_limits: ModelCapacityLimits
    compact_window: (
        Callable[[ResponseRequest, ReceivedInputCount, UUID], Awaitable[NativeItems]] | None
    ) = None


@dataclass(frozen=True, slots=True)
class HeldModelResponse:
    """Process-local recovery handoff, never a replacement for a durable checkpoint.

    Only pass this object back to the same Step. Do not serialize it into logs or
    product history. Its operation seed is retained along with the exact native R.
    """

    thread_id: str
    request_id: UUID
    request_snapshot: NativeSnapshot = field(repr=False)
    update: ResponseStepState = field(repr=False)


@dataclass(frozen=True, slots=True)
class HeldInputCount:
    """Intact process-local count bound to the exact original request, not a cache."""

    thread_id: str
    request_id: UUID
    request_snapshot: NativeSnapshot = field(repr=False)
    update: ResponseStepState = field(repr=False)


class InputCountSaveError(RuntimeError):
    def __init__(self, recovery: HeldInputCount) -> None:
        super().__init__("The original input count is held; reconcile before counting again")
        self.recovery = recovery


class ResponseStepSaveError(RuntimeError):
    """No tools started from this R; the caller can retry saving the held original."""

    def __init__(self, recovery: HeldModelResponse) -> None:
        super().__init__(
            "The original model result is held; reconcile its checkpoint before retrying"
        )
        self.recovery = recovery


class ModelStepLimitError(RuntimeError):
    """The last Step is saved, but this invocation may not request another response."""


@dataclass(frozen=True, slots=True)
class ResponseLoopControls:
    """Product-owned pause request and acknowledgement; no model-visible controls."""

    read_pause_requested: Callable[[], Awaitable[bool]]
    mark_paused: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class PausedResponseLoop:
    """A durable native interrupt, not a final answer or a failed execution."""

    interrupt_id: str
    state: ResponseStepState = field(repr=False)


async def run_response_loop(
    checkpointer: BaseCheckpointSaver[str],
    *,
    thread_id: str,
    request: ResponseRequest | None,
    runtime: ResponseStepRuntime,
    max_tool_calls: int,
    max_model_steps: int,
    recovery: HeldModelResponse | HeldInputCount | None = None,
    controls: ResponseLoopControls | None = None,
    resume_interrupt_id: str | None = None,
    save_retry_policy: ResultSaveRetryPolicy | None = None,
) -> ResponseStepState | PausedResponseLoop:
    """Continue complete native Steps to a final answer within a fixed saved limit.

    This does not commit the product Turn or refresh context. Only intact result
    save failures receive bounded local recovery, not arbitrary failed I/O.
    Recover with None and the original limits/bindings. A native pause is a typed
    result, not failure; release it only with the current interrupt ID after the
    product owner authorizes resume. Ordinary recovery cannot grant that authority.
    """
    if type(max_model_steps) is not int or max_model_steps < 1:
        raise ValueError("Configure a positive model Step bound")
    return await _run_response_flow(
        checkpointer,
        thread_id=thread_id,
        request=request,
        runtime=runtime,
        max_tool_calls=max_tool_calls,
        max_model_steps=max_model_steps,
        recovery=recovery,
        controls=controls,
        resume_interrupt_id=resume_interrupt_id,
        save_retry_policy=save_retry_policy or ResultSaveRetryPolicy(),
    )


async def run_response_step(
    checkpointer: BaseCheckpointSaver[str],
    *,
    thread_id: str,
    request: ResponseRequest | None,
    runtime: ResponseStepRuntime,
    max_tool_calls: int,
    recovery: HeldModelResponse | HeldInputCount | None = None,
    save_retry_policy: ResultSaveRetryPolicy | None = None,
) -> ResponseStepState:
    """Start a fresh Step or resume it with None; callers still own single-writer eligibility.

    A Step uses one dedicated thread identity. A completed Step may be read/resumed but
    not restarted with new input. Use run_response_loop for multi-Step execution.
    """
    result = await _run_response_flow(
        checkpointer,
        thread_id=thread_id,
        request=request,
        runtime=runtime,
        max_tool_calls=max_tool_calls,
        max_model_steps=None,
        recovery=recovery,
        save_retry_policy=save_retry_policy or ResultSaveRetryPolicy(),
    )
    if isinstance(result, PausedResponseLoop):
        raise ValueError("Single-Step execution cannot own a pause interrupt")
    return result


async def _run_response_flow(
    checkpointer: BaseCheckpointSaver[str],
    *,
    thread_id: str,
    request: ResponseRequest | None,
    runtime: ResponseStepRuntime,
    max_tool_calls: int,
    max_model_steps: int | None,
    recovery: HeldModelResponse | HeldInputCount | None,
    controls: ResponseLoopControls | None = None,
    resume_interrupt_id: str | None = None,
    save_retry_policy: ResultSaveRetryPolicy,
) -> ResponseStepState | PausedResponseLoop:
    async def run_or_reconcile() -> ResponseStepState | PausedResponseLoop:
        nonlocal request, recovery, resume_interrupt_id
        try:
            return await _run_response_flow_once(
                checkpointer,
                thread_id=thread_id,
                request=request,
                runtime=runtime,
                max_tool_calls=max_tool_calls,
                max_model_steps=max_model_steps,
                recovery=recovery,
                controls=controls,
                resume_interrupt_id=resume_interrupt_id,
            )
        except (ResponseStepSaveError, InputCountSaveError) as error:
            # The request and any prior interrupt have already been consumed.
            # Preserve exact native output/operation identities, never submit input again.
            request = None
            resume_interrupt_id = None
            recovery = error.recovery
            raise

    return await retry_result_save(
        run_or_reconcile,
        errors=(ResponseStepSaveError, InputCountSaveError),
        policy=save_retry_policy,
    )


async def _run_response_flow_once(
    checkpointer: BaseCheckpointSaver[str],
    *,
    thread_id: str,
    request: ResponseRequest | None,
    runtime: ResponseStepRuntime,
    max_tool_calls: int,
    max_model_steps: int | None,
    recovery: HeldModelResponse | HeldInputCount | None,
    controls: ResponseLoopControls | None = None,
    resume_interrupt_id: str | None = None,
) -> ResponseStepState | PausedResponseLoop:
    if not thread_id:
        raise ValueError("A durable Step requires a nonempty thread identity")
    validate_capacity_limits(runtime.capacity_limits)
    if resume_interrupt_id is not None and (
        not resume_interrupt_id or request is not None or recovery is not None or controls is None
    ):
        raise ValueError("Explicit resume requires the original paused loop with no new input")
    if recovery is not None and (recovery.thread_id != thread_id or request is not None):
        raise ValueError("A held response can only resume its original Step with None")
    # The small holder belongs to this invocation, not to the role or the saver.
    # Release only after the next node confirms the preceding sync save, so later
    # capacity/accounting/tool failures are not mistaken for result-save failures.
    held = recovery

    def retain(state: ResponseStepState, update: ResponseStepState) -> None:
        nonlocal held
        held = HeldModelResponse(
            thread_id, state["request_id"], deepcopy(state["request_snapshot"]), deepcopy(update)
        )

    def retain_count(state: ResponseStepState, update: ResponseStepState) -> None:
        nonlocal held
        held = HeldInputCount(
            thread_id, state["request_id"], deepcopy(state["request_snapshot"]), deepcopy(update)
        )

    def release() -> None:
        nonlocal held
        held = None

    graph = _build_response_step(
        checkpointer,
        max_tool_calls=max_tool_calls,
        max_model_steps=max_model_steps,
        retain_response=retain,
        release_response=release,
        retain_count=retain_count,
        release_count=release,
        controls=controls,
    )
    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": (2 * max_tool_calls + 14) * (max_model_steps or 1),
    }
    try:
        saved = await graph.aget_state(config)
    except Exception as error:
        if held is not None:
            raise _result_save_error(held) from error
        raise
    if request is not None and saved.created_at is not None:
        raise ValueError("This Step already exists; resume with None instead of new input")
    if request is None and saved.created_at is None:
        raise ValueError("There is no saved Step to resume")
    # The first durable checkpoint can still hold input in __start__, with no
    # expanded values. Let the native graph restore it; request_model validates
    # those original limits before any outbound request.
    if saved.created_at is not None and not (not saved.values and saved.next == ("__start__",)):
        _require_execution_limits(saved.values, max_tool_calls, max_model_steps)
        if saved.values.get("capacity_limits") != runtime.capacity_limits:
            raise ValueError("Resume with the original capacity limits")
        _require_control_configuration(saved.values, controls)
    if saved.interrupts:
        if controls is None or recovery is not None:
            raise ValueError("A paused loop requires its original control binding")
        # StateSnapshot erases the compiled graph's TypedDict in its public type.
        paused = _paused_result(cast(ResponseStepState, saved.values), saved.interrupts)
        if resume_interrupt_id is None:
            # An ordinary reopen only reconciles the already durable pause. The
            # product owner checks unfinished writer eligibility in mark_paused.
            await controls.mark_paused()
            return paused
        if resume_interrupt_id != paused.interrupt_id:
            raise ValueError("The resume identity does not match the current interrupt")
    elif resume_interrupt_id is not None:
        raise ValueError("There is no current pause interrupt to resume")
    if recovery is not None:
        if (
            saved.values.get("request_id") != recovery.request_id
            or saved.values.get("request_snapshot") != recovery.request_snapshot
        ):
            raise ValueError("The held response does not match the saved request boundary")
        if isinstance(recovery, HeldInputCount):
            if saved.values.get("input_count") is not None:
                if (
                    saved.values.get("input_count") != recovery.update.get("input_count")
                    or saved.values.get("counted_request_id") != recovery.request_id
                ):
                    raise ValueError("The saved request contains a different input count")
                # Native saved/pending results win; do not rewind later work.
                held = None
            else:
                if saved.next != ("count_input",):
                    raise ValueError("The held count does not match the saved request boundary")
                await runtime.ensure_active()
                try:
                    await graph.aupdate_state(
                        config, deepcopy(recovery.update), as_node="count_input"
                    )
                except Exception as error:
                    raise InputCountSaveError(recovery) from error
        elif saved.values.get("response_snapshot"):
            if any(
                saved.values.get(key) != recovery.update[key]
                for key in ("response_snapshot", "response_attempt_id", "operation_seed")
            ):
                raise ValueError("The saved Step contains a different model result")
            # A confirmed R (including native pending writes) wins. In particular,
            # never overwrite later prepared commands, observations or completed items.
            held = None
        else:
            if (
                saved.next != ("request_model",)
                or saved.values.get("tool_results")
                or saved.values.get("prepared_tool") is not None
                or saved.values.get("next_action") is not None
            ):
                raise ValueError("The held response does not match the saved request boundary")
            try:
                await runtime.ensure_active()
            except Exception:
                # Late billing is still real, but an inactive worker cannot adopt the R.
                await runtime.account_response(_received_response(recovery.update))
                raise
            try:
                await graph.aupdate_state(
                    config, deepcopy(recovery.update), as_node="request_model"
                )
            except Exception as error:
                raise ResponseStepSaveError(recovery) from error
    try:
        await runtime.ensure_active()
    except Exception:
        if saved.next == ("compact_window",) and runtime.compact_window is not None:
            # The private compaction graph may already hold paid C, even though the
            # parent still has W. Re-enter its guarded recovery to settle that result.
            count = saved.values.get("input_count")
            if count is not None and saved.values.get("counted_request_id") == saved.values.get(
                "request_id"
            ):
                await runtime.compact_window(
                    ResponseRequest.from_snapshot(saved.values["request_snapshot"]),
                    count,
                    saved.values["request_id"],
                )
        if saved.values.get("response_snapshot"):
            await runtime.account_response(
                ReceivedModelResponse(
                    restore_response(saved.values["response_snapshot"]),
                    saved.values["response_attempt_id"],
                )
            )
        elif isinstance(recovery, HeldModelResponse):
            # The validated handoff may just have been adopted by aupdate_state;
            # `saved` still describes the earlier boundary, not that successful write.
            await runtime.account_response(_received_response(recovery.update))
        raise
    if (
        controls is not None
        and request is None
        and held is None
        and resume_interrupt_id is None
        and saved.values.get("completed_steps", 0) > 0
        and saved.values.get("next_action") in ("continue", "deliver_answer")
        and saved.next in (("prepare_next_request",), ())
        and not any(task.name == "finish_step" for task in saved.tasks)
    ):
        # A saved continue decision is not authority across a recovery boundary.
        # An already-confirmed result handoff does not suppress this control check.
        # Re-enter only its pure control successor at the current checkpoint; no
        # historical checkpoint, Step replay, input rewrite or model/tool effects.
        # get_state can project pending finish_step writes over an older checkpoint;
        # let native recovery consolidate those first, rather than overwriting them.
        await graph.aupdate_state(config, {"control_action": "continue"}, as_node="finish_step")
    initial_state: ResponseStepState | Command[str] | None = None
    if request is not None:
        initial_state = {
            "request_id": uuid4(),
            "request_snapshot": request.create_payload(),
            "completed_steps": 0,
            "model_step_limit": max_model_steps,
            "tool_call_limit": max_tool_calls,
            "capacity_limits": deepcopy(runtime.capacity_limits),
            "pause_enabled": controls is not None,
        }
    elif resume_interrupt_id is not None:
        initial_state = Command(resume={resume_interrupt_id: True})
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
            raise _result_save_error(held) from error
        raise
    if result.interrupts:
        if controls is None:
            raise ValueError("Unexpected pause in an execution without controls")
        paused = _paused_result(result.value, result.interrupts)
        # Only acknowledge the product pause after the saver confirms the native
        # interrupt. A lost acknowledgement is reconciled by the entry path above.
        await controls.mark_paused()
        return paused
    await runtime.ensure_active()
    return result.value


def _build_response_step(
    checkpointer: BaseCheckpointSaver[str],
    *,
    max_tool_calls: int,
    max_model_steps: int | None = None,
    retain_response: Callable[[ResponseStepState, ResponseStepState], None] | None = None,
    release_response: Callable[[], None] | None = None,
    retain_count: Callable[[ResponseStepState, ResponseStepState], None] | None = None,
    release_count: Callable[[], None] | None = None,
    controls: ResponseLoopControls | None = None,
) -> CompiledStateGraph[
    ResponseStepState, ResponseStepRuntime, ResponseStepState, ResponseStepState
]:
    """Shared graph; public entry points enforce thread identity and saved limits."""
    if type(max_tool_calls) is not int or max_tool_calls < 1:
        raise ValueError("Configure a positive per-response tool bound")

    async def count_input(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        _require_execution_limits(state, max_tool_calls, max_model_steps)
        _require_control_configuration(state, controls)
        if state["capacity_limits"] != runtime.context.capacity_limits:
            raise ValueError("Resume with the original capacity limits")
        validate_capacity_limits(state["capacity_limits"])
        await runtime.context.ensure_active()
        require_request_limits(
            ResponseRequest.from_snapshot(state["request_snapshot"]), state["capacity_limits"]
        )
        count = await runtime.context.count_input(
            ResponseRequest.from_snapshot(state["request_snapshot"]),
            uuid5(state["request_id"], "input_tokens"),
        )
        # Save before interpretation/admission. A failed count never becomes a guessed zero.
        update: ResponseStepState = {
            "input_count": count,
            "counted_request_id": state["request_id"],
        }
        if retain_count is not None:
            retain_count(state, update)
        return update

    async def request_model(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        _require_execution_limits(state, max_tool_calls, max_model_steps)
        await runtime.context.ensure_active()
        count = state.get("input_count")
        if count is None or state.get("counted_request_id") != state["request_id"]:
            raise ValueError("The exact request needs a saved input count before generation")
        require_request_capacity(
            ResponseRequest.from_snapshot(state["request_snapshot"]),
            count,
            state["capacity_limits"],
            completed_steps=0,  # The post-count route enforces the middle-Step policy.
        )
        received = await runtime.context.request_model(
            ResponseRequest.from_snapshot(state["request_snapshot"]), state["request_id"]
        )
        update: ResponseStepState = {
            "response_snapshot": snapshot_response(received.response),
            "response_attempt_id": received.attempt_id,
            "operation_seed": uuid4(),
            "prepared_tool": None,
            "tool_results": [],
            "next_action": None,
        }
        if retain_response is not None:
            retain_response(state, update)
        return update

    async def check_capacity(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        if release_count is not None:
            release_count()
        await runtime.context.ensure_active()
        count = state.get("input_count")
        if count is None or state.get("counted_request_id") != state["request_id"]:
            raise ValueError("The exact request needs a saved input count before admission")
        try:
            require_request_capacity(
                ResponseRequest.from_snapshot(state["request_snapshot"]),
                count,
                state["capacity_limits"],
                completed_steps=state.get("completed_steps", 0),
            )
        except CompactionRequiredError as error:
            if state.get("compacted_request_id") == state["request_id"]:
                raise RequestCapacityError(
                    "The compacted window still exceeds the boundary threshold"
                ) from error
            return {"request_admission": "compact_window"}
        return {"request_admission": "request_model"}

    def route_counted(state: ResponseStepState) -> Literal["request_model", "compact_window"]:
        return state["request_admission"]

    async def compact_window(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        await runtime.context.ensure_active()
        compact = runtime.context.compact_window
        if compact is None:
            raise CompactionRequiredError("The next request requires explicit boundary compaction")
        count = state.get("input_count")
        if count is None or state.get("counted_request_id") != state["request_id"]:
            raise ValueError("Compaction requires the saved count for this exact window")
        items = await compact(
            ResponseRequest.from_snapshot(state["request_snapshot"]), count, state["request_id"]
        )
        await runtime.context.ensure_active()
        next_id = uuid5(state["request_id"], "compacted")
        return {
            "request_id": next_id,
            "request_snapshot": {**deepcopy(state["request_snapshot"]), "input": deepcopy(items)},
            "input_items": deepcopy(items),
            "compacted_request_id": next_id,
            "input_count": None,
            "counted_request_id": None,
        }

    async def account_response(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        if release_response is not None:
            release_response()
        # R is durable before usage parsing / SQL. Accounting is idempotent and must
        # remain possible after cancellation; only subsequent adoption needs a guard.
        await runtime.context.account_response(_received_response(state))
        return {}

    async def prepare_tool(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        await runtime.context.ensure_active()
        # Inspection is after R's node boundary so unsupported output is still recoverable.
        calls = inspect_response_step(restore_response(state["response_snapshot"])).calls
        if len(calls) > max_tool_calls:
            raise ValueError("The response exceeds this execution's configured tool bound")
        require_result_order(calls, state["tool_results"])
        if len(state["tool_results"]) == len(calls):
            return {"prepared_tool": None}
        call = calls[len(state["tool_results"])]
        operation_seed = state["operation_seed"]
        if operation_seed is None:
            raise ValueError("The model response has no saved operation identity")
        operation_id = uuid5(operation_seed, call.call_id)
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
            "completed_steps": state.get("completed_steps", 0) + 1,
            "input_items": [
                *state["request_snapshot"]["input"],
                *response_input_items(response),
                *(dict(item) for item in state["tool_results"]),
            ],
            "next_action": "deliver_answer"
            if step.action == ResponseAction.DELIVER_ANSWER
            else "continue",
        }

    async def prepare_next_request(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        await runtime.context.ensure_active()
        limit = state["model_step_limit"]
        if limit is None or state["completed_steps"] >= limit:
            raise ModelStepLimitError("The saved model Step limit has been reached")
        # Change only input. Instructions, tools, model, reasoning and the existing
        # maps remain those of the original execution, not today's configuration.
        next_request = {**deepcopy(state["request_snapshot"]), "input": state["input_items"]}
        next_id = uuid4()
        unchanged_compaction = (
            state.get("compacted_request_id") == state["request_id"]
            and state["input_items"] == state["request_snapshot"]["input"]
        )
        return {
            "request_id": next_id,
            "compacted_request_id": next_id if unchanged_compaction else None,
            "request_snapshot": next_request,
            "response_snapshot": {},
            "response_attempt_id": None,
            "operation_seed": None,
            "prepared_tool": None,
            "tool_results": [],
            "next_action": None,
            "input_count": None,
            "counted_request_id": None,
        }

    def route_finished(state: ResponseStepState) -> Literal["prepare_next_request", "__end__"]:
        return "__end__" if state["next_action"] == "deliver_answer" else "prepare_next_request"

    async def check_control(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        await runtime.context.ensure_active()
        if controls is None:
            raise ValueError("Control handling requires the original product binding")
        requested = await controls.read_pause_requested()
        if type(requested) is not bool:
            raise ValueError("The product pause request must have a definite boolean value")
        return {"control_action": "pause" if requested else "continue"}

    def route_control(
        state: ResponseStepState,
    ) -> Literal["pause_at_boundary", "prepare_next_request", "__end__"]:
        return "pause_at_boundary" if state["control_action"] == "pause" else route_finished(state)

    async def pause_at_boundary(
        state: ResponseStepState, runtime: Runtime[ResponseStepRuntime]
    ) -> ResponseStepState:
        await runtime.context.ensure_active()
        # Always reach this same interrupt on re-entry. No model/tool effects in
        # this node: native resume restarts the node, not its Python instruction.
        resumed = interrupt({"kind": "step_pause", "completed_steps": state["completed_steps"]})
        if resumed is not True:
            raise ValueError("Only an explicit original-loop resume may release this pause")
        await runtime.context.ensure_active()
        return {}

    graph = StateGraph(ResponseStepState, context_schema=ResponseStepRuntime)
    graph.add_node("count_input", count_input)
    graph.add_node("check_capacity", check_capacity)
    graph.add_node("compact_window", compact_window)
    graph.add_node("request_model", request_model)
    graph.add_node("account_response", account_response)
    graph.add_node("prepare_tool", prepare_tool)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("finish_step", finish_step)
    graph.add_edge(START, "count_input")
    graph.add_edge("count_input", "check_capacity")
    graph.add_conditional_edges("check_capacity", route_counted)
    graph.add_edge("compact_window", "count_input")
    graph.add_edge("request_model", "account_response")
    graph.add_edge("account_response", "prepare_tool")
    graph.add_conditional_edges("prepare_tool", route_prepared)
    graph.add_edge("execute_tool", "prepare_tool")
    if max_model_steps is None:
        graph.add_edge("finish_step", END)
    else:
        graph.add_node("prepare_next_request", prepare_next_request)
        if controls is None:
            graph.add_conditional_edges("finish_step", route_finished)
        else:
            graph.add_node("check_control", check_control)
            graph.add_node("pause_at_boundary", pause_at_boundary)
            graph.add_edge("finish_step", "check_control")
            graph.add_conditional_edges("check_control", route_control)
            graph.add_edge("pause_at_boundary", "check_control")
        graph.add_edge("prepare_next_request", "count_input")
    return graph.compile(checkpointer=checkpointer)


def _received_response(state: ResponseStepState) -> ReceivedModelResponse:
    attempt_id = state["response_attempt_id"]
    if attempt_id is None:
        raise ValueError("There is no model response to account for")
    return ReceivedModelResponse(restore_response(state["response_snapshot"]), attempt_id)


def _result_save_error(
    held: HeldModelResponse | HeldInputCount,
) -> ResponseStepSaveError | InputCountSaveError:
    return (
        InputCountSaveError(held)
        if isinstance(held, HeldInputCount)
        else ResponseStepSaveError(held)
    )


def _require_execution_limits(
    state: Mapping[str, object],
    max_tool_calls: int,
    max_model_steps: int | None,
) -> None:
    if (
        state.get("model_step_limit") != max_model_steps
        or state.get("tool_call_limit") != max_tool_calls
    ):
        raise ValueError("Resume with the original execution mode and limits")


def _require_control_configuration(
    state: Mapping[str, object], controls: ResponseLoopControls | None
) -> None:
    if state.get("pause_enabled", False) != (controls is not None):
        raise ValueError("Resume with the original pause-control configuration")


def _paused_result(
    state: ResponseStepState, interrupts: tuple[Interrupt, ...]
) -> PausedResponseLoop:
    if (
        len(interrupts) != 1
        or not isinstance(interrupts[0].value, dict)
        or interrupts[0].value.get("kind") != "step_pause"
        or state.get("control_action") != "pause"
        or state.get("completed_steps", 0) < 1
    ):
        raise ValueError("The saved interrupt is not a complete Step pause")
    return PausedResponseLoop(interrupts[0].id, deepcopy(state))
