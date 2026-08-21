from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import TypedDict
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from langgraph.graph import END, START, StateGraph

from app.adapters.langgraph.postgres import (
    DocumentNotFound,
    IdempotencyConflict,
    PendingSourceRequiresReconciliation,
    SourceConflict,
    open_postgres_consultant_runtime,
)
from app.consultant.candidate_publication import CandidatePublicationStale
from app.consultant.interview import VerifiedConsultantCommit
from app.consultant.results import (
    AnalysisBasis,
    AttentionChange,
    AttentionOperation,
    ConsultantResult,
    GapReason,
    SufficiencyRecommendation,
    UnderstandingChange,
    UnderstandingOperation,
)
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedTask,
    CommandReceipt,
    EmployeeSource,
    EmployeeSourceKind,
    InterviewPriority,
    RunExecutionEvidence,
    RunStatus,
    SourceProcessingStatus,
    SourceValidity,
)
from app.consultant.workspace_resources import WorkspaceCatalog, project_candidate_files
from app.consultant.workspace_tools import _serialize_check_result


def _database_url() -> str:
    return os.getenv("TEST_DATABASE_URL", "").replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


@pytest_asyncio.fixture(autouse=True)
async def cleanup_new_consultant_documents() -> AsyncIterator[None]:
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


def _document(document_id: UUID, *, suffix: str = "") -> ApprovedJobDocument:
    duty_id = uuid4()
    task_id = uuid4()
    return ApprovedJobDocument(
        document_id=document_id,
        job_title=f"採購管理專員{suffix}",
        work_description=f"負責缺料檢查與採購安排{suffix}",
        duties=(
            ApprovedDuty(
                duty_id=duty_id,
                statement="物料供應管理",
                display_order=0,
            ),
        ),
        tasks=(
            ApprovedTask(
                task_id=task_id,
                duty_id=duty_id,
                statement="檢查缺料並安排採購",
                action="檢查並安排",
                object="缺料與採購",
                purpose_result="確保物料按期供應",
                display_order=0,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_catalog_and_source_admission_are_durable_and_idempotent(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="採購職務")
        replayed_create = await runtime.create_document(document_id, title="採購職務")
        assert replayed_create == created
        with pytest.raises(IdempotencyConflict):
            await runtime.create_document(document_id, title="不同標題")

        admitted, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我每天整理採購需求。",
        )
        replay, replay_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我每天整理採購需求。",
        )
        assert should_process is True
        assert replay_process is False
        assert replay.revision == admitted.revision
        assert admitted.latest_run is not None
        assert admitted.latest_run["status"] == RunStatus.SOURCE_SAVED.value


@pytest.mark.asyncio
async def test_source_is_immutable_and_correction_supersedes_without_quote_copy(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    original_id = uuid4()
    correction_id = uuid4()
    original_text = "我每週一整理採購需求。"
    correction_text = "更正：我是每天整理採購需求。"

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        first = await runtime.record_employee_source(
            document_id=document_id,
            source_id=original_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text=original_text,
        )
        replay = await runtime.record_employee_source(
            document_id=document_id,
            source_id=original_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text=original_text,
        )
        assert replay.revision == first.revision
        with pytest.raises(SourceConflict):
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=original_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="同一 ID 不得換成別的內容",
            )

        corrected = await runtime.record_employee_source(
            document_id=document_id,
            source_id=correction_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text=correction_text,
            supersedes_source_id=original_id,
        )
        original = await runtime.get_source(document_id, original_id)
        current = await runtime.get_source(document_id, correction_id)
        assert corrected.revision == first.revision + 1
        assert original.validity is SourceValidity.SUPERSEDED
        assert current.validity is SourceValidity.CURRENT
        assert original.text == original_text
        assert correction_text not in json.dumps(
            await runtime.raw_state(document_id), ensure_ascii=False, default=str
        )


@pytest.mark.asyncio
async def test_direct_edit_is_authority_idempotent_and_exports_the_approved_document(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    first_source_id = uuid4()
    second_source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")
        first_document = _document(document_id)
        first = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=first_document,
            source_id=first_source_id,
        )
        revised = first_document.model_copy(
            update={"work_description": "負責缺料預警與緊急採購協調"}
        )
        second = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=first.revision,
            document=revised,
            source_id=second_source_id,
        )
        replay = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=first.revision,
            document=revised,
            source_id=second_source_id,
        )
        assert second.revision == first.revision + 1
        assert replay.revision == second.revision
        assert (await runtime.export_approved_document(document_id)) == revised
        direct_source = await runtime.get_source(document_id, second_source_id)
        assert direct_source.kind is EmployeeSourceKind.DIRECT_EDIT
        assert direct_source.text == revised.work_description


