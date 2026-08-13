from __future__ import annotations

import json
import os
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.runtime import Runtime

from app.adapters.langgraph.postgres import open_postgres_consultant_runtime
from app.consultant.context import (
    ContextRequest,
    ContextSelectionReason,
    ConsultantAgentRuntimeContext,
    ConsultantContextMiddleware,
    DocumentSourceLookup,
    SemanticSourceIndex,
    SourceLookupMode,
    build_consultant_context,
)
from app.consultant.model_runtime import (
    ConsultantModelProfile,
    RunPolicy,
    resolve_execution,
)
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedTask,
    EmployeeSourceKind,
)
from app.consultant.views import ConsultantSnapshot


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL", "")
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest.fixture
def consultant_database_url() -> str:
    value = _database_url()
    if not value:
        pytest.skip("TEST_DATABASE_URL not set; consultant PostgreSQL test skipped")
    return value


def _execution(*, max_context_tokens: int = 24_000):
    return resolve_execution(
        ConsultantModelProfile(
            profile_id="primary-consultant",
            revision=3,
            requested_model="anthropic/claude-opus-5",
            provider_allowlist=("Anthropic",),
            max_output_tokens=4096,
        ),
        RunPolicy(
            policy_id="interactive-consultation",
            revision=4,
            run_kind="interactive_consultation",
            allowed_skill_ids=("task-boundary", "duty-grouping", "knowledge"),
            allowed_tool_ids=(
                "source_by_id",
                "source_lineage",
                "source_lexical_search",
            ),
            max_context_tokens=max_context_tokens,
            max_model_calls=3,
            max_lookup_waves=2,
            max_total_tool_calls=12,
            model_retry_count=1,
            tool_retry_count=1,
            max_elapsed_seconds=180,
            max_total_tokens=32_000,
            max_cost_usd=Decimal("2.00"),
        ),
    )


