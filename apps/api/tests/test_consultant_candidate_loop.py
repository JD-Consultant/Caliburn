from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.adapters.langgraph.postgres import open_postgres_consultant_runtime
from app.config import Settings
from app.consultant.candidate_wire import (
    CandidateEditBatch,
    CandidateEditOperation,
    OutputDocumentChange,
    OutputDocumentField,
    OutputDocumentTarget,
    OutputOpksItem,
    OutputOpksKind,
    OutputResponsibilityRole,
    OutputTask,
)
from app.consultant.model_output import (
    ConsultantModelOutput,
    OutputAnalysisBasis,
    OutputCandidatePublication,
    OutputQuestion,
    OutputQuestionKind,
    OutputSufficiency,
)
from app.consultant.provider_wire import OutputQuoteAnchor
from app.consultant.document_review import AtomicSubgroupIncomplete, DocumentReviewError
from app.consultant.run_service import build_configured_execution, execute_admitted_consultant_turn
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
    DocumentChangeStatus,
)
from app.consultant.verification import ConsultantVerificationError
from app.consultant.workspace_resources import WorkspaceCatalog, project_candidate_files


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL", "")
    if not value:
        pytest.fail("Task 6 requires an explicit local TEST_DATABASE_URL")
    if "localhost" not in value and "127.0.0.1" not in value:
        pytest.fail("Task 6 may only clean an explicit local PostgreSQL database")
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


@dataclass
class _OwnedDocuments:
    document_ids: set[UUID] = field(default_factory=set)


@pytest_asyncio.fixture
async def owned_documents() -> AsyncIterator[_OwnedDocuments]:
    owned = _OwnedDocuments()
    try:
        yield owned
    finally:
        database_url = _database_url()
        for document_id in owned.document_ids:
            async with open_postgres_consultant_runtime(database_url) as runtime:
                await runtime.delete_document(document_id)
        if owned.document_ids:
            async with await psycopg.AsyncConnection.connect(
                database_url, autocommit=True
            ) as connection:
                async with connection.cursor() as cursor:
                    await cursor.executemany(
                        "DELETE FROM consultant_documents WHERE document_id = %s",
                        [(document_id,) for document_id in owned.document_ids],
                    )


def _output(
    source_id: UUID,
    *,
    candidate_revision: int = 0,
    revision_digest: str = "",
    action_ids: tuple[UUID, ...] = (),
) -> ConsultantModelOutput:
    return ConsultantModelOutput(
        visible_reply="我已整理這次職務分析，請由您決定是否採用候選變更。",
        analysis_bases=(
            OutputAnalysisBasis(
                source_ids=(source_id,), quote_anchors=(), skill_ids=("task-boundary",)
            ),
        ),
        reply_basis_ordinal=1,
        used_skill_ids=("task-boundary",),
        understanding_changes=(),
        attention_changes=(),
        gaps=(),
        candidate_publication=OutputCandidatePublication(
            candidate_revision=candidate_revision,
            revision_digest=revision_digest,
            action_ids=action_ids,
        ),
        question=OutputQuestion(
            kind=OutputQuestionKind.NONE,
            text="",
            answer_target="",
            reason="",
            current_understanding="",
            choices=(),
            affected_work_ids=(),
            affected_branch="",
            basis_ordinal=0,
        ),
        sufficiency=OutputSufficiency(
            currently_enough=True,
            reason="本輪已足以建立候選，其他細節可在後續補充。",
            remaining_gap_reasons=(),
            continuing_benefit="持續訪談可補充其他工作內容。",
            basis_ordinal=1,
        ),
    )


