"""Durably adopt one complete native compacted window using the existing saver.

The caller chooses an eligible boundary and owns its cancellation/rollback scope.
This flow does not add new input, change maps, count the new window or publish a Turn.
"""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Literal, TypedDict
from uuid import UUID, uuid4, uuid5

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from openai.types.responses.compacted_response import CompactedResponse

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import (
    NativeItems,
    NativeSnapshot,
    compaction_input_items,
    snapshot_compaction,
)
from caliburn.agent_execution.request_capacity import (
    ModelCapacityLimits,
    ReceivedInputCount,
    require_request_capacity,
    require_request_limits,
)


@dataclass(frozen=True, slots=True)
class ReceivedCompaction:
    response: CompactedResponse = field(repr=False)
    attempt_id: UUID


@dataclass(frozen=True, slots=True)
class CompactionRuntime:
    request_compaction: Callable[[ResponseRequest, UUID], Awaitable[ReceivedCompaction]]
    account_compaction: Callable[[ReceivedCompaction], Awaitable[None]]
    ensure_active: Callable[[], Awaitable[None]]
    capacity_limits: ModelCapacityLimits


class HistoryPreparationPolicy(TypedDict):
    threshold_tokens: int
    compact_requested: bool


class CompactionState(TypedDict, total=False):
    request_id: UUID
    request_snapshot: NativeSnapshot
    input_count: ReceivedInputCount
    capacity_limits: ModelCapacityLimits
    compaction_snapshot: NativeSnapshot
    compaction_attempt_id: UUID
    adopted: bool
    preparation_policy: HistoryPreparationPolicy | None
    needs_compaction: bool


@dataclass(frozen=True, slots=True)
class HeldCompaction:
    """Only an intact process-local result, never a remote backup or another store."""

    thread_id: str
    request_id: UUID
    request_snapshot: NativeSnapshot = field(repr=False)
    update: CompactionState = field(repr=False)


class CompactionSaveError(RuntimeError):
    def __init__(self, recovery: HeldCompaction) -> None:
        super().__init__("The original compaction is held; reconcile its saved boundary")
        self.recovery = recovery


@dataclass(frozen=True, slots=True)
class HeldPreparationCount:
    """An intact history count that has not yet crossed its reliable save boundary."""

    thread_id: str
    request_id: UUID
    request_snapshot: NativeSnapshot = field(repr=False)
    update: CompactionState = field(repr=False)


class PreparationCountSaveError(RuntimeError):
    def __init__(self, recovery: HeldPreparationCount) -> None:
        super().__init__("The original history count is held; reconcile before counting again")
        self.recovery = recovery


async def prepare_context_history(
    checkpointer: BaseCheckpointSaver[str],
    *,
    thread_id: str,
    history_request: ResponseRequest,
    threshold_tokens: int,
    compact_requested: bool,
    count_input: Callable[[ResponseRequest, UUID], Awaitable[ReceivedInputCount]],
    runtime: CompactionRuntime,
    recovery: HeldCompaction | HeldPreparationCount | None = None,
) -> NativeItems:
    """Prepare valid history once, before adding new-work maps or employee input.

    Use one boundary identity for this role's preparation. Same-batch re-entry must
    use its original request and policy, including when no compaction was needed.
    A's role supplies 128_000; Memory supplies its explicitly chosen threshold.
    The caller owns history eligibility, single-writer fencing and cross-Turn use.
    """
    if type(threshold_tokens) is not int or threshold_tokens < 1:
        raise ValueError("Configure a positive history compaction threshold")
    if type(compact_requested) is not bool:
        raise ValueError("The saved compaction request must be a boolean")
    return await _run_context_boundary(
        checkpointer,
        thread_id=thread_id,
        request=history_request,
        input_count=None,
        runtime=runtime,
        preparation_policy={
            "threshold_tokens": threshold_tokens,
            "compact_requested": compact_requested,
        },
        count_input=count_input,
        recovery=recovery,
    )


async def run_context_compaction(
    checkpointer: BaseCheckpointSaver[str],
    *,
    thread_id: str,
    request: ResponseRequest,
    input_count: ReceivedInputCount,
    runtime: CompactionRuntime,
    recovery: HeldCompaction | None = None,
) -> NativeItems:
    """Compact once at a caller-selected boundary; repeat the same arguments to resume.

    This private graph thread is scoped to one compaction, not an Agent conversation.
    A different request, count or capacity policy cannot replace its saved inputs.
    """
    return await _run_context_boundary(
        checkpointer,
        thread_id=thread_id,
        request=request,
        input_count=input_count,
        runtime=runtime,
        preparation_policy=None,
        count_input=None,
        recovery=recovery,
    )


