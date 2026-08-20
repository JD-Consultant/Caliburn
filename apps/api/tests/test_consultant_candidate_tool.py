from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import cast
from uuid import UUID, uuid4

import pytest
from langgraph.prebuilt import ToolNode, ToolRuntime
from langgraph.graph import END, START, StateGraph
from langchain_core.tools import BaseTool
from langchain.agents.middleware.types import AgentState

from app.consultant.candidate_tool import (
    CandidateEditToolBinding,
    build_job_document_candidate_edit_tool,
)
from app.consultant.candidate_wire import (
    CandidateEditBatch,
    OutputDocumentChange,
    OutputDocumentField,
    OutputDocumentTarget,
    OutputDuty,
    OutputOpksItem,
    OutputOpksKind,
)
from app.consultant.candidate_workspace import (
    CandidateEditAction,
    CandidateEditReceipt,
    CandidateEditRejected,
    CandidateStageRequest,
)
from app.consultant.provider_wire import OutputAnalysisBasis
from langchain_core.messages import AIMessage, ToolMessage


@dataclass
class RecordingCandidateStagePort:
    outcomes: list[CandidateEditReceipt | BaseException]
    requests: list[tuple[UUID, CandidateStageRequest]] = field(default_factory=list)

    async def stage_candidate_revision(
        self,
        *,
        document_id: UUID,
        request: CandidateStageRequest,
    ) -> CandidateEditReceipt:
        self.requests.append((document_id, request))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _duty_change() -> OutputDocumentChange:
    return OutputDocumentChange(
        change_ref="candidate-duty",
        depends_on_change_refs=(),
        depends_on_action_ids=(),
        supersedes_action_ids=(),
        atomic_group_ref="duty-group",
        operation="add",
        target=OutputDocumentTarget.DUTY,
        target_id="",
        field=OutputDocumentField.ENTITY,
        text_value="",
        integer_value=-1,
        uuid_value="",
        uuid_values=(),
        enablers=(),
        duties=(
            OutputDuty(
                duty_id="",
                entity_ref="candidate-duty",
                statement="管理採購作業",
                display_order=-1,
            ),
        ),
        tasks=(),
        opks_items=(),
        opks_kind=OutputOpksKind.NONE,
        task_ids=(),
        indicator_ids=(),
        basis_ordinal=1,
    )


def _unknown_task_linkage_change() -> OutputDocumentChange:
    unknown_task_id = uuid4()
    return OutputDocumentChange(
        change_ref="candidate-output",
        depends_on_change_refs=(),
        depends_on_action_ids=(),
        supersedes_action_ids=(),
        atomic_group_ref="",
        operation="add",
        target=OutputDocumentTarget.OPKS,
        target_id="",
        field=OutputDocumentField.ENTITY,
        text_value="",
        integer_value=-1,
        uuid_value="",
        uuid_values=(),
        enablers=(),
        duties=(),
        tasks=(),
        opks_items=(
            OutputOpksItem(
                item_id="",
                entity_ref="candidate-output",
                text="完成採購需求彙整",
                display_order=-1,
                task_ids=(unknown_task_id,),
                indicator_ids=(),
                task_refs=(),
                indicator_refs=(),
            ),
        ),
        opks_kind=OutputOpksKind.OUTPUT,
        task_ids=(unknown_task_id,),
        indicator_ids=(),
        basis_ordinal=1,
    )


def _batch(
    source_id: UUID,
    *,
    base_candidate_revision: int = 0,
    change: OutputDocumentChange | None = None,
) -> CandidateEditBatch:
    return CandidateEditBatch(
        base_candidate_revision=base_candidate_revision,
        summary="建立可審核的候選文件。",
        analysis_bases=(
            OutputAnalysisBasis(
                source_ids=(source_id,),
                quote_anchors=(),
                skill_ids=("task-boundary",),
            ),
        ),
        replacement_changes=(change or _duty_change(),),
    )


def _receipt() -> CandidateEditReceipt:
    action_id = uuid4()
    dependency_id = uuid4()
    superseded_action_id = uuid4()
    atomic_group_id = uuid4()
    return CandidateEditReceipt(
        candidate_revision=1,
        revision_digest="a" * 64,
        changeset_id=uuid4(),
        action_ids=(action_id,),
        external_dependency_action_ids=(dependency_id,),
        actions=(
            CandidateEditAction(
                action_id=action_id,
                operation="add",
                path="/duties",
                before=None,
                after={
                    "duty_id": str(uuid4()),
                    "statement": "管理採購作業",
                    "display_order": 0,
                },
                depends_on_action_ids=(dependency_id,),
                supersedes_action_ids=(superseded_action_id,),
                atomic_subgroup_id=atomic_group_id,
                status="pending",
                stale_reason=None,
            ),
        ),
    )


def _binding(
    runtime: RecordingCandidateStagePort,
    *,
    document_id: UUID,
    run_id: UUID,
    baseline_revision: int = 7,
) -> CandidateEditToolBinding:
    return CandidateEditToolBinding(
        runtime=runtime,
        document_id=document_id,
        run_id=run_id,
        baseline_revision=baseline_revision,
        selected_skill_ids=("task-boundary",),
    )