class _ScriptedCandidateModel(FakeMessagesListChatModel):
    """Deterministic LangChain model that derives the final reference from ToolMessage."""

    bound_tool_names: list[str] = []
    seen_messages: list[list[BaseMessage]] = []
    final_factory: Callable[[dict[str, Any]], ConsultantModelOutput] | None = None
    tool_results: list[tuple[str, dict[str, Any]]] = []
    event_trace: list[str] = []
    _recorded_tool_call_ids: set[str] = set()

    def bind_tools(self, tools: Any, **kwargs: Any) -> _ScriptedCandidateModel:
        del kwargs
        self.bound_tool_names = [
            getattr(tool, "name", None) or tool.get("name", "") for tool in tools
        ]
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        self.seen_messages.append(messages)
        tool_messages = [item for item in messages if isinstance(item, ToolMessage)]
        for item in tool_messages:
            if item.tool_call_id not in self._recorded_tool_call_ids:
                self._recorded_tool_call_ids.add(item.tool_call_id)
                if item.name == "job_document_candidate_edit":
                    payload = json.loads(item.content)
                    self.tool_results.append((item.name, payload))
                    self.event_trace.append(
                        f"tool_result:{item.tool_call_id}:{payload['status']}"
                    )
        if any(
            item.name == "job_document_candidate_edit" for item in tool_messages
        ):
            payload = json.loads(tool_messages[-1].content)
            if payload["status"] == "rejected":
                if len(self.responses) < 3:
                    raise AssertionError(payload["issues"])
                rejected_results = [
                    result
                    for name, result in self.tool_results
                    if name == "job_document_candidate_edit"
                    and result["status"] == "rejected"
                ]
                if len(rejected_results) > 1:
                    raise AssertionError(payload["issues"])
                response = self.responses[2]
            elif self.final_factory is None:
                raise AssertionError("script is missing its final response factory")
            elif payload["status"] != "applied":
                raise AssertionError(payload)
            else:
                response = AIMessage(content=self.final_factory(payload).model_dump_json())
        elif tool_messages:
            response = self.responses[1]
        else:
            response = self.responses[0]
        for tool_call in response.tool_calls:
            self.event_trace.append(f"model_call:{tool_call['id']}")
        response = response.model_copy(
            update={
                "response_metadata": {
                    "model_name": "scripted-consultant",
                    "provider": "OpenAI",
                    "cost": "0",
                    "finish_reason": "stop",
                },
                "usage_metadata": {
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "total_tokens": 2,
                },
            }
        )
        return ChatResult(generations=[ChatGeneration(message=response)])


def _task_and_opks_batch(source_id: UUID) -> CandidateEditBatch:
    task = OutputDocumentChange(
        change_ref="task-create",
        depends_on_change_refs=(),
        depends_on_action_ids=(),
        supersedes_action_ids=(),
        atomic_group_ref="",
        operation="add",
        target=OutputDocumentTarget.TASK,
        target_id="",
        field=OutputDocumentField.ENTITY,
        text_value="",
        integer_value=-1,
        uuid_value="",
        uuid_values=(),
        enablers=(),
        duties=(),
        tasks=(
            OutputTask(
                task_id="",
                duty_id="",
                entity_ref="task-create",
                duty_ref="",
                statement="彙整採購需求並完成請購資料。",
                action="彙整",
                object="採購需求",
                purpose_result="完成可送審的請購資料",
                context="依內部需求與庫存狀況",
                frequency_text="每日",
                responsibility_role=OutputResponsibilityRole.PRIMARY,
                enablers=(),
                display_order=-1,
            ),
        ),
        opks_items=(),
        opks_kind=OutputOpksKind.NONE,
        task_ids=(),
        indicator_ids=(),
        basis_ordinal=1,
    )
    opks = task.model_copy(
        update={
            "change_ref": "output-create",
            "depends_on_change_refs": ("task-create",),
            "target": OutputDocumentTarget.OPKS,
            "tasks": (),
            "opks_kind": OutputOpksKind.OUTPUT,
            "opks_items": (
                OutputOpksItem(
                    item_id="",
                    entity_ref="output-create",
                    text="完成可送審的請購資料",
                    display_order=-1,
                    task_ids=(),
                    indicator_ids=(),
                    task_refs=("task-create",),
                    indicator_refs=(),
                ),
            ),
        }
    )
    performance = opks.model_copy(
        update={
            "change_ref": "performance-create",
            "opks_kind": OutputOpksKind.PERFORMANCE_INDICATOR,
            "opks_items": (
                OutputOpksItem(
                    item_id="",
                    entity_ref="performance-create",
                    text="請購資料在時限內完成並可送審",
                    display_order=-1,
                    task_ids=(),
                    indicator_ids=(),
                    task_refs=("task-create",),
                    indicator_refs=(),
                ),
            ),
        }
    )
    return CandidateEditBatch(
        base_candidate_revision=0,
        summary="建立一項 Task 與其 Output、Performance Indicator。",
        analysis_bases=(
            OutputAnalysisBasis(
                source_ids=(source_id,), quote_anchors=(), skill_ids=("task-boundary",)
            ),
        ),
        replacement_changes=(task, opks, performance),
    )


_NINE_TASK_STATEMENTS = (
    "核對採購需求",
    "確認庫存狀況",
    "整理請購資料",
    "檢查供應商資訊",
    "建立請購單",
    "送出主管審核",
    "追蹤審核結果",
    "處理退回修正",
    "通知需求單位",
)