@pytest.mark.asyncio
async def test_verified_consultant_commit_survives_postgres_runtime_restart(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    run_id = uuid4()
    now = datetime.now(UTC)
    basis = AnalysisBasis(source_ids=(source_id,), skill_ids=("work-discovery",))
    result = ConsultantResult(
        visible_reply="我先整理出請購下單，接著釐清觸發條件。",
        reply_basis=basis,
        used_skill_ids=("work-discovery",),
        understanding_changes=(
            UnderstandingChange(
                operation=UnderstandingOperation.ADD,
                kind="task_hypothesis",
                text="員工依缺料狀況建立請購單。",
                basis=basis,
            ),
        ),
        attention_changes=(
            AttentionChange(
                operation=AttentionOperation.ADD,
                kind="task_boundary",
                title="請購下單",
                reason="需要釐清完成標準。",
                priority=InterviewPriority.TASK_BOUNDARY,
                make_current=True,
                basis=basis,
            ),
        ),
        sufficiency=SufficiencyRecommendation(
            currently_enough=False,
            reason="其他例行工作尚未盤點。",
            remaining_gap_reasons=(GapReason.WORK_COVERAGE_MISSING,),
            continuing_benefit="繼續盤點可避免漏掉例行工作。",
            basis=basis,
        ),
    )
    commit = VerifiedConsultantCommit(
        run_id=run_id,
        answer_source_id=source_id,
        started_at=now,
        completed_at=now,
        execution_evidence=RunExecutionEvidence(
            resolved_execution={
                "profile_id": "primary-consultant",
                "requested_model": "anthropic/claude-opus-5",
            },
        ),
        result=result,
    )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="採購職務")
        sourced = await runtime.record_employee_source(
            document_id=document_id,
            source_id=source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="我會先看缺料，再建立請購單。",
        )
        committed = await runtime.commit_verified_consultant_result(
            document_id=document_id,
            expected_revision=sourced.revision,
            commit=commit,
        )
        assert committed.revision == created.revision + 2

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        reopened = await runtime.reopen_document(document_id)
        assert reopened.revision == committed.revision
        assert reopened.messages[0].text == result.visible_reply
        assert reopened.latest_run is not None
        assert reopened.latest_run["execution_evidence"]["resolved_execution"][
            "requested_model"
        ] == "anthropic/claude-opus-5"


@pytest.mark.asyncio
async def test_authority_command_idempotency_is_payload_bound(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    command = CommandReceipt(
        command_id=uuid4(),
        command_kind="direct_document_edit",
        payload_sha256="a" * 64,
    )
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")
        edited = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=initial.approved_document.model_copy(update={"job_title": "採購專員"}),
            source_id=source_id,
            command_receipt=command,
        )
        replay = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=initial.approved_document.model_copy(update={"job_title": "採購專員"}),
            source_id=source_id,
            command_receipt=command,
        )
        assert replay.revision == edited.revision
        with pytest.raises(IdempotencyConflict):
            await runtime.apply_direct_edit(
                document_id=document_id,
                expected_revision=edited.revision,
                document=initial.approved_document.model_copy(update={"job_title": "採購管理師"}),
                source_id=source_id,
                command_receipt=command.model_copy(update={"payload_sha256": "b" * 64}),
            )


@pytest.mark.asyncio
async def test_workspace_check_only_records_receipt_then_publishes_once_and_replays(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    answer_source_id = uuid4()
    direct_edit_source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="候選職務")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=direct_edit_source_id,
        )
        admitted, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=answer_source_id,
            text="請檢查職務標題。",
        )
        assert should_process is True
        assert admitted.revision == seeded.revision + 1

        snapshot = await runtime.reopen_document(document_id)
        sources = await runtime.list_sources(document_id)
        catalog = WorkspaceCatalog.from_snapshot(
            snapshot.approved_document,
            sources=sources,
        )
        files = project_candidate_files(catalog, run_id=run_id)
        header_path = f"/candidate/{run_id}/header.json"
        header = json.loads(files[header_path])
        header["job_title"] = "資深採購管理專員"
        files[header_path] = json.dumps(header, ensure_ascii=False, indent=2) + "\n"

        checked = await runtime.check_candidate_document(
            document_id=document_id,
            run_id=run_id,
            files=files,
            tool_call_id="check-task6-001",
            selected_skill_ids=("output",),
            loaded_skill_ids=("output",),
        )
        assert checked.status == "checked"
        assert checked.receipt is not None
        assert (await runtime.reopen_document(document_id)).review_queue == {}
        checked_state = await runtime.raw_state(document_id)
        assert checked_state["checked_candidate"] is not None

        replayed_check = await runtime.check_candidate_document(
            document_id=document_id,
            run_id=run_id,
            files=files,
            tool_call_id="check-task6-001",
            selected_skill_ids=("output",),
            loaded_skill_ids=("output",),
        )
        assert replayed_check.status == "checked"
        assert replayed_check.resource_digest == checked.resource_digest
        assert replayed_check.action_handles == checked.action_handles
        assert replayed_check.actions == checked.actions
        assert replayed_check.review_queue == {}
        replayed_observation = _serialize_check_result(replayed_check)
        assert '"action_handles"' in replayed_observation
        assert "receipt" not in replayed_observation
        assert replayed_check.receipt == checked.receipt
        assert await runtime.raw_state(document_id) == checked_state

        published = await runtime.publish_checked_candidate(
            document_id=document_id,
            run_id=run_id,
            files=files,
        )
        assert len(published.review_queue) == 1
        published_state = await runtime.raw_state(document_id)
        assert published_state["checked_candidate"] is None
        publication_receipts = [
            receipt
            for receipt in published_state["command_receipts"].values()
            if receipt["command_kind"] == "publish_checked_candidate"
        ]
        assert len(publication_receipts) == 1

        replay = await runtime.publish_checked_candidate(
            document_id=document_id,
            run_id=run_id,
            files=files,
        )
        replay_state = await runtime.raw_state(document_id)
        assert replay.revision == published.revision
        assert replay.review_queue == published.review_queue
        assert replay_state["command_receipts"] == published_state["command_receipts"]


