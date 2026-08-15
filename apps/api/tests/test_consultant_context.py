from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.runtime import Runtime

from app.adapters.langgraph.postgres import open_postgres_consultant_runtime
from app.consultant.candidate_workspace import (
    CandidateEditAction,
    CandidateToolReceipt,
    CandidateWorkspace,
    candidate_revision_digest,
)
from app.consultant.context import (
    ApprovedDocumentSlice,
    ContextRequest,
    ContextSelectionReason,
    ConsultantAgentRuntimeContext,
    ConsultantContextMiddleware,
    DocumentSourceLookup,
    GlobalOrientationIndex,
    SemanticSourceIndex,
    SourceLookupMode,
    _prompt,
    build_consultant_context,
    build_employee_source_tools,
)
from app.consultant.document_review import create_document_changeset
from app.consultant.model_runtime import (
    ConsultantModelProfile,
    RunPolicy,
    resolve_execution,
)
from app.consultant.results import (
    AnalysisBasis,
    DocumentChangeOperation,
    ReviewableDocumentChange,
)
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedTask,
    DocumentChangeSet,
    DocumentChangeStatus,
    DocumentPatchAction,
    DocumentPatchOperation,
    DocumentPathRead,
    EmployeeSource,
    EmployeeSourceKind,
    initial_thread_state,
)
from app.consultant.views import ConsultantSnapshot, snapshot_from_state


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL", "")
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(autouse=True)
async def cleanup_new_context_documents() -> AsyncIterator[None]:
    """Hard-delete only catalog rows created by this context test."""
    database_url = _database_url()
    if not database_url:
        yield
        return

    async def catalog_ids() -> set[UUID]:
        async with await psycopg.AsyncConnection.connect(
            database_url, autocommit=True
        ) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT to_regclass('public.consultant_documents')"
                )
                row = await cursor.fetchone()
                if row is None or row[0] is None:
                    return set()
                await cursor.execute("SELECT document_id FROM consultant_documents")
                return {row[0] for row in await cursor.fetchall()}

    before = await catalog_ids()
    yield
    created = await catalog_ids() - before
    if not created:
        return
    async with open_postgres_consultant_runtime(database_url) as runtime:
        for document_id in created:
            await runtime.delete_document(document_id)
    async with await psycopg.AsyncConnection.connect(
        database_url, autocommit=True
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.executemany(
                "DELETE FROM consultant_documents WHERE document_id = %s",
                [(document_id,) for document_id in created],
            )


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
                "employee_source_get",
                "employee_source_lineage",
                "employee_source_search",
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


def _context_source(document_id: UUID, source_id: UUID) -> EmployeeSource:
    return EmployeeSource.pending(
        source_id=source_id,
        document_id=document_id,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text="這是本輪員工原話。",
    )


class _ContextSourceRuntime:
    def __init__(self, source: EmployeeSource) -> None:
        self.source = source

    async def get_source(self, document_id: UUID, source_id: UUID) -> EmployeeSource:
        assert document_id == self.source.document_id
        assert source_id == self.source.source_id
        return self.source


def _context_action(
    *,
    action_id: UUID,
    source_id: UUID,
    target_id: UUID,
    status: DocumentChangeStatus = DocumentChangeStatus.PENDING,
    after: str = "候選內容",
    path: str | None = None,
    target_key: str | None = None,
    depends_on_action_ids: tuple[UUID, ...] = (),
    employee_after: str | None = None,
    rejection_reason: str | None = None,
    stale_reason: str | None = None,
) -> DocumentPatchAction:
    return DocumentPatchAction(
        action_id=action_id,
        operation=DocumentPatchOperation.REVISE,
        path=path or f"/tasks/{target_id}/statement",
        target_key=target_key or f"task:{target_id}:statement",
        before="原核准內容",
        after=after,
        source_ids=(source_id,),
        read_set=(
            DocumentPathRead(
                path=path or f"/tasks/{target_id}/statement",
                value_sha256=sha256(b"original").hexdigest(),
            ),
        ),
        target_ids=(target_id,),
        depends_on_action_ids=depends_on_action_ids,
        atomic_subgroup_id=uuid4(),
        status=status,
        employee_after=employee_after,
        rejection_reason=rejection_reason,
        stale_reason=stale_reason,
    )


def _context_changeset(
    *,
    changeset_id: UUID,
    created_revision: int,
    actions: tuple[DocumentPatchAction, ...],
) -> DocumentChangeSet:
    return DocumentChangeSet(
        changeset_id=changeset_id,
        summary="候選文件變更。",
        actions=actions,
        source_ids=tuple(
            sorted({source_id for action in actions for source_id in action.source_ids}, key=str)
        ),
        created_revision=created_revision,
    )


def _prompt_section(prompt: str, name: str) -> dict:
    start = prompt.index(f"<{name}")
    payload_start = prompt.index(">", start) + 1
    payload_end = prompt.index(f"</{name}>", payload_start)
    return json.loads(prompt[payload_start:payload_end])


def _empty_orientation(document_id: UUID) -> GlobalOrientationIndex:
    return GlobalOrientationIndex(
        document_id=document_id,
        state_revision=7,
        total_work_count=0,
        total_hypothesis_count=0,
        total_duty_count=0,
        total_task_count=0,
        gap_count=0,
        pending_review_count=0,
        omitted_work_count=0,
        omitted_hypothesis_count=0,
        omitted_duty_count=0,
        omitted_task_count=0,
    )


def _context_snapshot(
    *,
    document: ApprovedJobDocument,
    source_id: UUID,
    review_queue: dict[str, dict] | None = None,
    active_candidate: CandidateWorkspace | None = None,
) -> ConsultantSnapshot:
    state = initial_thread_state(document.document_id)
    state.update(
        {
            "revision": 7,
            "source_count": 1,
            "latest_source_id": str(source_id),
            "approved_document": document.model_dump(mode="json"),
            "review_queue": review_queue or {},
            "active_candidate": (
                active_candidate.model_dump(mode="json")
                if active_candidate is not None
                else None
            ),
        }
    )
    return snapshot_from_state(state)


def _active_workspace(
    *,
    run_id: UUID,
    changeset: DocumentChangeSet,
) -> CandidateWorkspace:
    digest = candidate_revision_digest(changeset)
    actions = tuple(
        CandidateEditAction(
            action_id=action.action_id,
            operation=action.operation,
            path=action.path,
            before=action.before,
            after=action.after,
            depends_on_action_ids=action.depends_on_action_ids,
            supersedes_action_ids=action.supersedes_action_ids,
            atomic_subgroup_id=action.atomic_subgroup_id,
            status=action.status,
            stale_reason=action.stale_reason,
        )
        for action in changeset.actions
    )
    receipt = CandidateToolReceipt(
        request_sha256="a" * 64,
        candidate_revision=1,
        revision_digest=digest,
        changeset_id=changeset.changeset_id,
        source_ids=changeset.source_ids,
        action_ids=tuple(action.action_id for action in changeset.actions),
        actions=actions,
    )
    return CandidateWorkspace(
        run_id=run_id,
        baseline_revision=7,
        candidate_revision=1,
        request_sha256="a" * 64,
        revision_digest=digest,
        used_skill_ids=("task-boundary",),
        changeset=changeset,
        tool_receipts={"candidate-call-1": receipt},
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
            review_bundle = create_document_changeset(
                document_id=document_id,
                run_id=uuid4(),
                summary="建議補充緊急缺料處理 Task。",
                read_revision=latest.revision,
                document=document,
                changes=(
                    ReviewableDocumentChange(
                        operation=DocumentChangeOperation.REVISE,
                        path=f"/tasks/{document.tasks[0].task_id}/statement",
                        after="辨識並追蹤緊急缺料",
                        basis=AnalysisBasis(
                            source_ids=(current_source_id,),
                            skill_ids=("task-boundary",),
                        ),
                    ),
                ),
                existing_review_queue={},
                interview_work={},
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
                        str(review_bundle.changeset_id): review_bundle.model_dump(
                            mode="json"
                        )
                    },
                    "required_clarification": {
                        "clarification_id": str(uuid4()),
                        "question": "緊急缺料時由誰決定通知業務？",
                        "reason": "員工說法與核准文件的責任邊界衝突",
                        "current_understanding": "目前可能由員工或主管決定。",
                        "choices": ["員工", "主管", "視情況"],
                        "affected_work_ids": [str(work_id)],
                        "affected_branch": "緊急缺料／通知責任",
                        "source_ids": [str(current_source_id)],
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
                            "name": "employee_source_get",
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
async def test_langchain_source_tools_are_document_scoped_and_expose_exact_evidence(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    other_document_id = uuid4()
    other_source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        try:
            await runtime.create_document(document_id, title="採購職務")
            await runtime.create_document(other_document_id, title="他份職務")
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=source_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="我每週整理採購需求。",
            )
            await runtime.record_employee_source(
                document_id=other_document_id,
                source_id=other_source_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="不應跨文件讀到。",
            )

            tools = {
                item.name: item
                for item in build_employee_source_tools(
                    DocumentSourceLookup(runtime),
                    document_id=document_id,
                )
            }
            exact = await tools["employee_source_get"].ainvoke(
                {"source_id": str(source_id)}
            )
            found = await tools["employee_source_search"].ainvoke(
                {"query": "採購需求"}
            )

            assert exact["source_id"] == str(source_id)
            assert exact["kind"] == "employee_turn"
            assert exact["speaker"] == "employee"
            assert exact["text"] == "我每週整理採購需求。"
            assert exact["validity"] == "current"
            assert exact["created_at"]
            assert exact["supersedes_source_id"] is None
            assert exact["superseded_by_source_id"] is None
            assert found == [exact]
            assert set(tools["employee_source_search"].args) == {"query"}
            with pytest.raises(KeyError):
                await tools["employee_source_get"].ainvoke(
                    {"source_id": str(other_source_id)}
                )
            assert set(tools) == {
                "employee_source_get",
                "employee_source_lineage",
                "employee_source_search",
            }
        finally:
            await runtime.delete_document(document_id)
            await runtime.delete_document(other_document_id)


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


def test_context_exposes_semantic_pending_overlay_and_employee_decision_memory() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document = _approved_document(document_id)
    task_id = document.tasks[0].task_id
    actions = (
        _context_action(
            action_id=UUID(int=1), source_id=source_id, target_id=task_id,
            after="待審候選內容",
        ),
        _context_action(
            action_id=UUID(int=2), source_id=source_id, target_id=task_id,
            status=DocumentChangeStatus.DEFERRED, after="暫緩候選內容",
        ),
        _context_action(
            action_id=UUID(int=3), source_id=source_id, target_id=task_id,
            status=DocumentChangeStatus.REJECTED, after="不得混入核准的拒絕內容",
            rejection_reason="這不是我的職責。",
        ),
        _context_action(
            action_id=UUID(int=4), source_id=source_id, target_id=task_id,
            status=DocumentChangeStatus.STALE, after="不得混入核准的失效內容",
            stale_reason="前置內容已變更。",
        ),
        _context_action(
            action_id=UUID(int=5), source_id=source_id, target_id=task_id,
            status=DocumentChangeStatus.EDIT_ACCEPTED, after="模型原本的候選內容",
            employee_after="員工修改後的核准內容",
        ),
    )
    changeset = _context_changeset(
        changeset_id=UUID(int=101), created_revision=6, actions=actions
    )
    approved = document.model_copy(update={"work_description": "員工修改後的核准內容"})
    source = _context_source(document_id, source_id)
    prompt = _prompt(
        orientation=_empty_orientation(document_id),
        approved_slice=ApprovedDocumentSlice(
            document_id=document_id,
            work_description=approved.work_description,
        ),
        current_work={"subject_id": str(task_id)},
        recent_consultant_turns=(),
        required_clarification=None,
        understanding={},
        gaps={},
        review_queue={str(changeset.changeset_id): changeset.model_dump(mode="json")},
        current_source=source,
        sources=(),
        lookup_handles=(),
        non_authoritative_dialogue_summary=None,
    )

    assert '<pending_document_overlay authority="candidate" approved="false">' in prompt
    assert '<document_decision_history authority="employee_decision" approved="false">' in prompt
    assert "pending content is only a conditional hypothesis" in prompt

    pending = _prompt_section(prompt, "pending_document_overlay")
    assert [item["status"] for item in pending["actions"]] == ["pending", "deferred"]
    assert pending["actions"][0] == {
        "changeset_id": str(changeset.changeset_id),
        "created_revision": 6,
        "action_id": str(actions[0].action_id),
        "operation": "revise",
        "path": f"/tasks/{task_id}/statement",
        "before": "原核准內容",
        "after": "待審候選內容",
        "source_ids": [str(source_id)],
        "depends_on_action_ids": [],
        "supersedes_action_ids": [],
        "atomic_subgroup_id": str(actions[0].atomic_subgroup_id),
        "status": "pending",
    }
    assert pending["omitted_count"] == {"pending": 0, "deferred": 0}

    history = _prompt_section(prompt, "document_decision_history")
    assert [item["status"] for item in history["actions"]] == [
        "rejected",
        "stale",
        "edit_accepted",
    ]
    assert history["actions"][0]["target_key"] == actions[2].target_key
    assert history["actions"][0]["rejection_reason"] == "這不是我的職責。"
    assert history["actions"][1]["stale_reason"] == "前置內容已變更。"
    assert history["actions"][2]["model_after"] == "模型原本的候選內容"
    assert history["actions"][2]["employee_after"] == "員工修改後的核准內容"
    assert history["omitted_count"] == {
        "rejected": 0,
        "stale": 0,
        "edit_accepted": 0,
    }
    approved_payload = _prompt_section(prompt, "approved_document_slice")
    assert approved_payload["work_description"] == "員工修改後的核准內容"
    assert "不得混入核准" not in json.dumps(approved_payload, ensure_ascii=False)


def test_context_overlay_has_deterministic_caps_and_dependency_closure() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document = _approved_document(document_id)
    focus_id = document.tasks[0].task_id
    unrelated_id = document.tasks[1].task_id
    pending_actions = tuple(
        _context_action(
            action_id=UUID(int=index + 1),
            source_id=source_id,
            target_id=focus_id if index == 13 else unrelated_id,
            depends_on_action_ids=(UUID(int=1),) if index == 13 else (),
            after=f"pending-{index}",
        )
        for index in range(14)
    )
    pending = _context_changeset(
        changeset_id=UUID(int=201), created_revision=4, actions=pending_actions
    )
    rejected = tuple(
        _context_action(
            action_id=UUID(int=301 + index), source_id=source_id,
            target_id=unrelated_id, status=DocumentChangeStatus.REJECTED,
            after=f"rejected-{index}", rejection_reason="員工拒絕。",
        )
        for index in range(9)
    )
    history_bundles = {
        str(UUID(int=400 + index)): _context_changeset(
            changeset_id=UUID(int=400 + index), created_revision=index,
            actions=(action,),
        ).model_dump(mode="json")
        for index, action in enumerate(rejected)
    }
    queue = {
        str(pending.changeset_id): pending.model_dump(mode="json"),
        **history_bundles,
    }
    source = _context_source(document_id, source_id)

    def render(review_queue: dict[str, dict]) -> str:
        return _prompt(
            orientation=_empty_orientation(document_id),
            approved_slice=ApprovedDocumentSlice(
                document_id=document_id, tasks=(document.tasks[0],)
            ),
            current_work={"subject_id": str(focus_id)},
            recent_consultant_turns=(), required_clarification=None,
            understanding={}, gaps={}, review_queue=review_queue,
            current_source=source, sources=(), lookup_handles=(),
            non_authoritative_dialogue_summary=None,
        )

    first_pending = _prompt_section(render(queue), "pending_document_overlay")
    reversed_queue = dict(reversed(tuple(queue.items())))
    second_pending = _prompt_section(render(reversed_queue), "pending_document_overlay")
    assert first_pending == second_pending
    assert len(first_pending["actions"]) == 12
    assert str(UUID(int=14)) in {item["action_id"] for item in first_pending["actions"]}
    assert str(UUID(int=1)) in {item["action_id"] for item in first_pending["actions"]}
    assert first_pending["omitted_count"] == {"pending": 2, "deferred": 0}

    history = _prompt_section(render(queue), "document_decision_history")
    assert [item["action_id"] for item in history["actions"]] == [
        str(UUID(int=value)) for value in range(302, 310)
    ]
    assert history["omitted_count"] == {
        "rejected": 1,
        "stale": 0,
        "edit_accepted": 0,
    }


def test_context_keeps_nine_employee_accepted_tasks_separate_from_rejected_output() -> None:
    document_id = uuid4()
    source_id = uuid4()
    duty_id = uuid4()
    accepted_tasks = tuple(
        ApprovedTask(
            task_id=uuid4(),
            duty_id=duty_id,
            statement=f"員工接受的工作 {index}",
            action="完成",
            object=f"工作 {index}",
            purpose_result="交付結果",
            display_order=index,
        )
        for index in range(9)
    )
    document = ApprovedJobDocument(
        document_id=document_id,
        job_title="九項已接受工作",
        duties=(ApprovedDuty(duty_id=duty_id, statement="主要職責", display_order=0),),
        tasks=accepted_tasks,
    )
    rejected_output = _context_action(
        action_id=UUID(int=601),
        source_id=source_id,
        target_id=accepted_tasks[0].task_id,
        path="/opks",
        target_key=f"opks:output:{accepted_tasks[0].task_id}",
        status=DocumentChangeStatus.REJECTED,
        after="模型重提的錯誤 O",
        rejection_reason="這不是本職務的產出。",
    )
    changeset = _context_changeset(
        changeset_id=UUID(int=602),
        created_revision=8,
        actions=(rejected_output,),
    )
    prompt = _prompt(
        orientation=_empty_orientation(document_id),
        approved_slice=ApprovedDocumentSlice(
            document_id=document_id,
            duties=(document.duties[0],),
            tasks=accepted_tasks,
        ),
        current_work={"subject_id": str(accepted_tasks[0].task_id)},
        recent_consultant_turns=(), required_clarification=None,
        understanding={}, gaps={},
        review_queue={str(changeset.changeset_id): changeset.model_dump(mode="json")},
        current_source=_context_source(document_id, source_id),
        sources=(), lookup_handles=(), non_authoritative_dialogue_summary=None,
    )

    approved = _prompt_section(prompt, "approved_document_slice")
    assert [task["statement"] for task in approved["tasks"]] == [
        f"員工接受的工作 {index}" for index in range(9)
    ]
    assert "模型重提的錯誤 O" not in json.dumps(approved, ensure_ascii=False)
    pending = _prompt_section(prompt, "pending_document_overlay")
    assert pending["actions"] == []
    history = _prompt_section(prompt, "document_decision_history")
    assert history["actions"] == [
        {
            "changeset_id": str(changeset.changeset_id),
            "created_revision": 8,
            "action_id": str(rejected_output.action_id),
            "status": "rejected",
            "target_key": rejected_output.target_key,
            "rejection_reason": "這不是本職務的產出。",
        }
    ]


@pytest.mark.asyncio
async def test_same_run_retry_sees_active_candidate_without_changing_progress() -> None:
    document_id = uuid4()
    source_id = uuid4()
    run_id = uuid4()
    document = _approved_document(document_id)
    changeset = _context_changeset(
        changeset_id=uuid4(),
        created_revision=7,
        actions=(
            _context_action(
                action_id=uuid4(), source_id=source_id,
                target_id=document.tasks[0].task_id, after="同一 run 可修正的候選",
            ),
        ),
    )
    snapshot = _context_snapshot(
        document=document,
        source_id=source_id,
        active_candidate=_active_workspace(run_id=run_id, changeset=changeset),
    )
    runtime = _ContextSourceRuntime(_context_source(document_id, source_id))
    before = snapshot.semantic_progress
    same_run = await build_consultant_context(
        runtime=runtime,
        snapshot=snapshot,
        execution=_execution(),
        request=ContextRequest(
            run_id=run_id,
            current_source_id=source_id,
            selected_skill_ids=("task-boundary",),
        ),
    )
    assert '<active_candidate_workspace authority="none" approved="false">' in same_run.system_prompt
    active = _prompt_section(same_run.system_prompt, "active_candidate_workspace")
    assert active["candidate_revision"] == 1
    assert active["revision_digest"] == snapshot.active_candidate.revision_digest
    assert active["actions"][0]["source_ids"] == [str(source_id)]
    assert snapshot.semantic_progress == before
    assert snapshot.semantic_progress.employee_decisions.pending == 0

    new_run = await build_consultant_context(
        runtime=runtime,
        snapshot=snapshot,
        execution=_execution(),
        request=ContextRequest(
            run_id=uuid4(),
            current_source_id=source_id,
            selected_skill_ids=("task-boundary",),
        ),
    )
    assert "<active_candidate_workspace" not in new_run.system_prompt
