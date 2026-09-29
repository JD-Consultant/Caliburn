"""Durably adopt one complete native compacted window using the existing saver.

The caller chooses an eligible boundary and owns its cancellation/rollback scope.
This flow does not add new input, change maps, count the new window or publish a Turn.
"""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TypedDict
from uuid import UUID, uuid4

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


class CompactionState(TypedDict, total=False):
    request_id: UUID
    request_snapshot: NativeSnapshot
    input_count: ReceivedInputCount
    capacity_limits: ModelCapacityLimits
    compaction_snapshot: NativeSnapshot
    compaction_attempt_id: UUID
    adopted: bool


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
    if not thread_id:
        raise ValueError("Compaction needs a nonempty durable boundary identity")
    held = recovery

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
    builder.add_node("request_compaction", request_compaction)
    builder.add_node("account_compaction", account_compaction)
    builder.add_node("adopt_compaction", adopt_compaction)
    builder.add_edge(START, "request_compaction")
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
            raise CompactionSaveError(held) from error
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
            or original_values.get("input_count") != input_count
            or original_values.get("capacity_limits") != runtime.capacity_limits
        ):
            raise ValueError("Resume compaction with its original request, count and limits")
    if recovery is not None:
        if (
            recovery.thread_id != thread_id
            or saved.values.get("request_id") != recovery.request_id
            or recovery.request_snapshot != payload
        ):
            raise ValueError("The held compaction belongs to a different saved boundary")
        if saved.values.get("compaction_snapshot"):
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
        elif recovery is not None:
            await runtime.account_compaction(_received_compaction(recovery.update))
        raise
    initial: CompactionState | None = None
    if saved.created_at is None:
        initial = {
            "request_id": uuid4(),
            "request_snapshot": payload,
            "input_count": deepcopy(input_count),
            "capacity_limits": deepcopy(runtime.capacity_limits),
            "adopted": False,
        }
    try:
        result = await graph.ainvoke(
            initial, config, context=runtime, durability="sync", version="v2"
        )
    except Exception as error:
        if held is not None:
            raise CompactionSaveError(held) from error
        raise
    await runtime.ensure_active()
    if not result.value.get("adopted"):
        raise ValueError("The compacted window has not been adopted")
    return compaction_input_items(result.value["compaction_snapshot"])


def _received_compaction(state: CompactionState) -> ReceivedCompaction:
    # Native SDK recursively reconstructs the same received fields without forcing
    # its narrower output union onto retained user/input_text items (SDK 3.20.0).
    response = CompactedResponse.construct(**deepcopy(state["compaction_snapshot"]))
    return ReceivedCompaction(response, state["compaction_attempt_id"])