def _approved_document(document_id: UUID) -> ApprovedJobDocument:
    purchasing = uuid4()
    reporting = uuid4()
    shortage_task = uuid4()
    report_task = uuid4()
    return ApprovedJobDocument(
        document_id=document_id,
        job_title="採購管理專員",
        work_description="管理物料供應並彙整採購資訊",
        duties=(
            ApprovedDuty(
                duty_id=purchasing,
                statement="物料供應管理",
                display_order=0,
            ),
            ApprovedDuty(
                duty_id=reporting,
                statement="採購資訊彙整",
                display_order=1,
            ),
        ),
        tasks=(
            ApprovedTask(
                task_id=shortage_task,
                duty_id=purchasing,
                statement="檢查缺料並安排採購",
                action="檢查並安排",
                object="缺料與採購",
                purpose_result="確保物料按期供應",
                display_order=0,
            ),
            ApprovedTask(
                task_id=report_task,
                duty_id=reporting,
                statement="彙整每月採購差異",
                action="彙整",
                object="採購差異",
                purpose_result="提供月度追蹤資訊",
                display_order=1,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_main_context_has_global_orientation_focus_and_exact_current_sources(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    direct_edit_id = uuid4()
    old_source_id = uuid4()
    correction_id = uuid4()
    unrelated_old_id = uuid4()
    unrelated_correction_id = uuid4()
    current_source_id = uuid4()
    work_id = uuid4()
    document = _approved_document(document_id)

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        try:
            initial = await runtime.create_document(document_id, title="採購職務")
            approved = await runtime.apply_direct_edit(
                document_id=document_id,
                expected_revision=initial.revision,
                document=document,
                source_id=direct_edit_id,
            )
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=old_source_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="我每週整理採購需求。",
            )
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=correction_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="更正：其實我是每天整理採購需求。",
                supersedes_source_id=old_source_id,
            )
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=unrelated_old_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="供應商窗口原本叫王先生。",
            )
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=unrelated_correction_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="更正：供應商窗口改由李小姐負責。",
                supersedes_source_id=unrelated_old_id,
            )
            latest = await runtime.record_employee_source(
                document_id=document_id,
                source_id=current_source_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="  我還會追蹤緊急缺料，必要時通知業務。\n",
            )
            snapshot = ConsultantSnapshot.model_validate(
                {
                    **latest.model_dump(mode="json"),
                    "interview_work": {
                        str(work_id): {
                            "work_id": str(work_id),
                            "kind": "task_deepening",
                            "subject_id": str(document.tasks[0].task_id),
                            "status": "active",
                            "priority_reason": "缺料處理仍缺少決策條件",
                            "source_ids": [str(current_source_id)],
                        }
                    },
                    "understanding": {
                        "u-1": {
                            "text": "員工負責辨識並追蹤緊急缺料",
                            "source_ids": [str(current_source_id)],
                        },
                        "u-old": {
                            "text": "過時理解：員工只負責例行採購",
                            "status": "superseded",
                            "source_ids": [str(old_source_id)],
                        },
                    },
                    "gaps": {
                        "g-1": {
                            "kind": "condition_missing",
                            "summary": "尚不清楚何時需要通知業務",
                            "blocking": False,
                            "source_ids": [str(current_source_id)],
                        }
                    },
                    "review_queue": {
                        "c-1": {
                            "status": "pending",
                            "summary": "建議補充緊急缺料處理 Task",
                        }
                    },
                    "required_clarification": {
                        "clarification_id": str(uuid4()),
                        "question": "緊急缺料時由誰決定通知業務？",
                        "reason": "員工說法與核准文件的責任邊界衝突",
                        "affected_work_ids": [str(work_id)],
                    },
                    "messages": [
                        {
                            "run_id": str(uuid4()),
                            "answer_source_id": str(correction_id),
                            "text": "我先確認缺料通知的責任邊界。",
                            "used_skill_ids": ["task-boundary"],
                            "next_question": {
                                "text": "緊急缺料時，誰決定要通知業務？",
                                "answer_target": "缺料通知責任",
                                "reason": "釐清本人責任。",
                                "basis": {
                                    "source_ids": [str(correction_id)],
                                    "skill_ids": ["task-boundary"],
                                    "quote_anchors": [],
                                },
                            },
                        }
                    ],
                }
            )
            bundle = await build_consultant_context(
                runtime=runtime,
                snapshot=snapshot,
                execution=_execution(),
                request=ContextRequest(
                    run_id=uuid4(),
                    current_source_id=current_source_id,
                    current_work_id=work_id,
                    focus_subject_id=document.tasks[0].task_id,
                    required_source_ids=(correction_id,),
                    recent_source_ids=(old_source_id,),
                    selected_skill_ids=("task-boundary", "duty-grouping"),
                    non_authoritative_dialogue_summary="舊摘要誤寫成每週整理。",
                ),
            )

            assert bundle.orientation.document_id == document_id
            assert {item.item_id for item in bundle.orientation.work_items} == {
                work_id
            }
            assert {item.item_id for item in bundle.orientation.tasks} == {
                task.task_id for task in document.tasks
            }
            assert bundle.approved_document_slice.tasks[0].task_id == document.tasks[0].task_id
            assert "尚不清楚何時需要通知業務" in bundle.system_prompt
            assert "緊急缺料時由誰決定通知業務？" in bundle.system_prompt
            assert "更正：其實我是每天整理採購需求。" in bundle.system_prompt
            assert "我每週整理採購需求。" not in bundle.system_prompt
            assert "供應商窗口改由李小姐負責。" not in bundle.system_prompt
            assert str(unrelated_correction_id) not in bundle.system_prompt
            assert "舊摘要誤寫成每週整理。" in bundle.system_prompt
            assert "過時理解：員工只負責例行採購" not in bundle.system_prompt
            assert "我先確認缺料通知的責任邊界。" in bundle.system_prompt
            assert "緊急缺料時，誰決定要通知業務？" in bundle.system_prompt
            assert "non_authoritative_dialogue_summary" not in (
                bundle.receipt.degraded_sections
            )
            assert isinstance(bundle.messages[-1], HumanMessage)
            assert bundle.messages[-1].content == (
                f"[employee source {current_source_id}]"
            )
            assert bundle.system_prompt.count("我還會追蹤緊急缺料，必要時通知業務。") == 1
            assert str(current_source_id) in bundle.system_prompt
            assert str(correction_id) in bundle.system_prompt
            assert bundle.receipt.selected_skill_ids == (
                "task-boundary",
                "duty-grouping",
            )
            assert bundle.receipt.total_input_tokens <= 24_000
            assert old_source_id in {
                item.source_id
                for item in bundle.receipt.omitted_sources
                if item.reason is ContextSelectionReason.SUPERSEDED
            }
            assert unrelated_correction_id not in {
                item.source_id for item in bundle.receipt.loaded_sources
            }
            receipt_json = bundle.receipt.model_dump_json()
            assert "每天整理採購需求" not in receipt_json
            assert "緊急缺料" not in receipt_json
            assert approved.revision < snapshot.revision
        finally:
            await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_context_middleware_rebinds_tagged_source_without_reordering_tool_loop(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        try:
            initial = await runtime.create_document(document_id, title="採購職務")
            edited = await runtime.apply_direct_edit(
                document_id=document_id,
                expected_revision=initial.revision,
                document=_approved_document(document_id),
                source_id=uuid4(),
            )
            latest = await runtime.record_employee_source(
                document_id=document_id,
                source_id=source_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="這是必須從 Store 重載的完整員工原話。",
            )
            execution = _execution()
            runtime_context = ConsultantAgentRuntimeContext(
                runtime=runtime,
                snapshot=latest,
                execution=execution,
                request=ContextRequest(
                    run_id=uuid4(),
                    current_source_id=source_id,
                    selected_skill_ids=("task-boundary",),
                ),
            )
            messages = [
                HumanMessage(
                    content="摘要或 state 中被改壞的副本",
                    additional_kwargs={"employee_source_id": str(source_id)},
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "source_by_id",
                            "args": {"source_id": str(source_id)},
                            "id": "lookup-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(content="唯讀工具結果", tool_call_id="lookup-1"),
            ]
            request = ModelRequest(
                model=FakeMessagesListChatModel(
                    responses=[AIMessage(content="完成")]
                ),
                messages=messages,
                system_message=SystemMessage(
                    content="非權威摘要可以保留，但不能取代來源。"
                ),
                runtime=Runtime(context=runtime_context),
            )
            captured: dict[str, ModelRequest] = {}

            async def handler(overridden: ModelRequest) -> ModelResponse:
                captured["request"] = overridden
                return ModelResponse(result=[AIMessage(content="完成")])

            await ConsultantContextMiddleware().awrap_model_call(request, handler)

            actual = captured["request"]
            assert actual.messages[0].content == f"[employee source {source_id}]"
            assert isinstance(actual.messages[-1], ToolMessage)
            assert actual.messages[-1].content == "唯讀工具結果"
            assert sum(
                message.content == "這是必須從 Store 重載的完整員工原話。"
                for message in actual.messages
            ) == 0
            assert "<exact_employee_sources>" in actual.system_message.text
            assert actual.system_message.text.count(
                "這是必須從 Store 重載的完整員工原話。"
            ) == 1
            assert len(runtime_context.context_receipts) == 1

            summarized_request = ModelRequest(
                model=request.model,
                messages=[
                    AIMessage(
                        content="先前對話已被非權威摘要取代",
                        additional_kwargs={"lc_source": "summarization"},
                    ),
                    ToolMessage(content="摘要後的唯讀工具結果", tool_call_id="lookup-1"),
                ],
                system_message=request.system_message,
                runtime=request.runtime,
            )
            await ConsultantContextMiddleware().awrap_model_call(
                summarized_request, handler
            )
            after_summary = captured["request"]
            assert isinstance(after_summary.messages[-1], ToolMessage)
            assert after_summary.system_message.text.count(
                "這是必須從 Store 重載的完整員工原話。"
            ) == 1
            assert len(runtime_context.context_receipts) == 2
            assert edited.revision < latest.revision
        finally:
            await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_source_lookup_prefers_id_and_lineage_then_current_lexical_results(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    old_source_id = uuid4()
    correction_id = uuid4()
    unrelated_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        try:
            await runtime.create_document(document_id, title="採購職務")
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=old_source_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="我每週整理採購需求。",
            )
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=correction_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="更正：每天整理採購需求。",
                supersedes_source_id=old_source_id,
            )
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=unrelated_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="月底彙整供應商請款資料。",
            )
            lookup = DocumentSourceLookup(runtime)

            exact = await lookup.by_id(document_id, old_source_id)
            lineage = await lookup.lineage(document_id, correction_id)
            current = await lookup.search(
                document_id,
                query="整理採購需求",
                mode=SourceLookupMode.LEXICAL,
                limit=5,
            )

            assert exact.source_id == old_source_id
            assert [item.source_id for item in lineage] == [
                old_source_id,
                correction_id,
            ]
            assert [item.source_id for item in current] == [correction_id]
            assert all(item.document_id == document_id for item in current)
        finally:
            await runtime.delete_document(document_id)


