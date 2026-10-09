"""Capture A's initial request once; the response loop owns every later continuation.

Call before starting the response loop, with one live invocation per execution (the
supervisor must quiesce a replaced writer). Preparation is adopted before new data is
read. Only a durably captured request may reach the model; no business table copies it.
This module neither resumes the response loop nor declares a Turn complete.
"""

import json
from dataclasses import dataclass, field
from typing import Literal, TypedDict
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from pydantic import ConfigDict, JsonValue, TypeAdapter, with_config

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import NativeItems, NativeSnapshot
from caliburn.agent_execution.context_windows import read_context_checkpoint
from caliburn.agents.job_consultant.interview_plan_context import (
    has_interview_plan_tools,
    interview_plan_item,
)
from caliburn.contracts.generated.tools.historical_interview import (
    HistoricalInterview,
    HistoricalInterviewMessage,
    Speaker,
)
from caliburn.contracts.generated.tools.memory_map import MemoryMap, MemoryMapItem
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStateError
from caliburn.features.interview_plans.models import PlanPosition
from caliburn.features.job_description.candidates import JdCandidatePosition, JdCandidateScope
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.model_tools.jd_reads import DEFAULT_JD_READ_MAX_RESULT_CHARACTERS
from caliburn.workflows.consultant_context import ConsultantContextData, ConsultantContextWorkflow
from caliburn.workflows.context_history import RoleContextHistory
from caliburn.workflows.memory_reads import PublishedMemoryRead

REFERENCE_DATA_KIND = "consultant_turn_reference"


@dataclass(frozen=True, slots=True)
class TurnContext:
    request: ResponseRequest = field(repr=False)
    memory_binding: PublishedMemoryRead
    candidate_position: JdCandidatePosition
    current_input_source_id: UUID
    plan_position: PlanPosition | None = None
    jd_read_max_result_characters: int = DEFAULT_JD_READ_MAX_RESULT_CHARACTERS

    @property
    def manual_jd_start_revision_id(self) -> UUID:
        return self.candidate_position.base_revision_id


@with_config(ConfigDict(strict=True, extra="forbid"))
class _BindingV1(TypedDict):
    version: Literal[1]
    job_file_id: str
    execution_id: str
    snapshot_id: str | None
    interview_through_sequence: int
    current_input_source_id: str
    candidate_generation_id: str
    candidate_base_revision_id: str
    candidate_revision_id: str


@with_config(ConfigDict(strict=True, extra="forbid"))
class _BindingV2(TypedDict):
    version: Literal[2]
    job_file_id: str
    execution_id: str
    snapshot_id: str | None
    interview_through_sequence: int
    current_input_source_id: str
    candidate_generation_id: str
    candidate_base_revision_id: str
    candidate_revision_id: str
    plan_base_revision_id: str


type _BindingSnapshot = _BindingV1 | _BindingV2


class _CaptureState(TypedDict, total=False):
    request_snapshot: NativeSnapshot
    binding: _BindingSnapshot
    jd_read_max_result_characters: int


_BINDING: TypeAdapter[_BindingSnapshot] = TypeAdapter(_BindingSnapshot)
_REQUEST = TypeAdapter(dict[str, JsonValue])


async def read_captured_turn_template(
    checkpointer: BaseCheckpointSaver[str], scope: ExecutionScope
) -> ResponseRequest | None:
    """只取既存 capture 的原模板，不執行節點、不授權恢復或採用業務狀態。

    取消後可沿用前回合的 prepared base，因此本回合未必有 preparation checkpoint。
    initial capture（含尚未完成的原生 input）仍固定本回合自己的提示與工具。
    """
    config: RunnableConfig = {
        "configurable": {
            "thread_id": f"{scope.job_file_id}:{scope.execution_id}:job_consultant:initial_context",
            "checkpoint_ns": "",
        }
    }
    saved = await checkpointer.aget_tuple(config)
    if saved is None:
        return None
    values = saved.checkpoint["channel_values"]
    if "request_snapshot" not in values:
        values = values.get("__start__", {})
    if not isinstance(values, dict):
        raise ExecutionStateError("The saved capture has no original request template")
    request = _restore_request(values.get("request_snapshot"))
    if "binding" in values:
        _restore_context(
            values["binding"], request.create_payload(), scope, read_limit=_read_limit(values)
        )
    return ResponseRequest.from_snapshot({**request.create_payload(), "input": []})