def _nine_tasks_and_rejected_output_batch(
    source_id: UUID,
    *,
    source_text: str,
) -> CandidateEditBatch:
    template = _task_and_opks_batch(source_id).replacement_changes[0]
    tasks = tuple(
        template.model_copy(
            update={
                "change_ref": f"task-{index}",
                "tasks": (
                    template.tasks[0].model_copy(
                        update={
                            "entity_ref": f"task-{index}",
                            "statement": statement,
                            "action": "處理",
                            "object": statement,
                        }
                    ),
                ),
            }
        )
        for index, statement in enumerate(_NINE_TASK_STATEMENTS)
    )
    output_template = _task_and_opks_batch(source_id).replacement_changes[1]
    rejected_output = output_template.model_copy(
        update={
            "change_ref": "output-to-reject",
            "depends_on_change_refs": ("task-0",),
            "opks_items": (
                output_template.opks_items[0].model_copy(
                    update={
                        "entity_ref": "output-to-reject",
                        "text": "模型誤判的採購總表",
                        "task_refs": ("task-0",),
                    }
                ),
            ),
        }
    )
    return CandidateEditBatch(
        base_candidate_revision=0,
        summary="建立九項工作與一項仍需員工裁決的 Output。",
        analysis_bases=(
            OutputAnalysisBasis(
                source_ids=(source_id,),
                quote_anchors=(
                    OutputQuoteAnchor(
                        source_id=source_id,
                        start=0,
                        end=len(source_text),
                        quote=source_text,
                    ),
                ),
                skill_ids=("task-boundary",),
            ),
        ),
        replacement_changes=(*tasks, rejected_output),
    )


def _oversized_task_document(
    document_id: UUID,
    *,
    duty_id: UUID,
    task_id: UUID,
    output_id: UUID,
    evidence_source_id: UUID,
) -> ApprovedJobDocument:
    return ApprovedJobDocument(
        document_id=document_id,
        duties=(
            ApprovedDuty(
                duty_id=duty_id,
                statement="辦理採購作業",
                display_order=0,
            ),
        ),
        tasks=(
            ApprovedTask(
                task_id=task_id,
                duty_id=duty_id,
                statement="彙整需求、建立請購資料並追蹤送審結果",
                action="辦理",
                object="請購作業",
                display_order=0,
            ),
        ),
        opks=(
            ApprovedOpksItem(
                item_id=output_id,
                kind=ApprovedOpksKind.OUTPUT,
                text="完成送審的請購資料",
                display_order=0,
                task_ids=(task_id,),
                evidence_source_ids=(evidence_source_id,),
            ),
        ),
    )


def _atomic_task_replacement_batch(
    source_id: UUID,
    *,
    duty_id: UUID,
    original_task_id: UUID,
    original_output_id: UUID,
) -> CandidateEditBatch:
    task_template, output_template, _ = _task_and_opks_batch(
        source_id
    ).replacement_changes
    group = "task-restructure"
    withdraw_output = output_template.model_copy(
        update={
            "change_ref": "withdraw-old-output",
            "atomic_group_ref": group,
            "operation": CandidateEditOperation.WITHDRAW,
            "target_id": str(original_output_id),
            "opks_items": (),
            "opks_kind": OutputOpksKind.OUTPUT,
            "depends_on_change_refs": (),
            "task_ids": (original_task_id,),
        }
    )
    withdraw_task = task_template.model_copy(
        update={
            "change_ref": "withdraw-old-task",
            "depends_on_change_refs": ("withdraw-old-output",),
            "atomic_group_ref": group,
            "operation": CandidateEditOperation.WITHDRAW,
            "target_id": str(original_task_id),
            "tasks": (),
        }
    )

    def replacement_task(change_ref: str, statement: str, action: str) -> OutputDocumentChange:
        return task_template.model_copy(
            update={
                "change_ref": change_ref,
                "depends_on_change_refs": (),
                "atomic_group_ref": group,
                "tasks": (
                    task_template.tasks[0].model_copy(
                        update={
                            "entity_ref": change_ref,
                            "duty_id": str(duty_id),
                            "statement": statement,
                            "action": action,
                            "object": "請購資料",
                            "purpose_result": "完成可送審的請購資料",
                        }
                    ),
                ),
            }
        )

    first_task = replacement_task(
        "prepare-request", "彙整需求並建立請購資料", "彙整"
    )
    second_task = replacement_task(
        "track-approval", "追蹤請購送審結果並處理退回", "追蹤"
    )

    def replacement_output(change_ref: str, task_ref: str, text: str) -> OutputDocumentChange:
        return output_template.model_copy(
            update={
                "change_ref": change_ref,
                "depends_on_change_refs": (task_ref,),
                "atomic_group_ref": group,
                "opks_items": (
                    output_template.opks_items[0].model_copy(
                        update={
                            "entity_ref": change_ref,
                            "text": text,
                            "task_refs": (task_ref,),
                        }
                    ),
                ),
            }
        )

    return CandidateEditBatch(
        base_candidate_revision=0,
        summary="以通用 typed operations 原子重組過大的 Task。",
        analysis_bases=(
            OutputAnalysisBasis(
                source_ids=(source_id,),
                quote_anchors=(),
                skill_ids=("task-boundary",),
            ),
        ),
        replacement_changes=(
            withdraw_output,
            withdraw_task,
            first_task,
            second_task,
            replacement_output(
                "prepared-output", "prepare-request", "完成可送審的請購資料"
            ),
            replacement_output(
                "approval-output", "track-approval", "完成送審結果追蹤紀錄"
            ),
        ),
    )