class FakeSemanticIndex(SemanticSourceIndex):
    def __init__(self, source_ids: tuple[UUID, ...]) -> None:
        self.source_ids = source_ids
        self.calls: list[tuple[UUID, str, int]] = []

    async def search_source_ids(
        self, document_id: UUID, query: str, *, limit: int
    ) -> tuple[UUID, ...]:
        self.calls.append((document_id, query, limit))
        return self.source_ids[:limit]


@pytest.mark.asyncio
async def test_optional_semantic_index_stays_document_scoped_and_is_not_rag(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        try:
            await runtime.create_document(document_id, title="採購職務")
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=source_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="供應延誤時我會通知業務協調交期。",
            )
            semantic = FakeSemanticIndex((source_id,))
            lookup = DocumentSourceLookup(runtime, semantic_index=semantic)

            found = await lookup.search(
                document_id,
                query="缺料造成交期風險",
                mode=SourceLookupMode.SEMANTIC,
                limit=3,
            )

            assert [item.source_id for item in found] == [source_id]
            assert semantic.calls == [(document_id, "缺料造成交期風險", 3)]
            assert runtime.source_namespace(document_id) == (
                "caliburn",
                "consultant",
                str(document_id),
                "sources",
            )
        finally:
            await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_context_degrades_orientation_explicitly_without_dropping_current_input(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    duties = tuple(
        ApprovedDuty(duty_id=uuid4(), statement=f"責任區域 {index}", display_order=index)
        for index in range(30)
    )
    tasks = tuple(
        ApprovedTask(
            task_id=uuid4(),
            duty_id=duties[index].duty_id,
            statement=f"處理工作項目 {index} 並完成追蹤",
            action="處理並追蹤",
            object=f"工作項目 {index}",
            purpose_result="確保工作完成",
            display_order=index,
        )
        for index in range(30)
    )
    document = ApprovedJobDocument(
        document_id=document_id,
        job_title="大量工作測試",
        duties=duties,
        tasks=tasks,
    )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        try:
            initial = await runtime.create_document(document_id, title="大量工作")
            edited = await runtime.apply_direct_edit(
                document_id=document_id,
                expected_revision=initial.revision,
                document=document,
                source_id=uuid4(),
            )
            latest = await runtime.record_employee_source(
                document_id=document_id,
                source_id=source_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="本輪一定不能被裁掉的完整員工回答。",
            )
            bundle = await build_consultant_context(
                runtime=runtime,
                snapshot=latest,
                execution=_execution(max_context_tokens=1_800),
                request=ContextRequest(
                    run_id=uuid4(),
                    current_source_id=source_id,
                    focus_subject_id=tasks[0].task_id,
                    selected_skill_ids=("task-boundary",),
                ),
            )

            assert bundle.messages[-1].content == f"[employee source {source_id}]"
            assert "本輪一定不能被裁掉的完整員工回答。" in bundle.system_prompt
            assert bundle.orientation.total_task_count == 30
            assert len(bundle.orientation.tasks) < 30
            assert "global_orientation" in bundle.receipt.degraded_sections
            assert bundle.receipt.total_input_tokens <= 1_800
            assert edited.revision < latest.revision
        finally:
            await runtime.delete_document(document_id)