async def read_saved_turn_context(
    checkpointer: BaseCheckpointSaver[str], scope: ExecutionScope
) -> TurnContext:
    """Restore a complete original capture without active admission or executing a node."""
    saved = await read_context_checkpoint(
        checkpointer,
        thread_id=f"{scope.job_file_id}:{scope.execution_id}:job_consultant:initial_context",
        checkpoint_id=None,
    )

    async def read_only_capture(state: _CaptureState) -> _CaptureState:
        raise RuntimeError("A completed capture reader cannot execute capture work")

    builder = StateGraph(_CaptureState)
    builder.add_node("capture_context", read_only_capture)
    builder.add_edge(START, "capture_context")
    builder.add_edge("capture_context", END)
    graph = builder.compile(checkpointer=checkpointer)
    snapshot = await graph.aget_state(saved.config)
    if snapshot.next or snapshot.tasks:
        raise ValueError("The original initial context is not completely saved")
    values = saved.checkpoint["channel_values"]
    return _restore_context(
        values.get("binding"), values.get("request_snapshot"), scope, read_limit=_read_limit(values)
    )


async def capture_turn_context(
    role_history: RoleContextHistory,
    *,
    data: ConsultantContextWorkflow,
    template: ResponseRequest,
    prepared_history: NativeItems,
    jd_read_max_result_characters: int = DEFAULT_JD_READ_MAX_RESULT_CHARACTERS,
) -> TurnContext:
    """Pin data after RoleContextHistory.prepare_history, using its exact returned items.

    Reentry restores the original request/settings, even if today's template differs.
    An interrupted capture uses native pending writes/None resume, not time travel.
    The caller owns preparation/recovery and supplies a template with empty input and
    complete role settings/tool definitions; handlers can be built after binding.

    Capacity checking belongs to the response loop; this normal path loads the entire
    recent range without truncation. No role prompt or notification tool is added here.
    """
    scope = role_history.writer.scope
    if scope.kind != ExecutionKind.CONSULTANT_TURN or role_history.role != AgentRole.JOB_CONSULTANT:
        raise ExecutionStateError("Only the consultant can capture Turn context")
    await role_history.ensure_active()

    async def capture_context(state: _CaptureState) -> _CaptureState:
        request = _restore_request(state.get("request_snapshot"))
        captured = await data.capture(
            role_history.writer, plan_enabled=has_interview_plan_tools(request)
        )
        return _project_data(scope, captured, request)

    builder = StateGraph(_CaptureState)
    builder.add_node("capture_context", capture_context)
    builder.add_edge(START, "capture_context")
    builder.add_edge("capture_context", END)
    graph = builder.compile(checkpointer=role_history.checkpointer)
    # Never share channels with the preparation/response graphs or depend on writer ID.
    config: RunnableConfig = {
        "configurable": {
            "thread_id": f"{scope.job_file_id}:{scope.execution_id}:job_consultant:initial_context",
            "checkpoint_ns": "",
        }
    }
    saved = await graph.aget_state(config)
    initial: _CaptureState | None = None
    if saved.created_at is None:
        if template.create_payload()["input"]:
            raise ValueError("The role template must not contain history, maps or current input")
        await data.require_uncaptured_start(role_history.writer)
        initial = {
            "request_snapshot": {**template.create_payload(), "input": prepared_history},
            "jd_read_max_result_characters": jd_read_max_result_characters,
        }
    if initial is not None or saved.next or saved.tasks:
        await graph.ainvoke(initial, config, durability="sync")
    # get_state may project pending writes. Return only the complete persisted boundary,
    # never a node result that has not reached the saver (nor an arbitrary latest graph).
    raw = await role_history.checkpointer.aget_tuple(config)
    if raw is None:
        raise ValueError("The initial context checkpoint is unavailable")
    checkpoint = await graph.aget_state(raw.config)
    if checkpoint.next or checkpoint.tasks:
        raise ValueError("The initial context checkpoint has unfinished capture work")
    values = raw.checkpoint["channel_values"]
    result = _restore_context(
        values.get("binding"), values.get("request_snapshot"), scope, read_limit=_read_limit(values)
    )
    await role_history.ensure_active()
    return result