def _task_statement_candidate_batch(
    source_id: UUID,
    *,
    source_text: str,
    task_id: UUID,
    statement: str,
) -> CandidateEditBatch:
    template = _task_and_opks_batch(source_id).replacement_changes[0]
    change = template.model_copy(
        update={
            "change_ref": "revise-task-statement",
            "operation": CandidateEditOperation.REVISE,
            "target_id": str(task_id),
            "field": OutputDocumentField.STATEMENT,
            "text_value": statement,
            "tasks": (),
        }
    )
    return CandidateEditBatch(
        base_candidate_revision=0,
        summary="修正目前 Task 敘述。",
        analysis_bases=(
            OutputAnalysisBasis(
                source_ids=(source_id,),
                quote_anchors=(
                    OutputQuoteAnchor(
                        source_id=source_id,
                        start=0,
                        end=len(source_text),
                        quote=source_text,
                    ),
                ),
                skill_ids=("task-boundary",),
            ),
        ),
        replacement_changes=(change,),
    )
@pytest.mark.asyncio
async def test_candidate_tool_loop_publishes_local_ref_task_and_opks_only_after_employee_acceptance(
    owned_documents: _OwnedDocuments,
) -> None:
    """A regression here means ToolNode/final-reference publication was bypassed."""

    database_url = _database_url()
    document_id, run_id, source_id = uuid4(), uuid4(), uuid4()
    owned_documents.document_ids.add(document_id)
    batch = _task_and_opks_batch(source_id)
    model = _ScriptedCandidateModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {"file_path": "/skills/task-boundary/SKILL.md"},
                        "id": "load-task-boundary",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "job_document_candidate_edit",
                        "args": batch.model_dump(mode="json"),
                        "id": "candidate-create-task-opks",
                        "type": "tool_call",
                    }
                ],
            )
        ],
        final_factory=lambda receipt: _output(
            source_id,
            candidate_revision=receipt["candidate_revision"],
            revision_digest=receipt["revision_digest"],
            action_ids=tuple(UUID(value) for value in receipt["action_ids"]),
        ),
    )

    async with open_postgres_consultant_runtime(database_url) as runtime:
        await runtime.create_document(document_id, title="Task 6 canary：採購")
        admitted, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我每天彙整採購需求，完成可以送審的請購資料。",
        )
        assert should_process is True

        published = await execute_admitted_consultant_turn(
            runtime=runtime,
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            execution=build_configured_execution(
                Settings(
                    _env_file=None,
                    openrouter_api_key="test-key",
                    consultant_provider="OpenAI",
                )
            ),
            model=model,
        )

        assert model.bound_tool_names == [
            "read_file",
            "employee_source_get",
            "employee_source_lineage",
            "employee_source_search",
            "job_document_candidate_edit",
        ]
        assert published.approved_document.tasks == ()
        bundle = published.document_review.bundles[0]
        assert len(bundle.actions) == 3
        accepted = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=published.revision,
            action="accept_changes",
            changeset_id=bundle.changeset_id,
            action_ids=tuple(action.action_id for action in bundle.actions),
        )
        assert len(accepted.approved_document.tasks) == 1
        created_task = accepted.approved_document.tasks[0]
        assert created_task.display_order == 0
        opks_by_kind = {
            item.kind: item for item in accepted.approved_document.opks
        }
        assert set(opks_by_kind) == {
            ApprovedOpksKind.OUTPUT,
            ApprovedOpksKind.PERFORMANCE_INDICATOR,
        }
        assert len(
            {
                created_task.task_id,
                *(item.item_id for item in accepted.approved_document.opks),
            }
        ) == 3
        for item in opks_by_kind.values():
            assert item.task_ids == (created_task.task_id,)
            assert item.display_order == 0
            assert item.evidence_source_ids == (source_id,)


