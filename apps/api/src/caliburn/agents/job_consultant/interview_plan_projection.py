"""Reintroduce A's saved plan after native C, pinning both before parent continuation."""

import json
from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Literal, TypedDict
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import ConfigDict, TypeAdapter, with_config

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import NativeItems
from caliburn.agent_execution.context_compaction import read_compacted_window
from caliburn.agent_execution.request_capacity import ReceivedInputCount
from caliburn.agents.job_consultant.interview_plan_context import (
    PLAN_DATA_KIND,
    interview_plan_item,
)
from caliburn.features.executions.models import ExecutionScope
from caliburn.features.interview_plans.models import PlanSnapshot, PlanStateError
from caliburn.workflows.context_history import RoleContextHistory

type CompactWindow = Callable[[ResponseRequest, ReceivedInputCount, UUID], Awaitable[NativeItems]]
type ReadPlan = Callable[[ExecutionScope], Awaitable[PlanSnapshot | None]]


@with_config(ConfigDict(strict=True, extra="forbid"))
class _CompactPosition(TypedDict):
    thread_id: str
    checkpoint_id: str


@with_config(ConfigDict(strict=True, extra="forbid"))
class _ProjectionBinding(TypedDict):
    version: Literal[1]
    job_file_id: str
    execution_id: str
    source_request_id: str
    compact_position: _CompactPosition


@with_config(ConfigDict(strict=True, extra="forbid"))
class _PlanItem(TypedDict):
    role: Literal["user"]
    content: str


@with_config(ConfigDict(strict=True, extra="forbid"))
class _Projection(TypedDict):
    plan_revision_id: str
    plan_item: _PlanItem


@with_config(ConfigDict(strict=True, extra="forbid"))
class _PlanContent(TypedDict):
    data_kind: Literal["consultant_interview_plan"]
    plan: str | None


class _ProjectionState(TypedDict, total=False):
    input_binding: _ProjectionBinding
    projection: _Projection


_BINDING = TypeAdapter(_ProjectionBinding)
_PROJECTION = TypeAdapter(_Projection)
_ITEM = TypeAdapter(_PlanItem)
_CONTENT = TypeAdapter(_PlanContent)


def bind_interview_plan_compaction(
    work: RoleContextHistory,
    original: CompactWindow,
    *,
    read_plan: ReadPlan,
) -> CompactWindow:
    """Delegate native recovery/accounting first, including inactive paid-C recovery."""

    async def compact(
        request: ResponseRequest, count: ReceivedInputCount, parent_id: UUID
    ) -> NativeItems:
        full_c = await original(request, count, parent_id)
        await work.ensure_active()
        scope = work.writer.scope
        c_thread = f"{work.response_thread_id}:compact:{parent_id}"
        config: RunnableConfig = {
            "configurable": {
                "thread_id": f"{work.response_thread_id}:plan_projection:{parent_id}",
                "checkpoint_ns": "",
            }
        }

        async def capture_projection(state: _ProjectionState) -> _ProjectionState:
            _restore_binding(state.get("input_binding"), scope, parent_id, c_thread)
            await work.ensure_active()
            plan = await read_plan(scope)
            if plan is None:
                raise PlanStateError("The captured plan capability has no retained candidate")
            if (plan.position.job_file_id, plan.position.execution_id) != (
                scope.job_file_id,
                scope.execution_id,
            ):
                raise PlanStateError("The plan projection belongs to another Turn")
            return {
                "projection": {
                    "plan_revision_id": str(plan.position.revision_id),
                    "plan_item": _ITEM.validate_python(interview_plan_item(plan.body)),
                }
            }

        builder = StateGraph(_ProjectionState)
        builder.add_node("capture_projection", capture_projection)
        builder.add_edge(START, "capture_projection")
        builder.add_edge("capture_projection", END)
        graph = builder.compile(checkpointer=work.checkpointer)
        # Raw __start__ is already a saved input binding. Never replace it with latest C.
        raw = await work.checkpointer.aget_tuple(config)
        initial: _ProjectionState | None = None
        if raw is None:
            canonical = await read_compacted_window(
                work.checkpointer, thread_id=c_thread, request=request, input_count=count
            )
            if canonical.items != full_c:
                raise ValueError("The callback did not return the complete original C")
            binding: _ProjectionBinding = {
                "version": 1,
                "job_file_id": str(scope.job_file_id),
                "execution_id": str(scope.execution_id),
                "source_request_id": str(parent_id),
                "compact_position": {
                    "thread_id": c_thread,
                    "checkpoint_id": canonical.checkpoint_id,
                },
            }
            initial = {"input_binding": binding}
        else:
            values = raw.checkpoint["channel_values"]
            binding = _restore_binding(_saved_binding(values), scope, parent_id, c_thread)
        if initial is not None:
            await graph.ainvoke(initial, config, durability="sync")
        elif raw is not None:
            saved = await graph.aget_state(raw.config)
            if saved.next or saved.tasks:
                await graph.ainvoke(None, config, durability="sync")
        raw = await work.checkpointer.aget_tuple(config)
        if raw is None:
            raise ValueError("The plan projection checkpoint is unavailable")
        saved = await graph.aget_state(raw.config)
        if saved.next or saved.tasks:
            raise ValueError("The plan projection checkpoint has unfinished work")
        values = raw.checkpoint["channel_values"]
        binding = _restore_binding(values.get("input_binding"), scope, parent_id, c_thread)
        projection = _PROJECTION.validate_python(values.get("projection"))
        UUID(projection["plan_revision_id"])
        content = _CONTENT.validate_json(projection["plan_item"]["content"])
        if content["data_kind"] != PLAN_DATA_KIND:
            raise ValueError("The projection has another data kind")
        canonical = await read_compacted_window(
            work.checkpointer,
            thread_id=binding["compact_position"]["thread_id"],
            checkpoint_id=binding["compact_position"]["checkpoint_id"],
            request=request,
            input_count=count,
        )
        await work.ensure_active()
        return [*canonical.items, deepcopy(dict(projection["plan_item"]))]

    return compact


def _saved_binding(values: dict[str, object]) -> object:
    binding = values.get("input_binding")
    if binding is not None:
        return binding
    started = values.get("__start__")
    return started.get("input_binding") if isinstance(started, dict) else None


def _restore_binding(
    value: object, scope: ExecutionScope, parent_id: UUID, c_thread: str
) -> _ProjectionBinding:
    binding = _BINDING.validate_python(value)
    if json.dumps(binding, sort_keys=True) != json.dumps(value, sort_keys=True):
        raise ValueError("The saved plan projection binding must preserve its original JSON types")
    position = binding["compact_position"]
    if (
        UUID(binding["job_file_id"]) != scope.job_file_id
        or UUID(binding["execution_id"]) != scope.execution_id
        or UUID(binding["source_request_id"]) != parent_id
        or position["thread_id"] != c_thread
        or not position["checkpoint_id"].strip()
    ):
        raise ValueError("The saved plan projection belongs to another original boundary")
    return binding