async def _tool_message(
    tool: object,
    batch: CandidateEditBatch,
    *,
    tool_call_id: str,
) -> ToolMessage:
    builder = StateGraph(AgentState)
    builder.add_node(
        "tools",
        ToolNode([cast(BaseTool, tool)], handle_tool_errors=False),
    )
    builder.add_edge(START, "tools")
    builder.add_edge("tools", END)
    result = await builder.compile().ainvoke(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "job_document_candidate_edit",
                            "args": batch.model_dump(mode="json"),
                            "id": tool_call_id,
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        }
    )
    message = result["messages"][-1]
    assert isinstance(message, ToolMessage)
    return message


@pytest.mark.asyncio
async def test_candidate_edit_tool_exposes_only_strict_batch_schema_and_materialized_receipt() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    receipt = _receipt()
    runtime = RecordingCandidateStagePort(outcomes=[receipt])
    tool = build_job_document_candidate_edit_tool(
        binding=_binding(runtime, document_id=document_id, run_id=run_id),
        loaded_skill_ids=lambda: ("task-boundary",),
    )

    assert tool.name == "job_document_candidate_edit"
    assert tool.tool_call_schema is CandidateEditBatch
    schema = tool.tool_call_schema.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {
        "base_candidate_revision",
        "summary",
        "analysis_bases",
        "replacement_changes",
    }
    assert CandidateEditBatch.model_json_schema()["required"] == schema["required"]
    schema_text = json.dumps(schema, ensure_ascii=False)
    assert all(
        forbidden not in schema_text
        for forbidden in (
            "document_id",
            "run_id",
            "baseline_revision",
            "selected_skill_ids",
            "loaded_skill_ids",
            "runtime",
            "raw_state",
            "checkpoint",
        )
    )

    message = await _tool_message(
        tool,
        _batch(source_id),
        tool_call_id="candidate-tool-1",
    )
    payload = json.loads(message.content)

    assert message.name == "job_document_candidate_edit"
    assert message.tool_call_id == "candidate-tool-1"
    assert payload == {
        "status": "applied",
        "candidate_revision": 1,
        "revision_digest": "a" * 64,
        "changeset_id": str(receipt.changeset_id),
        "action_ids": [str(receipt.action_ids[0])],
        "external_dependency_action_ids": [
            str(receipt.external_dependency_action_ids[0])
        ],
        "actions": [
            {
                "action_id": str(receipt.action_ids[0]),
                "operation": "add",
                "path": "/duties",
                "before": None,
                "after": receipt.actions[0].after,
                "depends_on_action_ids": [
                    str(receipt.external_dependency_action_ids[0])
                ],
                "supersedes_action_ids": [
                    str(receipt.actions[0].supersedes_action_ids[0])
                ],
                "atomic_subgroup_id": str(receipt.actions[0].atomic_subgroup_id),
                "status": "pending",
                "stale_reason": None,
            }
        ],
    }
    assert runtime.requests[0][0] == document_id
    request = runtime.requests[0][1]
    assert request.run_id == run_id
    assert request.baseline_revision == 7
    assert request.tool_call_id == "candidate-tool-1"
    assert request.selected_skill_ids == ("task-boundary",)
    assert request.loaded_skill_ids == ("task-boundary",)


@pytest.mark.asyncio
async def test_candidate_edit_tool_rejects_invalid_stage_without_mutation_then_allows_same_base_repair() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    runtime = RecordingCandidateStagePort(
        outcomes=[
            CandidateEditRejected(
                baseline_revision=7,
                candidate_revision=0,
                issues=("OPKS task linkage references an unknown Task handle",),
            ),
            _receipt(),
        ]
    )
    tool = build_job_document_candidate_edit_tool(
        binding=_binding(runtime, document_id=document_id, run_id=run_id),
        loaded_skill_ids=lambda: ("task-boundary",),
    )

    rejected = await _tool_message(
        tool,
        _batch(source_id, change=_unknown_task_linkage_change()),
        tool_call_id="candidate-tool-invalid",
    )
    rejected_payload = json.loads(rejected.content)
    applied = await _tool_message(
        tool,
        _batch(source_id),
        tool_call_id="candidate-tool-repaired",
    )

    assert rejected_payload == {
        "status": "rejected",
        "baseline_revision": 7,
        "candidate_revision": 0,
        "issues": ["OPKS task linkage references an unknown Task handle"],
    }
    assert json.loads(applied.content)["status"] == "applied"
    assert [request.batch.base_candidate_revision for _, request in runtime.requests] == [
        0,
        0,
    ]
    assert [request.tool_call_id for _, request in runtime.requests] == [
        "candidate-tool-invalid",
        "candidate-tool-repaired",
    ]


@pytest.mark.asyncio
async def test_candidate_edit_tool_leaves_unknown_infrastructure_errors_for_retry_middleware() -> None:
    runtime = RecordingCandidateStagePort(outcomes=[RuntimeError("checkpoint unavailable")])
    tool = build_job_document_candidate_edit_tool(
        binding=_binding(runtime, document_id=uuid4(), run_id=uuid4()),
        loaded_skill_ids=lambda: ("task-boundary",),
    )
    runtime_context = ToolRuntime(
        state={},
        context={},
        config={},
        stream_writer=lambda _value: None,
        tool_call_id="candidate-tool-infrastructure",
        store=None,
    )

    with pytest.raises(RuntimeError, match="checkpoint unavailable"):
        await tool.coroutine(  # type: ignore[misc] - test invokes the ToolRuntime boundary directly
            **_batch(uuid4()).model_dump(mode="python"),
            runtime=runtime_context,
        )