@pytest.mark.asyncio
async def test_rejected_candidate_tool_result_precedes_the_scripted_repair_and_second_revision_publication(
    owned_documents: _OwnedDocuments,
) -> None:
    """A bad local linkage must be observed as ToolMessage before the repair call."""

    database_url = _database_url()
    document_id, run_id, source_id = uuid4(), uuid4(), uuid4()
    seed_source_id, duty_id, original_task_id, original_output_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    owned_documents.document_ids.add(document_id)
    repaired = _atomic_task_replacement_batch(
        source_id,
        duty_id=duty_id,
        original_task_id=original_task_id,
        original_output_id=original_output_id,
    )
    invalid_output = repaired.replacement_changes[-1].model_copy(
        update={
            "opks_items": (
                repaired.replacement_changes[-1].opks_items[0].model_copy(
                    update={"task_refs": ("missing-task",)}
                ),
            )
        }
    )
    invalid = repaired.model_copy(
        update={
            "replacement_changes": (
                *repaired.replacement_changes[:-1],
                invalid_output,
            )
        }
    )
    model = _ScriptedCandidateModel(
        responses=[
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {"file_path": "/skills/task-boundary/SKILL.md"}, "id": "load-split-skill", "type": "tool_call"}]),
            AIMessage(content="", tool_calls=[{"name": "job_document_candidate_edit", "args": invalid.model_dump(mode="json"), "id": "bad-split-link", "type": "tool_call"}]),
            AIMessage(content="", tool_calls=[{"name": "job_document_candidate_edit", "args": repaired.model_dump(mode="json"), "id": "repair-split-link", "type": "tool_call"}]),
        ],
        final_factory=lambda receipt: _output(
            source_id,
            candidate_revision=receipt["candidate_revision"],
            revision_digest=receipt["revision_digest"],
            action_ids=tuple(UUID(value) for value in receipt["action_ids"]),
        ),
    )
    async with open_postgres_consultant_runtime(database_url) as runtime:
        await runtime.create_document(document_id, title="Task 6 canary：修正 linkage")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=0,
            document=_oversized_task_document(
                document_id,
                duty_id=duty_id,
                task_id=original_task_id,
                output_id=original_output_id,
                evidence_source_id=seed_source_id,
            ),
            source_id=seed_source_id,
        )
        admitted, _ = await runtime.admit_employee_answer(
            document_id=document_id, run_id=run_id, source_id=source_id,
            text="我會拆開請購資料整理與送審確認兩項工作。",
        )
        published = await execute_admitted_consultant_turn(
            runtime=runtime, document_id=document_id, run_id=run_id, source_id=source_id,
            execution=build_configured_execution(Settings(_env_file=None, openrouter_api_key="test-key", consultant_provider="OpenAI")), model=model,
        )
        candidate_results = [payload for name, payload in model.tool_results if name == "job_document_candidate_edit"]
        assert [payload["status"] for payload in candidate_results] == ["rejected", "applied"]
        assert "unknown local ref" in candidate_results[0]["issues"][0]
        assert model.event_trace.index("tool_result:bad-split-link:rejected") < model.event_trace.index(
            "model_call:repair-split-link"
        )
        bundle = published.document_review.bundles[0]
        assert len(bundle.actions) == 6
        assert len({item.atomic_subgroup_id for item in bundle.actions}) == 1
        assert all(item.atomic_subgroup_id is not None for item in bundle.actions)
        with pytest.raises(AtomicSubgroupIncomplete):
            await runtime.decide_document_changes(
                document_id=document_id,
                expected_revision=published.revision,
                action="accept_changes",
                changeset_id=bundle.changeset_id,
                action_ids=(bundle.actions[0].action_id,),
            )
        accepted = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=published.revision,
            action="accept_changes",
            changeset_id=bundle.changeset_id,
            action_ids=tuple(action.action_id for action in bundle.actions),
        )
        assert accepted.revision == published.revision + 1
        assert {task.statement for task in accepted.approved_document.tasks} == {
            "彙整需求並建立請購資料",
            "追蹤請購送審結果並處理退回",
        }
        assert all(task.duty_id == duty_id for task in accepted.approved_document.tasks)
        assert original_task_id not in {
            task.task_id for task in accepted.approved_document.tasks
        }
        assert len(accepted.approved_document.opks) == 2
        assert original_output_id not in {
            item.item_id for item in accepted.approved_document.opks
        }
        assert {
            item.task_ids[0] for item in accepted.approved_document.opks
        } == {task.task_id for task in accepted.approved_document.tasks}