def _project_data(
    scope: ExecutionScope, captured: ConsultantContextData, request: ResponseRequest
) -> _CaptureState:
    snapshot_id = captured.snapshot_id
    frontier = captured.interview_scope.through_sequence
    original = captured.current_input
    position = captured.candidate_position
    covered = captured.covered_through_sequence
    recent = captured.recent
    memory_failure = captured.memory_failure_reason
    plan = captured.plan
    maps = {
        f"{layer.value}_map": MemoryMap(
            items=[
                MemoryMapItem(target_title=item.title, description=item.description)
                for item in entries
            ]
        ).model_dump(mode="json")
        for layer, entries in (
            (MemoryLayer.WORK_SITUATION, captured.situation_map),
            (MemoryLayer.WORK_UNDERSTANDING, captured.understanding_map),
        )
    }
    historical = HistoricalInterview(
        data_kind="historical_interview",
        messages=[
            HistoricalInterviewMessage(
                interview_sequence=message.interview_sequence,
                speaker=Speaker(message.speaker.value),
                text=message.interview_text,
            )
            for message in recent.messages
        ],
    )
    app_data = {
        "data_kind": REFERENCE_DATA_KIND,
        **maps,
        "historical_interview": historical.model_dump(mode="json"),
        "interview_read_boundary": {
            "covered_through_sequence": covered,
            "through_sequence": frontier,
            "context_sequences": list(recent.context_sequences),
        },
    }
    if memory_failure is not None:
        app_data["memory_consolidation"] = {
            "status": "blocked",
            "failure_reason": memory_failure,
            "next_action": (
                "繼續訪談；使用目前已發布記憶、近期原話與 read_interview，不宣稱已更新。"
            ),
        }
    payload = request.create_payload()
    payload["input"] = [
        *payload["input"],
        *([interview_plan_item(plan.body)] if plan is not None else []),
        {"role": "user", "content": json.dumps(app_data, ensure_ascii=False)},
        {"role": "user", "content": original.interview_text},
    ]
    common_binding = {
        "version": 1,
        "job_file_id": str(scope.job_file_id),
        "execution_id": str(scope.execution_id),
        "snapshot_id": str(snapshot_id) if snapshot_id is not None else None,
        "interview_through_sequence": frontier,
        "current_input_source_id": str(original.source_id),
        "candidate_generation_id": str(position.scope.generation_id),
        "candidate_base_revision_id": str(position.base_revision_id),
        "candidate_revision_id": str(position.revision_id),
    }
    binding: _BindingSnapshot
    if plan is not None:
        binding = _BINDING.validate_python(
            {
                **common_binding,
                "version": 2,
                "plan_base_revision_id": str(plan.position.revision_id),
            }
        )
    else:
        binding = _BINDING.validate_python(common_binding)
    _restore_context(binding, payload, scope)
    return {"request_snapshot": payload, "binding": binding}


def _restore_request(value: object) -> ResponseRequest:
    snapshot = _REQUEST.validate_python(value, strict=True)
    return ResponseRequest.from_snapshot(snapshot)


def _restore_context(
    binding_value: object,
    request_value: object,
    scope: ExecutionScope,
    *,
    read_limit: int = DEFAULT_JD_READ_MAX_RESULT_CHARACTERS,
) -> TurnContext:
    binding = _BINDING.validate_python(binding_value)
    if json.dumps(binding, sort_keys=True) != json.dumps(binding_value, sort_keys=True):
        raise ValueError("The saved initial binding must preserve its original JSON types")
    if (UUID(binding["job_file_id"]), UUID(binding["execution_id"])) != (
        scope.job_file_id,
        scope.execution_id,
    ):
        raise ExecutionStateError("The initial context belongs to another Turn")
    snapshot_id = binding["snapshot_id"]
    request = _restore_request(request_value)
    if has_interview_plan_tools(request) != (binding["version"] == 2):
        raise ExecutionStateError("The saved context and interview plan capability disagree")
    return TurnContext(
        request=request,
        jd_read_max_result_characters=read_limit,
        memory_binding=PublishedMemoryRead(
            scope,
            UUID(snapshot_id) if snapshot_id is not None else None,
            binding["interview_through_sequence"],
        ),
        candidate_position=JdCandidatePosition(
            JdCandidateScope(scope.execution_id, UUID(binding["candidate_generation_id"])),
            UUID(binding["candidate_base_revision_id"]),
            UUID(binding["candidate_revision_id"]),
        ),
        current_input_source_id=UUID(binding["current_input_source_id"]),
        plan_position=(
            PlanPosition(
                scope.job_file_id, scope.execution_id, UUID(binding["plan_base_revision_id"])
            )
            if binding["version"] == 2
            else None
        ),
    )


def _read_limit(values: dict[str, object]) -> int:
    """舊 checkpoint 未帶此值時沿既有上限；不以今日候選重建已捕捉的工具行為。"""
    value = values.get("jd_read_max_result_characters", DEFAULT_JD_READ_MAX_RESULT_CHARACTERS)
    if type(value) is not int or value < 1:
        raise ExecutionStateError("The saved JD read result limit is invalid")
    return value