async def _run_context_boundary(
    checkpointer: BaseCheckpointSaver[str],
    *,
    thread_id: str,
    request: ResponseRequest,
    input_count: ReceivedInputCount | None,
    runtime: CompactionRuntime,
    preparation_policy: HistoryPreparationPolicy | None,
    count_input: Callable[[ResponseRequest, UUID], Awaitable[ReceivedInputCount]] | None,
    recovery: HeldCompaction | HeldPreparationCount | None,
) -> NativeItems:
    if not thread_id:
        raise ValueError("Compaction needs a nonempty durable boundary identity")
    held = recovery

    async def count_history(
        state: CompactionState, runtime: Runtime[CompactionRuntime]
    ) -> CompactionState:
        nonlocal held
        await runtime.context.ensure_active()
        original = ResponseRequest.from_snapshot(state["request_snapshot"])
        require_request_limits(original, state["capacity_limits"])
        if count_input is None:
            raise ValueError("History preparation needs an explicit token counter")
        count = await count_input(original, uuid5(state["request_id"], "input_tokens"))
        update: CompactionState = {"input_count": deepcopy(count)}
        held = HeldPreparationCount(
            thread_id, state["request_id"], deepcopy(state["request_snapshot"]), deepcopy(update)
        )
        return update

    async def assess_history(
        state: CompactionState, runtime: Runtime[CompactionRuntime]
    ) -> CompactionState:
        nonlocal held
        held = None  # The count now exists in the preceding sync checkpoint.
        await runtime.context.ensure_active()
        original = ResponseRequest.from_snapshot(state["request_snapshot"])
        require_request_capacity(
            original, state["input_count"], state["capacity_limits"], completed_steps=0
        )
        policy = state["preparation_policy"]
        if policy is None:
            raise ValueError("History assessment needs its saved preparation policy")
        return {
            "needs_compaction": policy["compact_requested"]
            or state["input_count"]["input_tokens"] >= policy["threshold_tokens"]
        }

    async def retain_history(
        state: CompactionState, runtime: Runtime[CompactionRuntime]
    ) -> CompactionState:
        await runtime.context.ensure_active()
        return {"adopted": True}

    async def request_compaction(
        state: CompactionState, runtime: Runtime[CompactionRuntime]
    ) -> CompactionState:
        nonlocal held
        await runtime.context.ensure_active()
        original = ResponseRequest.from_snapshot(state["request_snapshot"])
        # Conservative admission: this slice only compacts requests that still fit.
        # The count includes instructions/tools, not just the items sent to compact.
        require_request_capacity(
            original, state["input_count"], state["capacity_limits"], completed_steps=0
        )
        received = await runtime.context.request_compaction(original, state["request_id"])
        update: CompactionState = {
            "compaction_snapshot": snapshot_compaction(received.response),
            "compaction_attempt_id": received.attempt_id,
        }
        held = HeldCompaction(
            thread_id, state["request_id"], deepcopy(state["request_snapshot"]), deepcopy(update)
        )
        return update

    async def account_compaction(
        state: CompactionState, runtime: Runtime[CompactionRuntime]
    ) -> CompactionState:
        nonlocal held
        held = None  # The preceding sync checkpoint now holds the whole C.
        await runtime.context.account_compaction(_received_compaction(state))
        return {}

    async def adopt_compaction(
        state: CompactionState, runtime: Runtime[CompactionRuntime]
    ) -> CompactionState:
        await runtime.context.ensure_active()
        items = compaction_input_items(state["compaction_snapshot"])
        if not items and state["request_snapshot"]["input"]:
            raise ValueError("An empty compacted window cannot replace nonempty history")
        return {"adopted": True}

    builder = StateGraph(CompactionState, context_schema=CompactionRuntime)
    builder.add_node("count_history", count_history)
    builder.add_node("assess_history", assess_history)
    builder.add_node("retain_history", retain_history)
    builder.add_node("request_compaction", request_compaction)
    builder.add_node("account_compaction", account_compaction)
    builder.add_node("adopt_compaction", adopt_compaction)

    def start_boundary(
        state: CompactionState,
    ) -> Literal["count_history", "request_compaction", "retain_history"]:
        if state.get("preparation_policy") is None:
            return "request_compaction"
        return "count_history" if state["request_snapshot"]["input"] else "retain_history"

    def route_history(
        state: CompactionState,
    ) -> Literal["request_compaction", "retain_history"]:
        return "request_compaction" if state["needs_compaction"] else "retain_history"

    builder.add_conditional_edges(START, start_boundary)
    builder.add_edge("count_history", "assess_history")
    builder.add_conditional_edges("assess_history", route_history)
    builder.add_edge("retain_history", END)
    builder.add_edge("request_compaction", "account_compaction")
    builder.add_edge("account_compaction", "adopt_compaction")
    builder.add_edge("adopt_compaction", END)
    graph = builder.compile(checkpointer=checkpointer)
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    payload = request.create_payload()
    try:
        saved = await graph.aget_state(config)
    except Exception as error:
        if held is not None:
            raise _result_save_error(held) from error
        raise
    if saved.created_at is not None:
        # __start__ can hold input before the first expanded checkpoint. It is never
        # overwritten: the node will restore those same saved arguments below.
        original_values = saved.values
        if not original_values and saved.next == ("__start__",):
            checkpoint = await checkpointer.aget_tuple(config)
            if checkpoint is None:
                raise ValueError("The original compaction boundary is unavailable")
            original_values = checkpoint.checkpoint["channel_values"]["__start__"]
        if (
            original_values.get("request_snapshot") != payload
            or (input_count is not None and original_values.get("input_count") != input_count)
            or original_values.get("capacity_limits") != runtime.capacity_limits
            or original_values.get("preparation_policy") != preparation_policy
        ):
            raise ValueError(
                "Resume with the original request, count, limits and preparation policy"
            )
    if recovery is not None:
        if (
            recovery.thread_id != thread_id
            or saved.values.get("request_id") != recovery.request_id
            or recovery.request_snapshot != payload
        ):
            raise ValueError("The held compaction belongs to a different saved boundary")
        if isinstance(recovery, HeldPreparationCount):
            if saved.values.get("input_count") is not None:
                if saved.values["input_count"] != recovery.update["input_count"]:
                    raise ValueError("The saved boundary has a different history count")
                held = None
            else:
                if saved.next != ("count_history",):
                    raise ValueError("The held count does not match the saved history boundary")
                await runtime.ensure_active()
                try:
                    await graph.aupdate_state(
                        config, deepcopy(recovery.update), as_node="count_history"
                    )
                except Exception as error:
                    raise PreparationCountSaveError(recovery) from error
        elif saved.values.get("compaction_snapshot"):
            if any(saved.values.get(key) != value for key, value in recovery.update.items()):
                raise ValueError("The saved boundary has a different compaction result")
            held = None
        else:
            if saved.next != ("request_compaction",):
                raise ValueError("The saved boundary cannot adopt this held compaction")
            try:
                await runtime.ensure_active()
            except Exception:
                await runtime.account_compaction(_received_compaction(recovery.update))
                raise
            try:
                await graph.aupdate_state(
                    config, deepcopy(recovery.update), as_node="request_compaction"
                )
            except Exception as error:
                raise CompactionSaveError(recovery) from error
    try:
        await runtime.ensure_active()
    except Exception:
        if saved.values.get("compaction_snapshot"):
            await runtime.account_compaction(
                _received_compaction(
                    {
                        "compaction_snapshot": saved.values["compaction_snapshot"],
                        "compaction_attempt_id": saved.values["compaction_attempt_id"],
                    }
                )
            )
        elif isinstance(recovery, HeldCompaction):
            await runtime.account_compaction(_received_compaction(recovery.update))
        raise
    initial: CompactionState | None = None
    if saved.created_at is None:
        require_request_limits(request, runtime.capacity_limits)
        initial = {
            "request_id": uuid4(),
            "request_snapshot": payload,
            "capacity_limits": deepcopy(runtime.capacity_limits),
            "preparation_policy": deepcopy(preparation_policy),
            "adopted": False,
        }
        if input_count is not None:
            initial["input_count"] = deepcopy(input_count)
    try:
        result = await graph.ainvoke(
            initial, config, context=runtime, durability="sync", version="v2"
        )
    except Exception as error:
        if held is not None:
            raise _result_save_error(held) from error
        raise
    await runtime.ensure_active()
    if not result.value.get("adopted"):
        raise ValueError("The compacted window has not been adopted")
    if result.value.get("compaction_snapshot") is not None:
        return compaction_input_items(result.value["compaction_snapshot"])
    if preparation_policy is None:
        raise ValueError("The compaction boundary has no saved result")
    return deepcopy(result.value["request_snapshot"]["input"])


def _result_save_error(
    held: HeldCompaction | HeldPreparationCount,
) -> CompactionSaveError | PreparationCountSaveError:
    if isinstance(held, HeldPreparationCount):
        return PreparationCountSaveError(held)
    return CompactionSaveError(held)


def _received_compaction(state: CompactionState) -> ReceivedCompaction:
    # Native SDK recursively reconstructs the same received fields without forcing
    # its narrower output union onto retained user/input_text items (SDK 3.20.0).
    response = CompactedResponse.construct(**deepcopy(state["compaction_snapshot"]))
    return ReceivedCompaction(response, state["compaction_attempt_id"])