@pytest.mark.asyncio
async def test_nine_accept_one_output_reject_survives_reopen_and_shapes_the_next_real_context(
    owned_documents: _OwnedDocuments,
) -> None:
    """Rejected content stays decision memory; only employee-accepted work is truth."""

    database_url = _database_url()
    document_id = uuid4()
    first_run_id, first_source_id = uuid4(), uuid4()
    second_run_id, second_source_id = uuid4(), uuid4()
    owned_documents.document_ids.add(document_id)
    first_source_text = (
        "我的工作包括："
        + "、".join(_NINE_TASK_STATEMENTS)
        + "。採購總表由主管彙整，不是我的工作產出。"
    )
    batch = _nine_tasks_and_rejected_output_batch(
        first_source_id,
        source_text=first_source_text,
    )
    first_model = _ScriptedCandidateModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {"file_path": "/skills/task-boundary/SKILL.md"},
                        "id": "load-nine-task-skill",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "job_document_candidate_edit",
                        "args": batch.model_dump(mode="json"),
                        "id": "candidate-nine-tasks-one-output",
                        "type": "tool_call",
                    }
                ],
            ),
        ],
        final_factory=lambda receipt: _output(
            first_source_id,
            candidate_revision=receipt["candidate_revision"],
            revision_digest=receipt["revision_digest"],
            action_ids=tuple(UUID(value) for value in receipt["action_ids"]),
        ),
    )
    execution = build_configured_execution(
        Settings(
            _env_file=None,
            openrouter_api_key="test-key",
            consultant_provider="OpenAI",
        )
    )

    async with open_postgres_consultant_runtime(database_url) as runtime:
        await runtime.create_document(document_id, title="Task 6 canary：九收一拒")
        _, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=first_run_id,
            source_id=first_source_id,
            text=first_source_text,
        )
        assert should_process is True
        published = await execute_admitted_consultant_turn(
            runtime=runtime,
            document_id=document_id,
            run_id=first_run_id,
            source_id=first_source_id,
            execution=execution,
            model=first_model,
        )
        bundle = published.document_review.bundles[0]
        task_actions = tuple(action for action in bundle.actions if action.path == "/tasks")
        output_action = next(action for action in bundle.actions if action.path == "/opks")
        assert len(task_actions) == 9
        assert len(bundle.actions) == 10

        accepted = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=published.revision,
            action="accept_changes",
            changeset_id=bundle.changeset_id,
            action_ids=tuple(action.action_id for action in task_actions),
        )
        reviewed = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=accepted.revision,
            action="reject_changes",
            changeset_id=bundle.changeset_id,
            action_ids=(output_action.action_id,),
            rejection_reason="採購總表由主管彙整，不是我的工作產出。",
        )
        assert len(reviewed.approved_document.tasks) == 9
        assert reviewed.approved_document.opks == ()

    neutral_output = _output(second_source_id)
    second_model = _ScriptedCandidateModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {"file_path": "/skills/task-boundary/SKILL.md"},
                        "id": "reload-task-skill",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content=neutral_output.model_dump_json()),
        ]
    )
    async with open_postgres_consultant_runtime(database_url) as runtime:
        reopened = await runtime.reopen_document(document_id)
        assert len(reopened.approved_document.tasks) == 9
        _, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=second_run_id,
            source_id=second_source_id,
            text="我們可以繼續訪談下一個細節。",
        )
        assert should_process is True
        completed = await execute_admitted_consultant_turn(
            runtime=runtime,
            document_id=document_id,
            run_id=second_run_id,
            source_id=second_source_id,
            execution=execution,
            model=second_model,
        )
        raw_state = await runtime.raw_state(document_id)

    prompt = "\n".join(
        str(message.content)
        for call_messages in second_model.seen_messages
        for message in call_messages
    )
    approved_section = prompt.split("<approved_document_slice>", 1)[1].split(
        "</approved_document_slice>", 1
    )[0]
    orientation_section = prompt.split("<global_orientation>", 1)[1].split(
        "</global_orientation>", 1
    )[0]
    assert all(statement in orientation_section for statement in _NINE_TASK_STATEMENTS)
    assert orientation_section.count('"authority":"approved_document"') >= 9
    assert "模型誤判的採購總表" not in approved_section
    assert "模型誤判的採購總表" not in orientation_section
    assert '"status":"rejected"' in prompt
    assert "採購總表由主管彙整，不是我的工作產出。" in prompt
    assert second_model.tool_results == []
    assert completed.approved_document.opks == ()
    assert not any("stop" in key.casefold() for key in raw_state)