@pytest.mark.asyncio
async def test_workspace_publication_rejects_changed_files_without_queue_mutation(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="候選職務")
        await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=uuid4(),
            text="請檢查職務標題。",
        )
        snapshot = await runtime.reopen_document(document_id)
        catalog = WorkspaceCatalog.from_snapshot(
            snapshot.approved_document,
            sources=await runtime.list_sources(document_id),
        )
        files = project_candidate_files(catalog, run_id=run_id)
        header_path = f"/candidate/{run_id}/header.json"
        header = json.loads(files[header_path])
        header["job_title"] = "已檢查的標題"
        files[header_path] = json.dumps(header, ensure_ascii=False, indent=2) + "\n"
        check = await runtime.check_candidate_document(
            document_id=document_id,
            run_id=run_id,
            files=files,
            tool_call_id="check-task6-002",
            selected_skill_ids=("output",),
            loaded_skill_ids=("output",),
        )
        assert check.status == "checked"
        changed = dict(files)
        header = json.loads(changed[header_path])
        header["job_title"] = "未經重新檢查的標題"
        changed[header_path] = json.dumps(header, ensure_ascii=False, indent=2) + "\n"
        with pytest.raises(CandidatePublicationStale):
            await runtime.publish_checked_candidate(
                document_id=document_id,
                run_id=run_id,
                files=changed,
            )
        assert (await runtime.reopen_document(document_id)).review_queue == {}
        assert (await runtime.raw_state(document_id))["checked_candidate"] is not None


@pytest.mark.asyncio
async def test_setup_serializer_and_checkpoint_schema_are_strict(
    consultant_database_url: str,
) -> None:
    class UnsafeValue:
        pass

    class UnsafeState(TypedDict, total=False):
        payload: object

    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.setup()
        await runtime.setup()
        assert runtime.connection_invariants() == {
            "saver_autocommit": True,
            "saver_dict_rows": True,
            "store_autocommit": True,
            "store_dict_rows": True,
            "strict_msgpack": True,
        }
        builder = StateGraph(UnsafeState)
        builder.add_node("persist", lambda state: state)
        builder.add_edge(START, "persist")
        builder.add_edge("persist", END)
        graph = builder.compile(checkpointer=runtime.saver)
        with pytest.raises(TypeError, match="not msgpack serializable"):
            await graph.ainvoke({"payload": UnsafeValue()}, config)
        await runtime.saver.adelete_thread(thread_id)


@pytest.mark.asyncio
async def test_pending_source_requires_reconciliation_after_store_failure(
    consultant_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")

        async def fail_after_store(_source: EmployeeSource) -> None:
            raise RuntimeError("after-store")

        monkeypatch.setattr(runtime, "_after_source_store", fail_after_store)
        with pytest.raises(RuntimeError, match="after-store"):
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=source_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="先保存再分析",
            )
        pending = await runtime.get_source(document_id, source_id)
        assert pending.processing_status is SourceProcessingStatus.PENDING
        assert (await runtime.reopen_document(document_id)).source_count == 0
        with pytest.raises(PendingSourceRequiresReconciliation):
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=uuid4(),
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="不能跳過 pending input",
            )

        monkeypatch.setattr(runtime, "_after_source_store", runtime._noop_source_hook)
        resumed = await runtime.record_employee_source(
            document_id=document_id,
            source_id=source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="先保存再分析",
        )
        assert resumed.source_count == 1
        assert (
            await runtime.get_source(document_id, source_id)
        ).processing_status is SourceProcessingStatus.COMMITTED


@pytest.mark.asyncio
async def test_delete_document_removes_the_whole_authority_namespace(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        await runtime.record_employee_source(
            document_id=document_id,
            source_id=uuid4(),
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="我每天先檢查缺料，再安排採購。",
        )
        await runtime.delete_document(document_id)
        await runtime.delete_document(document_id)
        with pytest.raises(DocumentNotFound):
            await runtime.reopen_document(document_id)