@pytest.mark.asyncio
async def test_direct_edit_blocks_an_unpublished_old_candidate_and_stales_a_published_read_set(
    owned_documents: _OwnedDocuments,
) -> None:
    """Employee authority wins both before publication and while review is pending."""

    database_url = _database_url()
    execution = build_configured_execution(
        Settings(
            _env_file=None,
            openrouter_api_key="test-key",
            consultant_provider="OpenAI",
        )
    )

    unpublished_document_id = uuid4()
    unpublished_run_id, unpublished_source_id = uuid4(), uuid4()
    correction_run_id, correction_source_id = uuid4(), uuid4()
    seed_source_id, direct_edit_source_id = uuid4(), uuid4()
    duty_id, task_id, output_id = uuid4(), uuid4(), uuid4()
    owned_documents.document_ids.add(unpublished_document_id)
    candidate_statement = "模型候選：建立請購資料並追蹤送審"
    candidate_source_text = f"我建議把這項工作寫成：{candidate_statement}。"
    unpublished_batch = _task_statement_candidate_batch(
        unpublished_source_id,
        source_text=candidate_source_text,
        task_id=task_id,
        statement=candidate_statement,
    )
    staged_receipt: dict[str, Any] = {}

    def abort_after_staging(receipt: dict[str, Any]) -> ConsultantModelOutput:
        staged_receipt.update(receipt)
        raise RuntimeError("intentional canary stop after candidate staging")

    staging_model = _ScriptedCandidateModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {"file_path": "/skills/task-boundary/SKILL.md"},
                        "id": "load-stale-baseline-skill",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "job_document_candidate_edit",
                        "args": unpublished_batch.model_dump(mode="json"),
                        "id": "stage-before-direct-edit",
                        "type": "tool_call",
                    }
                ],
            ),
        ],
        final_factory=abort_after_staging,
    )

    async with open_postgres_consultant_runtime(database_url) as runtime:
        initial = await runtime.create_document(
            unpublished_document_id,
            title="Task 6 canary：發布前 direct edit",
        )
        seeded = await runtime.apply_direct_edit(
            document_id=unpublished_document_id,
            expected_revision=initial.revision,
            document=_oversized_task_document(
                unpublished_document_id,
                duty_id=duty_id,
                task_id=task_id,
                output_id=output_id,
                evidence_source_id=seed_source_id,
            ),
            source_id=seed_source_id,
        )
        _, should_process = await runtime.admit_employee_answer(
            document_id=unpublished_document_id,
            run_id=unpublished_run_id,
            source_id=unpublished_source_id,
            text=candidate_source_text,
        )
        assert should_process is True
        with pytest.raises(
            RuntimeError,
            match="intentional canary stop after candidate staging",
        ):
            await execute_admitted_consultant_turn(
                runtime=runtime,
                document_id=unpublished_document_id,
                run_id=unpublished_run_id,
                source_id=unpublished_source_id,
                execution=execution,
                model=staging_model,
            )
        failed = await runtime.reopen_document(unpublished_document_id)
        failed_raw = await runtime.raw_state(unpublished_document_id)
        assert failed_raw["active_candidate"] is not None
        assert "active_candidate" not in failed.model_dump(mode="json")
        assert staged_receipt["status"] == "applied"

        employee_statement = "員工直接改成：只負責建立請購資料"
        employee_document = failed.approved_document.model_copy(
            update={
                "tasks": (
                    failed.approved_document.tasks[0].model_copy(
                        update={"statement": employee_statement}
                    ),
                ),
            }
        )
        edited = await runtime.apply_direct_edit(
            document_id=unpublished_document_id,
            expected_revision=failed.revision,
            document=employee_document,
            source_id=direct_edit_source_id,
        )
        assert "active_candidate" not in edited.model_dump(mode="json")
        assert (await runtime.raw_state(unpublished_document_id))[
            "active_candidate"
        ] is None

        _, should_process = await runtime.admit_employee_answer(
            document_id=unpublished_document_id,
            run_id=correction_run_id,
            source_id=correction_source_id,
            text="請以我剛剛直接修改的 Task 敘述為準。",
            supersedes_source_id=unpublished_source_id,
        )
        assert should_process is True
        stale_final = _output(
            correction_source_id,
            candidate_revision=staged_receipt["candidate_revision"],
            revision_digest=staged_receipt["revision_digest"],
            action_ids=tuple(UUID(value) for value in staged_receipt["action_ids"]),
        )
        stale_final_model = _ScriptedCandidateModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_file",
                            "args": {"file_path": "/skills/task-boundary/SKILL.md"},
                            "id": "reload-stale-final-skill",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content=stale_final.model_dump_json()),
            ]
        )
        with pytest.raises(
            ConsultantVerificationError,
            match="no active candidate workspace",
        ):
            await execute_admitted_consultant_turn(
                runtime=runtime,
                document_id=unpublished_document_id,
                run_id=correction_run_id,
                source_id=correction_source_id,
                execution=execution,
                model=stale_final_model,
            )
        after_failed_publication = await runtime.reopen_document(
            unpublished_document_id
        )
        assert after_failed_publication.approved_document.tasks[0].statement == (
            employee_statement
        )
        assert after_failed_publication.document_review.bundles == ()
        assert seeded.revision < after_failed_publication.revision

    published_document_id = uuid4()
    published_run_id, published_source_id = uuid4(), uuid4()
    published_seed_source_id, published_edit_source_id = uuid4(), uuid4()
    published_duty_id, published_task_id, published_output_id = (
        uuid4(),
        uuid4(),
        uuid4(),
    )
    owned_documents.document_ids.add(published_document_id)
    published_statement = "模型候選：負責追蹤請購送審結果"
    published_source_text = f"這項工作可以改成：{published_statement}。"
    published_batch = _task_statement_candidate_batch(
        published_source_id,
        source_text=published_source_text,
        task_id=published_task_id,
        statement=published_statement,
    )
    publication_model = _ScriptedCandidateModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {"file_path": "/skills/task-boundary/SKILL.md"},
                        "id": "load-published-stale-skill",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "job_document_candidate_edit",
                        "args": published_batch.model_dump(mode="json"),
                        "id": "publish-before-direct-edit",
                        "type": "tool_call",
                    }
                ],
            ),
        ],
        final_factory=lambda receipt: _output(
            published_source_id,
            candidate_revision=receipt["candidate_revision"],
            revision_digest=receipt["revision_digest"],
            action_ids=tuple(UUID(value) for value in receipt["action_ids"]),
        ),
    )

    async with open_postgres_consultant_runtime(database_url) as runtime:
        initial = await runtime.create_document(
            published_document_id,
            title="Task 6 canary：待審 direct edit",
        )
        await runtime.apply_direct_edit(
            document_id=published_document_id,
            expected_revision=initial.revision,
            document=_oversized_task_document(
                published_document_id,
                duty_id=published_duty_id,
                task_id=published_task_id,
                output_id=published_output_id,
                evidence_source_id=published_seed_source_id,
            ),
            source_id=published_seed_source_id,
        )
        await runtime.admit_employee_answer(
            document_id=published_document_id,
            run_id=published_run_id,
            source_id=published_source_id,
            text=published_source_text,
        )
        published = await execute_admitted_consultant_turn(
            runtime=runtime,
            document_id=published_document_id,
            run_id=published_run_id,
            source_id=published_source_id,
            execution=execution,
            model=publication_model,
        )
        bundle = published.document_review.bundles[0]
        pending_action = bundle.actions[0]
        employee_statement = "員工直接改成：只追蹤主管已核准案件"
        edited_document = published.approved_document.model_copy(
            update={
                "tasks": (
                    published.approved_document.tasks[0].model_copy(
                        update={"statement": employee_statement}
                    ),
                ),
            }
        )
        edited = await runtime.apply_direct_edit(
            document_id=published_document_id,
            expected_revision=published.revision,
            document=edited_document,
            source_id=published_edit_source_id,
        )
        stale_action = edited.document_review.bundles[0].actions[0]
        assert stale_action.action_id == pending_action.action_id
        assert stale_action.status is DocumentChangeStatus.STALE
        with pytest.raises(
            DocumentReviewError,
            match="only pending or deferred",
        ):
            await runtime.decide_document_changes(
                document_id=published_document_id,
                expected_revision=edited.revision,
                action="accept_changes",
                changeset_id=bundle.changeset_id,
                action_ids=(pending_action.action_id,),
            )
        final = await runtime.reopen_document(published_document_id)
        assert final.approved_document.tasks[0].statement == employee_statement


@pytest.mark.asyncio
async def test_workspace_check_only_records_receipt_then_publishes_exactly_once(
    owned_documents: _OwnedDocuments,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    direct_edit_source_id = uuid4()
    employee_source_id = uuid4()
    duty_id, task_id, output_id = uuid4(), uuid4(), uuid4()
    owned_documents.document_ids.add(document_id)

    async with open_postgres_consultant_runtime(_database_url()) as runtime:
        await runtime.create_document(document_id, title="resource publication")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=0,
            document=_oversized_task_document(
                document_id,
                duty_id=duty_id,
                task_id=task_id,
                output_id=output_id,
                evidence_source_id=direct_edit_source_id,
            ),
            source_id=direct_edit_source_id,
        )
        admitted, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=employee_source_id,
            text="請確認採購職務標題。",
        )
        assert should_process is True
        assert admitted.revision == seeded.revision + 1

        sources = await runtime.list_sources(document_id)
        catalog = WorkspaceCatalog.from_snapshot(
            admitted.approved_document,
            sources=sources,
        )
        files = project_candidate_files(catalog, run_id=run_id)
        header_path = f"/candidate/{run_id}/header.json"
        header = json.loads(files[header_path])
        header["job_title"] = "資深採購專員"
        files[header_path] = json.dumps(header, ensure_ascii=False, indent=2) + "\n"

        checked = await runtime.check_candidate_document(
            document_id=document_id,
            run_id=run_id,
            files=files,
            tool_call_id="resource-check-001",
        )
        assert checked.status == "checked", checked.issues
        after_check = await runtime.reopen_document(document_id)
        assert after_check.review_queue == {}
        raw_checked = await runtime.raw_state(document_id)
        assert raw_checked["checked_candidate"] is not None

        published = await runtime.publish_checked_candidate(
            document_id=document_id,
            run_id=run_id,
            files=files,
        )
        assert len(published.review_queue) == 1
        assert (await runtime.raw_state(document_id))["checked_candidate"] is None

        replayed = await runtime.publish_checked_candidate(
            document_id=document_id,
            run_id=run_id,
            files=files,
        )
        assert replayed.revision == published.revision
        assert replayed.review_queue == published.review_queue
