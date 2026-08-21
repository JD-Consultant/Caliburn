from __future__ import annotations

import asyncio
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
from pydantic import ValidationError

from app.adapters.langgraph.postgres import (
    ActiveConsultantRun,
    DocumentNotFound,
    IdempotencyConflict,
    PendingSourceRequiresReconciliation,
    QuoteAnchorMismatch,
    SourceConflict,
    StaleRevision,
    UnknownEvidenceSource,
    open_postgres_consultant_runtime,
)
from app.consultant.candidate_wire import (
    CandidateEditBatch,
    CandidateWireMappingError,
    OutputDocumentChange,
    OutputDocumentField,
    OutputDocumentTarget,
    OutputDuty,
    OutputOpksItem,
    OutputOpksKind,
)
from app.consultant.candidate_workspace import (
    CandidateEditRejected,
    CandidateStageRequest,
    CandidateWorkspace,
)
from app.consultant.candidate_publication import CandidatePublicationStale
from app.consultant.graph import _published_candidate_changeset
from app.consultant.interview import VerifiedConsultantCommit
from app.consultant.provider_wire import OutputAnalysisBasis
from app.consultant.skill_backend import CONSULTANT_SKILL_IDS
from app.consultant.results import (
    AnalysisBasis,
    AttentionChange,
    AttentionOperation,
    ConsultantResult,
    CandidatePublication,
    DocumentChangeOperation,
    GapReason,
    RequiredClarificationDraft,
    SufficiencyRecommendation,
    UnderstandingChange,
    UnderstandingOperation,
)
from app.consultant.state import (
    ApprovedDuty,
    ApprovedEnabler,
    ApprovedEnablerKind,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedResponsibilityRole,
    ApprovedTask,
    CommandReceipt,
    EmployeeSource,
    EmployeeSourceKind,
    InterviewPriority,
    RunStatus,
    RunExecutionEvidence,
    SourceProcessingStatus,
    SourceValidity,
    UnderstandingImpact,
)
from app.consultant.workspace_resources import WorkspaceCatalog, project_candidate_files


@pytest.mark.asyncio
async def test_catalog_and_source_first_run_admission_are_durable_and_idempotent(
    consultant_database_url: str,
) -> None:
    first_document_id = uuid4()
    second_document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(first_document_id, title="採購職務")
        await runtime.create_document(second_document_id, title="倉儲職務")
        replayed_create = await runtime.create_document(
            first_document_id, title="採購職務"
        )
        assert replayed_create.document_id == first_document_id
        with pytest.raises(IdempotencyConflict):
            await runtime.create_document(first_document_id, title="另一個標題")

        catalog = await runtime.list_documents()
        assert [item.document_id for item in catalog] == [
            first_document_id,
            second_document_id,
        ]
        assert [item.title for item in catalog] == ["採購職務", "倉儲職務"]

        admitted, should_process = await runtime.admit_employee_answer(
            document_id=first_document_id,
            run_id=run_id,
            source_id=source_id,
            text="我每天整理採購需求。",
        )
        assert should_process is True
        assert admitted.latest_run is not None
        assert admitted.latest_run["run_id"] == str(run_id)
        assert admitted.latest_run["status"] == RunStatus.SOURCE_SAVED.value

        replay, should_process = await runtime.admit_employee_answer(
            document_id=first_document_id,
            run_id=run_id,
            source_id=source_id,
            text="我每天整理採購需求。",
        )
        assert should_process is False
        assert replay.revision == admitted.revision

        with pytest.raises(SourceConflict):
            await runtime.admit_employee_answer(
                document_id=first_document_id,
                run_id=run_id,
                source_id=source_id,
                text="同一 key 卻換了內容。",
            )
        with pytest.raises(ActiveConsultantRun):
            await runtime.admit_employee_answer(
                document_id=first_document_id,
                run_id=uuid4(),
                source_id=uuid4(),
                text="這則回答不能越過待處理回合。",
            )

        failed = await runtime.mark_consultant_run_failed(
            document_id=first_document_id,
            run_id=run_id,
            error_code="model_unavailable",
        )
        assert failed.latest_run is not None
        assert failed.latest_run["status"] == RunStatus.FAILED.value
        editable_document = failed.approved_document.model_copy(
            update={"job_title": "採購專員"}
        )
        edited_while_failed = await runtime.apply_direct_edit(
            document_id=first_document_id,
            expected_revision=failed.revision,
            document=editable_document,
            source_id=uuid4(),
        )
        assert edited_while_failed.approved_document.job_title == "採購專員"
        assert (
            await runtime.export_approved_document(first_document_id)
        ).job_title == "採購專員"
        with pytest.raises(ActiveConsultantRun):
            await runtime.admit_employee_answer(
                document_id=first_document_id,
                run_id=uuid4(),
                source_id=uuid4(),
                text="失敗回合未處理前仍不能加下一則。",
            )

        retried, should_process = await runtime.admit_employee_answer(
            document_id=first_document_id,
            run_id=run_id,
            source_id=source_id,
            text="我每天整理採購需求。",
        )
        assert should_process is True
        assert retried.latest_run is not None
        assert retried.latest_run["status"] == RunStatus.SOURCE_SAVED.value

        await runtime.delete_document(first_document_id)
        await runtime.delete_document(second_document_id)


@pytest.mark.asyncio
async def test_failed_run_allows_explicit_employee_correction_but_not_unrelated_answer(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    failed_run_id = uuid4()
    failed_source_id = uuid4()
    correction_run_id = uuid4()
    correction_source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=failed_run_id,
            source_id=failed_source_id,
            text="我每天整理採購需求。",
        )
        await runtime.mark_consultant_run_failed(
            document_id=document_id,
            run_id=failed_run_id,
            error_code="invalid_employee_input",
        )

        with pytest.raises(ActiveConsultantRun):
            await runtime.admit_employee_answer(
                document_id=document_id,
                run_id=uuid4(),
                source_id=uuid4(),
                text="另一項不相干的工作。",
            )

        corrected, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=correction_run_id,
            source_id=correction_source_id,
            text="更正：我是每週整理採購需求。",
            supersedes_source_id=failed_source_id,
        )

        assert should_process is True
        assert corrected.latest_run is not None
        assert corrected.latest_run["run_id"] == str(correction_run_id)
        assert corrected.latest_run["source_id"] == str(correction_source_id)
        assert corrected.latest_run["status"] == RunStatus.SOURCE_SAVED.value
        failed_source = await runtime.get_source(document_id, failed_source_id)
        correction_source = await runtime.get_source(document_id, correction_source_id)
        assert failed_source.validity is SourceValidity.SUPERSEDED
        assert failed_source.superseded_by_source_id == correction_source_id
        assert correction_source.supersedes_source_id == failed_source_id

        await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_calibration_confirmation_is_employee_evidence_and_idempotent(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    decision_source_id = uuid4()
    run_id = uuid4()
    now = datetime.now(UTC)
    basis = AnalysisBasis(
        source_ids=(source_id,),
        skill_ids=("work-discovery",),
    )
    result = ConsultantResult(
        visible_reply="我目前理解你負責建立請購單，請確認。",
        reply_basis=basis,
        used_skill_ids=("work-discovery",),
        understanding_changes=(
            UnderstandingChange(
                operation=UnderstandingOperation.ADD,
                kind="responsibility_hypothesis",
                text="員工負責建立請購單。",
                impact=UnderstandingImpact.EMPLOYEE_REQUEST,
                basis=basis,
            ),
        ),
        sufficiency=SufficiencyRecommendation(
            currently_enough=True,
            reason="目前理解可供員工校準。",
            continuing_benefit="繼續可深入細節。",
            basis=basis,
        ),
    )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        sourced = await runtime.record_employee_source(
            document_id=document_id,
            source_id=source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="我負責建立請購單。",
        )
        proposed = await runtime.commit_verified_consultant_result(
            document_id=document_id,
            expected_revision=sourced.revision,
            commit=VerifiedConsultantCommit(
                run_id=run_id,
                answer_source_id=source_id,
                started_at=now,
                completed_at=now,
                result=result,
            ),
        )
        calibration = proposed.understanding_projection.calibration
        assert calibration is not None

        confirmed = await runtime.decide_understanding_calibration(
            document_id=document_id,
            expected_revision=proposed.revision,
            calibration_id=calibration.calibration_id,
            decision="confirm",
            employee_text="我確認上述理解正確。",
            source_id=decision_source_id,
        )
        replay = await runtime.decide_understanding_calibration(
            document_id=document_id,
            expected_revision=proposed.revision,
            calibration_id=calibration.calibration_id,
            decision="confirm",
            employee_text="我確認上述理解正確。",
            source_id=decision_source_id,
        )

        assert confirmed.revision == replay.revision
        assert confirmed.understanding_projection.calibration is None
        assert (
            confirmed.understanding_projection.items[0].status.value
            == "employee_confirmed"
        )
        evidence = await runtime.get_source(document_id, decision_source_id)
        assert evidence.text == "我確認上述理解正確。"
        assert evidence.processing_status is SourceProcessingStatus.COMMITTED


@pytest.mark.asyncio
async def test_authority_command_idempotency_is_payload_bound_and_revision_independent(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    command_id = uuid4()
    source_id = uuid4()
    receipt = CommandReceipt(
        command_id=command_id,
        command_kind="direct_document_edit",
        payload_sha256="a" * 64,
    )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")
        document = initial.approved_document.model_copy(
            update={"job_title": "採購專員"}
        )
        edited = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=document,
            source_id=source_id,
            command_receipt=receipt,
        )
        replay = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=document,
            source_id=source_id,
            command_receipt=receipt,
        )

        assert replay.revision == edited.revision
        with pytest.raises(IdempotencyConflict):
            await runtime.apply_direct_edit(
                document_id=document_id,
                expected_revision=edited.revision,
                document=document.model_copy(update={"job_title": "採購管理師"}),
                source_id=source_id,
                command_receipt=receipt.model_copy(
                    update={"payload_sha256": "b" * 64}
                ),
            )


def _psycopg_url() -> str:
    value = os.getenv("TEST_DATABASE_URL", "")
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(autouse=True)
async def cleanup_new_consultant_documents() -> AsyncIterator[None]:
    """Keep repeated local runs from accumulating random document namespaces."""
    database_url = _psycopg_url()
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
    value = _psycopg_url()
    if not value:
        pytest.skip("TEST_DATABASE_URL not set; consultant PostgreSQL test skipped")
    return value


def _document(document_id: UUID, *, suffix: str = "") -> ApprovedJobDocument:
    duty_id = uuid4()
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
                task_id=uuid4(),
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
async def test_create_reopen_and_delete_clear_the_whole_document_namespace(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.setup()
        await runtime.setup()
        created = await runtime.create_document(document_id, title="採購職務")
        async with await psycopg.AsyncConnection.connect(
            consultant_database_url, autocommit=True
        ) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT updated_at FROM consultant_documents WHERE document_id = %s",
                    (document_id,),
                )
                created_updated_at = (await cursor.fetchone())[0]
        await asyncio.sleep(0.01)
        await runtime.record_employee_source(
            document_id=document_id,
            source_id=source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="我每天先檢查缺料，再依交期安排採購。",
        )
        async with await psycopg.AsyncConnection.connect(
            consultant_database_url, autocommit=True
        ) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT updated_at FROM consultant_documents WHERE document_id = %s",
                    (document_id,),
                )
                source_updated_at = (await cursor.fetchone())[0]

        assert created.document_id == document_id
        assert created.revision == 0
        assert source_updated_at > created_updated_at

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        reopened = await runtime.reopen_document(document_id)
        source = await runtime.get_source(document_id, source_id)

        assert reopened.revision == 1
        assert reopened.source_count == 1
        assert source.text == "我每天先檢查缺料，再依交期安排採購。"

        await runtime.delete_document(document_id)
        await runtime.delete_document(document_id)

        with pytest.raises(DocumentNotFound):
            await runtime.reopen_document(document_id)
        assert await runtime.get_source_or_none(document_id, source_id) is None
        assert (
            await runtime.graph.aget_state(runtime.graph_config(document_id))
        ).values == {}


@pytest.mark.asyncio
async def test_source_is_immutable_and_correction_supersedes_without_quote_copy(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    original_id = uuid4()
    correction_id = uuid4()
    original_text = "  我每週一整理採購需求。\n"
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

        assert first.revision == replay.revision == 1
        with pytest.raises(SourceConflict):
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=original_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="同一 ID 被換成別的內容",
            )

        corrected = await runtime.record_employee_source(
            document_id=document_id,
            source_id=correction_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text=correction_text,
            supersedes_source_id=original_id,
        )
        original = await runtime.get_source(document_id, original_id)
        correction = await runtime.get_source(document_id, correction_id)
        raw_state = await runtime.raw_state(document_id)

        assert corrected.revision == 2
        assert corrected.source_count == 2
        assert original.text == original_text
        assert original.positions[0].start == 0
        assert original.positions[0].end == len(original_text)
        assert original.validity is SourceValidity.SUPERSEDED
        assert original.superseded_by_source_id == correction_id
        assert correction.validity is SourceValidity.CURRENT
        assert correction.supersedes_source_id == original_id
        checkpoint_json = json.dumps(raw_state, ensure_ascii=False, default=str)
        assert original_text not in checkpoint_json
        assert correction_text not in checkpoint_json


@pytest.mark.asyncio
async def test_verified_consultant_commit_survives_postgres_runtime_restart(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    run_id = uuid4()
    now = datetime.now(UTC)
    basis = AnalysisBasis(
        source_ids=(source_id,),
        skill_ids=("work-discovery",),
    )
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
                reason="這是目前最清楚且可深入的工作故事。",
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
            context_selection_receipts=({"loaded_source_ids": [str(source_id)]},),
            attempt_receipts=({"actual_provider": "Anthropic"},),
        ),
        result=result,
    )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
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

        assert committed.revision == sourced.revision + 1
        assert committed.messages[0].run_id == run_id
        assert committed.approved_document.tasks == ()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        reopened = await runtime.reopen_document(document_id)
        raw = await runtime.raw_state(document_id)

        assert reopened.revision == committed.revision
        assert reopened.messages[0].text == result.visible_reply
        assert reopened.current_interview is not None
        assert reopened.current_interview.title == "請購下單"
        assert reopened.understanding_projection.items[0].text == (
            "員工依缺料狀況建立請購單。"
        )
        assert reopened.sufficiency.currently_enough is False
        assert raw["latest_run"]["run_id"] == str(run_id)
        assert raw["latest_run"]["execution_evidence"]["resolved_execution"][
            "requested_model"
        ] == "anthropic/claude-opus-5"
        assert "我會先看缺料" not in json.dumps(
            raw["latest_run"]["execution_evidence"],
            ensure_ascii=False,
        )
        assert raw["approved_document"]["tasks"] == []


@pytest.mark.asyncio
async def test_pending_source_reconciles_both_crash_windows(
    consultant_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_checkpoint_document = uuid4()
    after_checkpoint_document = uuid4()
    before_source = uuid4()
    after_source = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(before_checkpoint_document, title="A")
        await runtime.create_document(after_checkpoint_document, title="B")

        async def fail_after_store(_source: EmployeeSource) -> None:
            raise RuntimeError("after-store")

        monkeypatch.setattr(runtime, "_after_source_store", fail_after_store)
        with pytest.raises(RuntimeError, match="after-store"):
            await runtime.record_employee_source(
                document_id=before_checkpoint_document,
                source_id=before_source,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="先保存再分析",
            )
        pending = await runtime.get_source(before_checkpoint_document, before_source)
        assert pending.processing_status is SourceProcessingStatus.PENDING
        assert (await runtime.reopen_document(before_checkpoint_document)).source_count == 0
        with pytest.raises(PendingSourceRequiresReconciliation):
            await runtime.record_employee_source(
                document_id=before_checkpoint_document,
                source_id=uuid4(),
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="不能越過前一筆 pending input",
            )

        monkeypatch.setattr(runtime, "_after_source_store", runtime._noop_source_hook)
        resumed = await runtime.record_employee_source(
            document_id=before_checkpoint_document,
            source_id=before_source,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="先保存再分析",
        )
        assert resumed.source_count == 1
        assert (
            await runtime.get_source(before_checkpoint_document, before_source)
        ).processing_status is SourceProcessingStatus.COMMITTED

        async def fail_after_checkpoint(_source: EmployeeSource) -> None:
            raise RuntimeError("after-checkpoint")

        monkeypatch.setattr(runtime, "_after_source_checkpoint", fail_after_checkpoint)
        with pytest.raises(RuntimeError, match="after-checkpoint"):
            await runtime.record_employee_source(
                document_id=after_checkpoint_document,
                source_id=after_source,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="checkpoint 後再標記完成",
            )
        checkpointed = await runtime.reopen_document(after_checkpoint_document)
        assert checkpointed.source_count == 1
        assert (
            await runtime.get_source(after_checkpoint_document, after_source)
        ).processing_status is SourceProcessingStatus.PENDING

        monkeypatch.setattr(
            runtime, "_after_source_checkpoint", runtime._noop_source_hook
        )
        reconciled = await runtime.record_employee_source(
            document_id=after_checkpoint_document,
            source_id=after_source,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="checkpoint 後再標記完成",
        )
        assert reconciled.source_count == 1
        assert reconciled.revision == checkpointed.revision


@pytest.mark.asyncio
async def test_answer_admission_reconciles_both_source_first_crash_windows(
    consultant_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_checkpoint_document = uuid4()
    after_checkpoint_document = uuid4()
    before_run, before_source = uuid4(), uuid4()
    after_run, after_source = uuid4(), uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(before_checkpoint_document, title="A")
        await runtime.create_document(after_checkpoint_document, title="B")

        async def fail_after_store(_source: EmployeeSource) -> None:
            raise RuntimeError("answer-after-store")

        monkeypatch.setattr(runtime, "_after_source_store", fail_after_store)
        with pytest.raises(RuntimeError, match="answer-after-store"):
            await runtime.admit_employee_answer(
                document_id=before_checkpoint_document,
                run_id=before_run,
                source_id=before_source,
                text="先保存員工回答再啟動模型",
            )
        monkeypatch.setattr(runtime, "_after_source_store", runtime._noop_source_hook)
        resumed, should_process = await runtime.admit_employee_answer(
            document_id=before_checkpoint_document,
            run_id=before_run,
            source_id=before_source,
            text="先保存員工回答再啟動模型",
        )
        assert should_process is True
        assert resumed.latest_run["status"] == RunStatus.SOURCE_SAVED.value
        assert (
            await runtime.get_source(before_checkpoint_document, before_source)
        ).processing_status is SourceProcessingStatus.COMMITTED

        async def fail_after_checkpoint(_source: EmployeeSource) -> None:
            raise RuntimeError("answer-after-checkpoint")

        monkeypatch.setattr(runtime, "_after_source_checkpoint", fail_after_checkpoint)
        with pytest.raises(RuntimeError, match="answer-after-checkpoint"):
            await runtime.admit_employee_answer(
                document_id=after_checkpoint_document,
                run_id=after_run,
                source_id=after_source,
                text="checkpoint 已記住可恢復 run",
            )
        monkeypatch.setattr(
            runtime, "_after_source_checkpoint", runtime._noop_source_hook
        )
        reconciled, should_process = await runtime.admit_employee_answer(
            document_id=after_checkpoint_document,
            run_id=after_run,
            source_id=after_source,
            text="checkpoint 已記住可恢復 run",
        )
        assert should_process is False
        assert reconciled.latest_run["status"] == RunStatus.SOURCE_SAVED.value
        assert (
            await runtime.get_source(after_checkpoint_document, after_source)
        ).processing_status is SourceProcessingStatus.COMMITTED


@pytest.mark.asyncio
async def test_direct_edit_mints_only_changed_employee_text_and_exports_checkpoint(
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
        first_source = await runtime.get_source(document_id, first_source_id)
        revised_document = first_document.model_copy(
            update={"work_description": "負責缺料預警與緊急採購協調"}
        )
        second = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=first.revision,
            document=revised_document,
            source_id=second_source_id,
        )
        second_source = await runtime.get_source(document_id, second_source_id)
        exported = await runtime.export_approved_document(document_id)
        replay = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=first.revision,
            document=revised_document,
            source_id=second_source_id,
        )

        assert second.revision == first.revision + 1
        assert replay.revision == second.revision
        assert first_source.text.splitlines() == [
            "採購管理專員",
            "負責缺料檢查與採購安排",
            "物料供應管理",
            "檢查缺料並安排採購",
            "檢查並安排",
            "缺料與採購",
            "確保物料按期供應",
        ]
        assert str(document_id) not in first_source.text
        assert str(first_document.duties[0].duty_id) not in first_source.text
        assert str(first_document.tasks[0].task_id) not in first_source.text
        assert second_source.kind is EmployeeSourceKind.DIRECT_EDIT
        assert second_source.text == "負責缺料預警與緊急採購協調"
        assert [anchor.model_dump(mode="json") for anchor in second_source.positions] == [
            {
                "document_path": "/work_description",
                "start": 0,
                "end": len(second_source.text),
            }
        ]
        assert first_document.job_title not in second_source.text
        assert exported == revised_document


@pytest.mark.asyncio
async def test_document_review_and_clarification_survive_postgres_restart(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    seed_source_id = uuid4()
    answer_source_id = uuid4()
    edit_source_id = uuid4()
    clarification_basis_source_id = uuid4()
    clarification_answer_source_id = uuid4()
    document = _document(document_id)
    task_id = document.tasks[0].task_id

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")
        await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=document,
            source_id=seed_source_id,
        )
        run_id = uuid4()
        sourced, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=answer_source_id,
            text="我會建立並覆核請購單。",
        )
        basis = AnalysisBasis(
            source_ids=(answer_source_id,),
            skill_ids=("task-boundary",),
        )
        committed = await _stage_and_publish(
            runtime,
            document_id=document_id,
            run_id=run_id,
            source_id=answer_source_id,
            baseline_revision=sourced.revision,
            changes=(
                _candidate_wire_change(
                    change_ref="task-statement",
                    operation=DocumentChangeOperation.REVISE,
                    target=OutputDocumentTarget.TASK,
                    target_id=str(task_id),
                    field=OutputDocumentField.STATEMENT,
                    text_value="建立並覆核請購單",
                    duties=(),
                ),
            ),
            result=ConsultantResult(
                visible_reply="我整理了一項任務文字更新供您審核。",
                reply_basis=basis,
                used_skill_ids=("task-boundary",),
                attention_changes=(
                    AttentionChange(
                        operation=AttentionOperation.ADD,
                        kind="task_boundary",
                        title="請購下單",
                        subject_id=task_id,
                        reason="需要確認請購責任邊界。",
                        priority=InterviewPriority.TASK_BOUNDARY,
                        make_current=True,
                        basis=basis,
                    ),
                ),
                sufficiency=SufficiencyRecommendation(
                    currently_enough=False,
                    reason="其他採購工作尚待盤點。",
                    remaining_gap_reasons=(GapReason.WORK_COVERAGE_MISSING,),
                    continuing_benefit="繼續訪談可補齊其他工作。",
                    basis=basis,
                ),
            ),
            candidate_skill_id="task-boundary",
        )
        bundle = committed.document_review.bundles[0]
        action = bundle.actions[0]
        reviewed = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=committed.revision,
            action="edit_and_accept_changes",
            changeset_id=bundle.changeset_id,
            action_ids=(action.action_id,),
            edited_after_by_action_id={
                action.action_id: "建立、覆核並送出請購單"
            },
            source_id=edit_source_id,
        )
        edit_source = await runtime.get_source(document_id, edit_source_id)

        assert reviewed.approved_document.tasks[0].statement == (
            "建立、覆核並送出請購單"
        )
        assert edit_source.text == "建立、覆核並送出請購單"
        assert edit_source.positions[0].document_path == (
            f"/tasks/{task_id}/statement"
        )
        assert "建立並覆核請購單" not in edit_source.text

        sourced_again = await runtime.record_employee_source(
            document_id=document_id,
            source_id=clarification_basis_source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="有時是我建立，有時是主管建立。",
        )
        clarification_basis = AnalysisBasis(
            source_ids=(clarification_basis_source_id,),
            skill_ids=("story-interview",),
        )
        now = datetime.now(UTC)
        waiting = await runtime.commit_verified_consultant_result(
            document_id=document_id,
            expected_revision=sourced_again.revision,
            commit=VerifiedConsultantCommit(
                run_id=uuid4(),
                answer_source_id=clarification_basis_source_id,
                started_at=now,
                completed_at=now,
                result=ConsultantResult(
                    visible_reply="責任邊界互相衝突，需要先請您確認。",
                    reply_basis=clarification_basis,
                    used_skill_ids=("story-interview",),
                    required_clarification=RequiredClarificationDraft(
                        reason="兩次說法對建立請購單的責任不同",
                        question="通常由誰建立請購單？",
                        current_understanding="可能由員工或主管建立。",
                        choices=("由我建立", "由主管建立", "視情況"),
                        affected_work_ids=(
                            reviewed.current_interview.work_id,
                        ),
                        affected_branch="請購下單／責任邊界",
                        basis=clarification_basis,
                    ),
                    sufficiency=SufficiencyRecommendation(
                        currently_enough=False,
                        reason="請購責任仍有衝突。",
                        remaining_gap_reasons=(GapReason.SOURCE_CONTRADICTION,),
                        continuing_benefit="確認後才能安全繼續該分支。",
                        basis=clarification_basis,
                    ),
                ),
            ),
        )
        assert waiting.required_clarification is not None
        waiting_document = waiting.approved_document

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        reopened = await runtime.reopen_document(document_id)
        assert reopened.required_clarification is not None
        resumed = await runtime.answer_required_clarification(
            document_id=document_id,
            expected_revision=reopened.revision,
            clarification_id=reopened.required_clarification.clarification_id,
            choice="由我建立",
            text="通常由我建立請購單，主管只在例外時協助。",
            source_id=clarification_answer_source_id,
        )
        clarification_source = await runtime.get_source(
            document_id, clarification_answer_source_id
        )

        assert resumed.required_clarification is None
        assert resumed.approved_document == waiting_document
        assert clarification_source.kind is EmployeeSourceKind.EMPLOYEE_TURN
        assert clarification_source.text == (
            "通常由我建立請購單，主管只在例外時協助。"
        )


@pytest.mark.asyncio
async def test_structural_edit_accept_uses_candidate_source_without_minting_evidence(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    seed_source_id = uuid4()
    answer_source_id = uuid4()
    candidate_edit_source_id = uuid4()
    document = _document(document_id)
    duty_id = document.duties[0].duty_id

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=document,
            source_id=seed_source_id,
        )
        run_id = uuid4()
        sourced, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=answer_source_id,
            text="這項工作可能不屬於原本的主要職責。",
        )
        basis = AnalysisBasis(
            source_ids=(answer_source_id,),
            skill_ids=("duty-grouping",),
        )
        proposed = await _stage_and_publish(
            runtime,
            document_id=document_id,
            run_id=run_id,
            source_id=answer_source_id,
            baseline_revision=sourced.revision,
            changes=(
                _candidate_wire_change(
                    change_ref="duty-reorder",
                    operation=DocumentChangeOperation.REORDER,
                    target=OutputDocumentTarget.DUTY,
                    target_id=str(duty_id),
                    field=OutputDocumentField.DISPLAY_ORDER,
                    text_value="",
                    integer_value=1,
                    duties=(),
                ),
            ),
            result=ConsultantResult(
                visible_reply="我整理了一項工作歸類建議供你確認。",
                reply_basis=basis,
                used_skill_ids=("duty-grouping",),
                sufficiency=SufficiencyRecommendation(
                    currently_enough=False,
                    reason="仍有其他工作待確認。",
                    remaining_gap_reasons=(GapReason.WORK_COVERAGE_MISSING,),
                    continuing_benefit="繼續訪談可確認職責分組。",
                    basis=basis,
                ),
            ),
            candidate_skill_id="duty-grouping",
        )
        bundle = proposed.document_review.bundles[0]
        action = bundle.actions[0]

        reviewed = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=proposed.revision,
            action="edit_and_accept_changes",
            changeset_id=bundle.changeset_id,
            action_ids=(action.action_id,),
            edited_after_by_action_id={action.action_id: 0},
            source_id=candidate_edit_source_id,
        )

        assert next(
            duty for duty in reviewed.approved_document.duties if duty.duty_id == duty_id
        ).display_order == 0
        assert (
            await runtime.get_source_or_none(document_id, candidate_edit_source_id)
        ) is None
        assert reviewed.source_count == seeded.source_count + 1

        await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_opks_edit_accept_attaches_direct_edit_source_to_adopted_text(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    seed_source_id = uuid4()
    answer_source_id = uuid4()
    direct_edit_source_id = uuid4()
    document = _document(document_id)
    task_id = document.tasks[0].task_id
    edited_text = "每週五完成採購異常報表"

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=document,
            source_id=seed_source_id,
        )
        run_id = uuid4()
        sourced, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=answer_source_id,
            text="我負責整理採購異常報表。",
        )
        proposed = await _stage_and_publish(
            runtime,
            document_id=document_id,
            run_id=run_id,
            source_id=answer_source_id,
            baseline_revision=sourced.revision,
            changes=(_candidate_opks_add(task_id),),
            result=_publication_result(answer_source_id, None),
        )
        bundle = proposed.document_review.bundles[0]
        action = bundle.actions[0]
        assert isinstance(action.after, dict)

        reviewed = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=proposed.revision,
            action="edit_and_accept_changes",
            changeset_id=bundle.changeset_id,
            action_ids=(action.action_id,),
            edited_after_by_action_id={
                action.action_id: {**action.after, "text": edited_text}
            },
            source_id=direct_edit_source_id,
        )
        source = await runtime.get_source(document_id, direct_edit_source_id)
        terminal_bundle = reviewed.document_review.bundles[0]
        terminal_action = terminal_bundle.actions[0]

        assert reviewed.approved_document.opks[0].evidence_source_ids[-1] == (
            direct_edit_source_id
        )
        assert direct_edit_source_id in terminal_action.source_ids
        assert direct_edit_source_id in terminal_bundle.source_ids
        assert source.positions[0].document_path == "/opks/text"
        assert source.positions[0].start == 0
        assert (
            source.text[source.positions[0].start : source.positions[0].end]
            == edited_text
        )
        assert reviewed.source_count == seeded.source_count + 2

        await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_mixed_opks_text_and_structural_edit_accept_scopes_direct_source(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    seed_source_id = uuid4()
    answer_source_id = uuid4()
    direct_edit_source_id = uuid4()
    document = _document(document_id)
    task_id = document.tasks[0].task_id
    duty_id = document.duties[0].duty_id
    edited_text = "每週五完成採購異常報表"

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=document,
            source_id=seed_source_id,
        )
        run_id = uuid4()
        sourced, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=answer_source_id,
            text="我負責整理採購異常報表。",
        )
        proposed = await _stage_and_publish(
            runtime,
            document_id=document_id,
            run_id=run_id,
            source_id=answer_source_id,
            baseline_revision=sourced.revision,
            changes=(
                _candidate_opks_add(task_id),
                _candidate_wire_change(
                    change_ref="duty-reorder-with-opks-text",
                    operation=DocumentChangeOperation.REORDER,
                    target=OutputDocumentTarget.DUTY,
                    target_id=str(duty_id),
                    field=OutputDocumentField.DISPLAY_ORDER,
                    text_value="",
                    integer_value=1,
                    duties=(),
                ),
            ),
            result=_publication_result(answer_source_id, None),
        )
        bundle = proposed.document_review.bundles[0]
        textual_action = next(
            action for action in bundle.actions if action.path == "/opks"
        )
        structural_action = next(
            action
            for action in bundle.actions
            if action.path == f"/duties/{duty_id}/display_order"
        )

        reviewed = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=proposed.revision,
            action="edit_and_accept_changes",
            changeset_id=bundle.changeset_id,
            action_ids=(textual_action.action_id, structural_action.action_id),
            edited_after_by_action_id={
                textual_action.action_id: {
                    **textual_action.after,
                    "text": edited_text,
                },
                structural_action.action_id: 1,
            },
            source_id=direct_edit_source_id,
        )
        source = await runtime.get_source(document_id, direct_edit_source_id)
        terminal_bundle = reviewed.document_review.bundles[0]
        terminal_textual_action = next(
            action for action in terminal_bundle.actions if action.path == "/opks"
        )
        terminal_structural_action = next(
            action
            for action in terminal_bundle.actions
            if action.path == f"/duties/{duty_id}/display_order"
        )

        assert reviewed.approved_document.opks[0].text == edited_text
        assert reviewed.approved_document.duties[0].display_order == 1
        assert direct_edit_source_id in terminal_textual_action.source_ids
        assert direct_edit_source_id not in terminal_structural_action.source_ids
        assert direct_edit_source_id in terminal_bundle.source_ids
        assert len(source.positions) == 1
        assert source.positions[0].document_path == "/opks/text"
        assert source.positions[0].start == 0
        assert source.positions[0].end == len(edited_text)
        assert source.text[source.positions[0].start : source.positions[0].end] == (
            edited_text
        )
        assert reviewed.source_count == seeded.source_count + 2

        await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_structural_edit_accept_does_not_attach_text_evidence(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    seed_source_id = uuid4()
    answer_source_id = uuid4()
    candidate_edit_source_id = uuid4()
    document = _document(document_id)
    task_id = document.tasks[0].task_id

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=document,
            source_id=seed_source_id,
        )
        run_id = uuid4()
        sourced, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=answer_source_id,
            text="我負責整理採購異常報表。",
        )
        proposed = await _stage_and_publish(
            runtime,
            document_id=document_id,
            run_id=run_id,
            source_id=answer_source_id,
            baseline_revision=sourced.revision,
            changes=(_candidate_opks_add(task_id),),
            result=_publication_result(answer_source_id, None),
        )
        bundle = proposed.document_review.bundles[0]
        action = bundle.actions[0]
        assert isinstance(action.after, dict)
        new_order = int(action.after["display_order"]) + 1

        reviewed = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=proposed.revision,
            action="edit_and_accept_changes",
            changeset_id=bundle.changeset_id,
            action_ids=(action.action_id,),
            edited_after_by_action_id={
                action.action_id: {**action.after, "display_order": new_order}
            },
            source_id=candidate_edit_source_id,
        )
        terminal_bundle = reviewed.document_review.bundles[0]
        terminal_action = terminal_bundle.actions[0]

        assert reviewed.approved_document.opks[0].display_order == new_order
        assert (
            await runtime.get_source_or_none(document_id, candidate_edit_source_id)
        ) is None
        assert candidate_edit_source_id not in terminal_action.source_ids
        assert candidate_edit_source_id not in terminal_bundle.source_ids
        assert reviewed.source_count == seeded.source_count + 1

        await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_candidate_opks_rejection_identity_survives_new_run_and_new_source(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    seed_source_id = uuid4()
    first_answer_source_id = uuid4()
    second_answer_source_id = uuid4()
    document = _document(document_id)
    task_id = document.tasks[0].task_id

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")
        await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=document,
            source_id=seed_source_id,
        )
        first_run_id = uuid4()
        first_sourced, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=first_run_id,
            source_id=first_answer_source_id,
            text="我負責整理採購異常報表。",
        )
        first = await _stage_and_publish(
            runtime,
            document_id=document_id,
            run_id=first_run_id,
            source_id=first_answer_source_id,
            baseline_revision=first_sourced.revision,
            changes=(_candidate_opks_add(task_id),),
            result=_publication_result(first_answer_source_id, None),
        )
        first_bundle = first.document_review.bundles[0]
        first_action = first_bundle.actions[0]

        rejected = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=first.revision,
            action="reject_changes",
            changeset_id=first_bundle.changeset_id,
            action_ids=(first_action.action_id,),
            rejection_reason="這不是本工作的產出。",
        )

        second_run_id = uuid4()
        second_sourced, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=second_run_id,
            source_id=second_answer_source_id,
            text="我也會覆核採購異常報表。",
        )
        second_receipt = await runtime.stage_candidate_revision(
            document_id=document_id,
            request=_candidate_stage_request(
                run_id=second_run_id,
                source_id=second_answer_source_id,
                baseline_revision=second_sourced.revision,
                tool_call_id="candidate-tool-2",
                changes=(_candidate_opks_add(task_id),),
            ),
        )
        second_state = CandidateWorkspace.model_validate(
            (await runtime.raw_state(document_id))["active_candidate"]
        )
        second_action = second_state.changeset.actions[0]
        second_source = await runtime.get_source(
            document_id, second_answer_source_id
        )

        assert rejected.approved_document == first.approved_document
        assert first_action.after["item_id"] != second_action.after["item_id"]
        assert first_action.target_key == second_action.target_key
        assert first_action.read_set == second_action.read_set
        assert second_action.read_set[0].path == "/opks"
        assert second_source.processing_status is SourceProcessingStatus.COMMITTED
        assert second_receipt.actions[0].action_id == second_action.action_id

        await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_direct_edit_rejects_unknown_opks_evidence_before_writing_source(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    direct_edit_source_id = uuid4()
    unknown_source_id = uuid4()
    document = _document(document_id)
    document = document.model_copy(
        update={
            "opks": (
                ApprovedOpksItem(
                    item_id=uuid4(),
                    kind=ApprovedOpksKind.OUTPUT,
                    text="採購安排結果",
                    display_order=0,
                    task_ids=(document.tasks[0].task_id,),
                    evidence_source_ids=(unknown_source_id,),
                ),
            )
        }
    )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")

        with pytest.raises(UnknownEvidenceSource, match=str(unknown_source_id)):
            await runtime.apply_direct_edit(
                document_id=document_id,
                expected_revision=initial.revision,
                document=document,
                source_id=direct_edit_source_id,
            )

        assert (
            await runtime.get_source_or_none(document_id, direct_edit_source_id)
            is None
        )

        valid_document = document.model_copy(
            update={
                "opks": (
                    document.opks[0].model_copy(
                        update={"evidence_source_ids": (direct_edit_source_id,)}
                    ),
                )
            }
        )
        committed = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=valid_document,
            source_id=direct_edit_source_id,
        )

        assert committed.approved_document == valid_document
        assert (
            await runtime.get_source(document_id, direct_edit_source_id)
        ).text.endswith("採購安排結果")


@pytest.mark.asyncio
async def test_generic_source_entry_cannot_mint_a_direct_edit_source(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        with pytest.raises(ValueError, match="authority command"):
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=uuid4(),
                kind=EmployeeSourceKind.DIRECT_EDIT,
                text="不能繞過 direct-edit authority command",
            )


def test_only_employee_turn_and_direct_edit_can_be_evidence_sources() -> None:
    common = {
        "source_id": str(uuid4()),
        "document_id": str(uuid4()),
        "speaker": "employee",
        "text": "內容",
        "text_sha256": "0" * 64,
        "created_at": datetime.now(UTC).isoformat(),
        "processing_status": "pending",
        "validity": "current",
    }
    for forbidden in ("model_output", "accepted", "rejected", "deferred", "reference"):
        with pytest.raises(ValidationError):
            EmployeeSource.model_validate({**common, "kind": forbidden})


def test_approved_document_preserves_manual_fields_and_opks_relationships() -> None:
    document_id = uuid4()
    duty_id = uuid4()
    task_id = uuid4()
    output_id = uuid4()
    indicator_id = uuid4()
    knowledge_id = uuid4()
    source_id = uuid4()
    document = ApprovedJobDocument(
        document_id=document_id,
        competency_level=4,
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
                frequency_text="每日",
                responsibility_role=ApprovedResponsibilityRole.PRIMARY,
                enablers=(
                    ApprovedEnabler(
                        kind=ApprovedEnablerKind.TOOL_SYSTEM,
                        name="ERP",
                    ),
                ),
                display_order=0,
                competency_level=3,
            ),
        ),
        opks=(
            ApprovedOpksItem(
                item_id=output_id,
                kind=ApprovedOpksKind.OUTPUT,
                text="採購安排結果",
                display_order=0,
                task_ids=(task_id,),
                evidence_source_ids=(source_id,),
            ),
            ApprovedOpksItem(
                item_id=indicator_id,
                kind=ApprovedOpksKind.PERFORMANCE_INDICATOR,
                text="缺料案件於交期前完成處置",
                display_order=0,
                task_ids=(task_id,),
                evidence_source_ids=(source_id,),
            ),
            ApprovedOpksItem(
                item_id=knowledge_id,
                kind=ApprovedOpksKind.KNOWLEDGE,
                text="物料需求規則",
                display_order=0,
                task_ids=(task_id,),
                indicator_ids=(indicator_id,),
                evidence_source_ids=(source_id,),
            ),
        ),
    )

    assert document.tasks[0].frequency_text == "每日"
    assert document.tasks[0].enablers[0].name == "ERP"
    assert document.opks[1].kind.value == "indicator"

    with pytest.raises(ValidationError, match="exactly one task"):
        ApprovedOpksItem(
            item_id=uuid4(),
            kind=ApprovedOpksKind.OUTPUT,
            text="沒有 Task 的 Output",
            display_order=1,
        )
    with pytest.raises(ValidationError, match="performance indicators"):
        ApprovedJobDocument.model_validate(
            document.model_copy(
                update={
                    "opks": (
                        *document.opks,
                        ApprovedOpksItem(
                            item_id=uuid4(),
                            kind=ApprovedOpksKind.SKILL,
                            text="錯誤連到 Output",
                            display_order=0,
                            indicator_ids=(output_id,),
                            evidence_source_ids=(source_id,),
                        ),
                    )
                }
            ).model_dump(mode="json")
        )


@pytest.mark.asyncio
async def test_same_thread_writers_are_serialized_and_one_becomes_stale(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")
        outcomes = await asyncio.gather(
            runtime.apply_direct_edit(
                document_id=document_id,
                expected_revision=initial.revision,
                document=_document(document_id, suffix=" A"),
                source_id=uuid4(),
            ),
            runtime.apply_direct_edit(
                document_id=document_id,
                expected_revision=initial.revision,
                document=_document(document_id, suffix=" B"),
                source_id=uuid4(),
            ),
            return_exceptions=True,
        )

        assert sum(not isinstance(outcome, Exception) for outcome in outcomes) == 1
        assert sum(isinstance(outcome, StaleRevision) for outcome in outcomes) == 1
        assert (await runtime.reopen_document(document_id)).revision == 1


@pytest.mark.asyncio
async def test_quote_anchor_and_uuid_namespace_are_document_scoped(
    consultant_database_url: str,
) -> None:
    first_document = uuid4()
    second_document = uuid4()
    shared_source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(first_document, title="A")
        await runtime.create_document(second_document, title="B")
        await runtime.record_employee_source(
            document_id=first_document,
            source_id=shared_source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text=" 每天檢查缺料並通知採購。",
        )
        await runtime.record_employee_source(
            document_id=second_document,
            source_id=shared_source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="每週彙整盤點差異。",
        )

        anchor = await runtime.resolve_quote(
            first_document,
            shared_source_id,
            start=3,
            end=7,
            expected_quote="檢查缺料",
        )
        leading_space_anchor = await runtime.resolve_quote(
            first_document,
            shared_source_id,
            start=0,
            end=3,
            expected_quote=" 每天",
        )
        assert anchor.quote == "檢查缺料"
        assert leading_space_anchor.quote == " 每天"
        assert (
            await runtime.get_source(first_document, shared_source_id)
        ).text != (await runtime.get_source(second_document, shared_source_id)).text
        with pytest.raises(QuoteAnchorMismatch):
            await runtime.resolve_quote(
                first_document,
                shared_source_id,
                start=3,
                end=7,
                expected_quote="彙整盤點",
            )
        with pytest.raises((TypeError, ValueError)):
            runtime.source_namespace("employee%input")


def _candidate_wire_change(**overrides: object) -> OutputDocumentChange:
    values: dict[str, object] = {
        "change_ref": "candidate-duty",
        "depends_on_change_refs": (),
        "depends_on_action_ids": (),
        "supersedes_action_ids": (),
        "atomic_group_ref": "",
        "operation": DocumentChangeOperation.ADD,
        "target": OutputDocumentTarget.DUTY,
        "target_id": "",
        "field": OutputDocumentField.ENTITY,
        "text_value": "",
        "integer_value": -1,
        "uuid_value": "",
        "uuid_values": (),
        "enablers": (),
        "duties": (
            OutputDuty(
                duty_id="",
                entity_ref="candidate-duty",
                statement="管理採購作業",
                display_order=-1,
            ),
        ),
        "tasks": (),
        "opks_items": (),
        "opks_kind": OutputOpksKind.NONE,
        "task_ids": (),
        "indicator_ids": (),
        "basis_ordinal": 1,
    }
    values.update(overrides)
    return OutputDocumentChange(**values)


def _candidate_opks_add(task_id: UUID) -> OutputDocumentChange:
    return _candidate_wire_change(
        change_ref="candidate-opks",
        target=OutputDocumentTarget.OPKS,
        field=OutputDocumentField.ENTITY,
        duties=(),
        tasks=(),
        opks_items=(
            OutputOpksItem(
                item_id="",
                entity_ref="candidate-opks-item",
                text="模型提出的工作產出",
                display_order=-1,
                task_ids=(task_id,),
                indicator_ids=(),
                task_refs=(),
                indicator_refs=(),
            ),
        ),
        opks_kind=OutputOpksKind.OUTPUT,
        task_ids=(task_id,),
        indicator_ids=(),
    )


def _two_candidate_wire_changes() -> tuple[OutputDocumentChange, ...]:
    return (
        _candidate_wire_change(),
        _candidate_wire_change(
            change_ref="candidate-duty-two",
            duties=(
                OutputDuty(
                    duty_id="",
                    entity_ref="candidate-duty-two",
                    statement="追蹤供應商交期。",
                    display_order=-1,
                ),
            ),
        ),
    )


def _candidate_stage_request(
    *,
    run_id: UUID,
    source_id: UUID,
    baseline_revision: int,
    base_candidate_revision: int = 0,
    tool_call_id: str = "candidate-tool-1",
    changes: tuple[OutputDocumentChange, ...] | None = None,
    summary: str = "建立可審核的候選文件。",
    skill_id: str = "task-boundary",
) -> CandidateStageRequest:
    return CandidateStageRequest(
        run_id=run_id,
        baseline_revision=baseline_revision,
        tool_call_id=tool_call_id,
        batch=CandidateEditBatch(
            base_candidate_revision=base_candidate_revision,
            summary=summary,
            analysis_bases=(
                OutputAnalysisBasis(
                    source_ids=(source_id,),
                    quote_anchors=(),
                    skill_ids=(skill_id,),
                ),
            ),
            replacement_changes=changes or (_candidate_wire_change(),),
        ),
        selected_skill_ids=(skill_id,),
        loaded_skill_ids=(skill_id,),
    )


def _publication_result(
    source_id: UUID,
    publication: CandidatePublication | None,
    *,
    skill_id: str = "task-boundary",
) -> ConsultantResult:
    basis = AnalysisBasis(source_ids=(source_id,), skill_ids=(skill_id,))
    return ConsultantResult(
        visible_reply="我已整理本回合的職務分析結果。",
        reply_basis=basis,
        used_skill_ids=(skill_id,),
        candidate_publication=publication,
        sufficiency=SufficiencyRecommendation(
            currently_enough=True,
            reason="目前資訊足以保存這項工作。",
            continuing_benefit="繼續訪談仍可補充細節。",
            basis=basis,
        ),
    )


def _publication(receipt) -> CandidatePublication:
    return CandidatePublication(
        candidate_revision=receipt.candidate_revision,
        revision_digest=receipt.revision_digest,
        action_ids=receipt.action_ids,
    )


async def _stage_and_publish(
    runtime,
    *,
    document_id: UUID,
    run_id: UUID,
    source_id: UUID,
    baseline_revision: int,
    result: ConsultantResult,
    changes: tuple[OutputDocumentChange, ...] | None = None,
    candidate_skill_id: str = "task-boundary",
):
    receipt = await runtime.stage_candidate_revision(
        document_id=document_id,
        request=_candidate_stage_request(
            run_id=run_id,
            source_id=source_id,
            baseline_revision=baseline_revision,
            changes=changes,
            skill_id=candidate_skill_id,
        ),
    )
    now = datetime.now(UTC)
    return await runtime.commit_verified_consultant_result(
        document_id=document_id,
        expected_revision=baseline_revision,
        commit=VerifiedConsultantCommit(
            run_id=run_id,
            answer_source_id=source_id,
            started_at=now,
            completed_at=now,
            result=result.model_copy(
                update={"candidate_publication": _publication(receipt)}
            ),
        ),
    )


@pytest.mark.asyncio
async def test_semantic_commit_publishes_only_the_exact_latest_candidate(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    now = datetime.now(UTC)

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        admitted, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責管理採購作業。",
        )
        receipt = await runtime.stage_candidate_revision(
            document_id=document_id,
            request=_candidate_stage_request(
                run_id=run_id,
                source_id=source_id,
                baseline_revision=admitted.revision,
            ),
        )
        published = await runtime.commit_verified_consultant_result(
            document_id=document_id,
            expected_revision=admitted.revision,
            commit=VerifiedConsultantCommit(
                run_id=run_id,
                answer_source_id=source_id,
                started_at=now,
                completed_at=now,
                result=_publication_result(
                    source_id,
                    CandidatePublication(
                        candidate_revision=receipt.candidate_revision,
                        revision_digest=receipt.revision_digest,
                        action_ids=receipt.action_ids,
                    ),
                ),
            ),
        )

        assert published.approved_document == admitted.approved_document
        assert len(published.document_review.bundles) == 1
        bundle = published.document_review.bundles[0]
        assert tuple(action.action_id for action in bundle.actions) == receipt.action_ids
        assert (await runtime.raw_state(document_id))["active_candidate"] is None
        await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_neutral_semantic_commit_discards_unpublished_candidate_only_after_commit(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        admitted, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責管理採購作業。",
        )
        await runtime.stage_candidate_revision(
            document_id=document_id,
            request=_candidate_stage_request(
                run_id=run_id,
                source_id=source_id,
                baseline_revision=admitted.revision,
            ),
        )
        committed = await runtime.commit_verified_consultant_result(
            document_id=document_id,
            expected_revision=admitted.revision,
            commit=VerifiedConsultantCommit(
                run_id=run_id,
                answer_source_id=source_id,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                result=_publication_result(source_id, None),
            ),
        )

        assert committed.approved_document == admitted.approved_document
        assert committed.document_review.bundles == ()
        assert (await runtime.raw_state(document_id))["active_candidate"] is None
        await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_publication_fails_closed_unless_it_is_the_latest_exact_candidate(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        admitted, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責管理採購作業。",
        )
        first = await runtime.stage_candidate_revision(
            document_id=document_id,
            request=_candidate_stage_request(
                run_id=run_id,
                source_id=source_id,
                baseline_revision=admitted.revision,
            ),
        )
        latest = await runtime.stage_candidate_revision(
            document_id=document_id,
            request=_candidate_stage_request(
                run_id=run_id,
                source_id=source_id,
                baseline_revision=admitted.revision,
                base_candidate_revision=first.candidate_revision,
                tool_call_id="candidate-tool-2",
                changes=_two_candidate_wire_changes(),
            ),
        )
        before_state = await runtime.raw_state(document_id)
        before_snapshot = await runtime.reopen_document(document_id)

        attempts = (
            (
                CandidatePublication(
                    candidate_revision=latest.candidate_revision + 1,
                    revision_digest=latest.revision_digest,
                    action_ids=latest.action_ids,
                ),
                run_id,
                admitted.revision,
                "latest revision",
            ),
            (_publication(first), run_id, admitted.revision, "latest revision"),
            (
                CandidatePublication(
                    candidate_revision=latest.candidate_revision,
                    revision_digest="b" * 64,
                    action_ids=latest.action_ids,
                ),
                run_id,
                admitted.revision,
                "digest",
            ),
            (
                CandidatePublication(
                    candidate_revision=latest.candidate_revision,
                    revision_digest=latest.revision_digest,
                    action_ids=latest.action_ids[:1],
                ),
                run_id,
                admitted.revision,
                "action handles",
            ),
            (
                CandidatePublication(
                    candidate_revision=latest.candidate_revision,
                    revision_digest=latest.revision_digest,
                    action_ids=tuple(reversed(latest.action_ids)),
                ),
                run_id,
                admitted.revision,
                "action handles",
            ),
            (_publication(latest), uuid4(), admitted.revision, "another consultant run"),
        )
        for publication, publication_run_id, expected_revision, message in attempts:
            now = datetime.now(UTC)
            with pytest.raises((ValueError, StaleRevision), match=message):
                await runtime.commit_verified_consultant_result(
                    document_id=document_id,
                    expected_revision=expected_revision,
                    commit=VerifiedConsultantCommit(
                        run_id=publication_run_id,
                        answer_source_id=source_id,
                        started_at=now,
                        completed_at=now,
                        result=_publication_result(source_id, publication),
                    ),
                )
            assert (await runtime.raw_state(document_id)) == before_state
            assert await runtime.reopen_document(document_id) == before_snapshot

        now = datetime.now(UTC)
        with pytest.raises(ValueError, match="baseline revision is stale"):
            _published_candidate_changeset(
                {**before_state, "revision": admitted.revision + 1},
                commit=VerifiedConsultantCommit(
                    run_id=run_id,
                    answer_source_id=source_id,
                    started_at=now,
                    completed_at=now,
                    result=_publication_result(source_id, _publication(latest)),
                ),
                expected_revision=admitted.revision + 1,
            )
        duplicate_publication = CandidatePublication.model_construct(
            candidate_revision=latest.candidate_revision,
            revision_digest=latest.revision_digest,
            action_ids=(latest.action_ids[0], latest.action_ids[0]),
        )
        with pytest.raises(ValueError, match="duplicate candidate publication action ID"):
            _published_candidate_changeset(
                before_state,
                commit=VerifiedConsultantCommit(
                    run_id=run_id,
                    answer_source_id=source_id,
                    started_at=now,
                    completed_at=now,
                    result=_publication_result(source_id, duplicate_publication),
                ),
                expected_revision=admitted.revision,
            )
        assert (await runtime.raw_state(document_id)) == before_state
        assert await runtime.reopen_document(document_id) == before_snapshot

        await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_publication_requires_final_skills_to_include_candidate_skills(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        admitted, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責管理採購作業。",
        )
        receipt = await runtime.stage_candidate_revision(
            document_id=document_id,
            request=_candidate_stage_request(
                run_id=run_id,
                source_id=source_id,
                baseline_revision=admitted.revision,
                skill_id="duty-grouping",
            ),
        )
        before_state = await runtime.raw_state(document_id)
        before_snapshot = await runtime.reopen_document(document_id)
        now = datetime.now(UTC)

        with pytest.raises(ValueError, match="used Skills missing"):
            await runtime.commit_verified_consultant_result(
                document_id=document_id,
                expected_revision=admitted.revision,
                commit=VerifiedConsultantCommit(
                    run_id=run_id,
                    answer_source_id=source_id,
                    started_at=now,
                    completed_at=now,
                    result=_publication_result(
                        source_id,
                        _publication(receipt),
                        skill_id="task-boundary",
                    ),
                ),
            )
        assert (await runtime.raw_state(document_id) == before_state)
        assert await runtime.reopen_document(document_id) == before_snapshot
        await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_candidate_workspace_survives_runtime_reopen_without_snapshot_leakage(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        admitted, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責管理採購作業。",
        )
        assert should_process is True
        catalog_before = await runtime.get_document_catalog_entry(document_id)
        approved_before = admitted.approved_document
        queue_before = admitted.review_queue
        revision_before = admitted.revision

        receipt = await runtime.stage_candidate_revision(
            document_id=document_id,
            request=_candidate_stage_request(
                run_id=run_id,
                source_id=source_id,
                baseline_revision=revision_before,
            ),
        )
        visible_after = await runtime.reopen_document(document_id)
        raw_after = await runtime.raw_state(document_id)
        catalog_after = await runtime.get_document_catalog_entry(document_id)

        assert receipt.status == "applied"
        assert receipt.candidate_revision == 1
        assert visible_after == admitted
        assert "active_candidate" not in visible_after.model_dump(mode="json")
        assert visible_after.approved_document == approved_before
        assert visible_after.review_queue == queue_before
        assert visible_after.revision == revision_before
        assert catalog_after.updated_at == catalog_before.updated_at
        staged = CandidateWorkspace.model_validate(raw_after["active_candidate"])
        assert staged.revision_digest == receipt.revision_digest
        assert tuple(action.action_id for action in staged.changeset.actions) == (
            receipt.action_ids
        )
        assert receipt.actions[0].before == staged.changeset.actions[0].before
        assert receipt.actions[0].after == staged.changeset.actions[0].after
        assert receipt.actions[0].depends_on_action_ids == (
            staged.changeset.actions[0].depends_on_action_ids
        )
        assert receipt.actions[0].supersedes_action_ids == (
            staged.changeset.actions[0].supersedes_action_ids
        )
        assert receipt.actions[0].atomic_subgroup_id == (
            staged.changeset.actions[0].atomic_subgroup_id
        )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        reopened = await runtime.reopen_document(document_id)
        raw_reopened = await runtime.raw_state(document_id)

        assert reopened.approved_document == approved_before
        assert reopened.review_queue == queue_before
        assert reopened.revision == revision_before
        assert CandidateWorkspace.model_validate(raw_reopened["active_candidate"]) == staged
        await runtime.delete_document(document_id)


@pytest.mark.asyncio
async def test_candidate_stage_is_payload_bound_and_failed_stage_keeps_last_success(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        admitted, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責管理採購作業。",
        )
        request = _candidate_stage_request(
            run_id=run_id,
            source_id=source_id,
            baseline_revision=admitted.revision,
        )
        first = await runtime.stage_candidate_revision(
            document_id=document_id,
            request=request,
        )
        replay = await runtime.stage_candidate_revision(
            document_id=document_id,
            request=request,
        )
        raw_before_failure = await runtime.raw_state(document_id)
        snapshot_before_failure = await runtime.reopen_document(document_id)

        assert replay == first
        with pytest.raises(CandidateEditRejected) as rejected:
            await runtime.stage_candidate_revision(
                document_id=document_id,
                request=_candidate_stage_request(
                    run_id=run_id,
                    source_id=source_id,
                    baseline_revision=admitted.revision,
                    base_candidate_revision=1,
                    summary="同一 tool-call ID 的不同內容。",
                ),
            )
        assert rejected.value.baseline_revision == admitted.revision
        assert rejected.value.candidate_revision == first.candidate_revision
        assert rejected.value.issues == (
            "candidate tool call candidate-tool-1 was reused with another payload",
        )
        assert rejected.value.__cause__ is None
        invalid_change = _candidate_wire_change(
            change_ref="invalid",
            operation=DocumentChangeOperation.REVISE,
            target_id=str(uuid4()),
            field=OutputDocumentField.STATEMENT,
            text_value="不可引用未知 Duty",
            duties=(),
        )
        with pytest.raises(CandidateEditRejected) as invalid_rejected:
            await runtime.stage_candidate_revision(
                document_id=document_id,
                request=_candidate_stage_request(
                    run_id=run_id,
                    source_id=source_id,
                    baseline_revision=admitted.revision,
                    base_candidate_revision=1,
                    tool_call_id="candidate-tool-2",
                    changes=(invalid_change,),
                ),
            )
        assert invalid_rejected.value.baseline_revision == admitted.revision
        assert invalid_rejected.value.candidate_revision == first.candidate_revision
        assert invalid_rejected.value.issues == ("unbound entity handle",)
        assert isinstance(invalid_rejected.value.__cause__, CandidateWireMappingError)
        assert str(invalid_rejected.value.__cause__) == "unbound entity handle"

        assert (await runtime.raw_state(document_id))["active_candidate"] == raw_before_failure["active_candidate"]
        snapshot_after_failure = await runtime.reopen_document(document_id)
        assert snapshot_after_failure.approved_document == snapshot_before_failure.approved_document
        assert snapshot_after_failure.review_queue == snapshot_before_failure.review_queue


@pytest.mark.asyncio
async def test_candidate_lifecycle_preserves_failed_retry_and_clears_on_correction(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        admitted, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責管理採購作業。",
        )
        first_request = _candidate_stage_request(
            run_id=run_id,
            source_id=source_id,
            baseline_revision=admitted.revision,
        )
        first_receipt = await runtime.stage_candidate_revision(
            document_id=document_id,
            request=first_request,
        )
        staged = (await runtime.raw_state(document_id))["active_candidate"]
        approved_before = admitted.approved_document
        queue_before = admitted.review_queue

        await runtime.mark_consultant_run_failed(
            document_id=document_id,
            run_id=run_id,
            error_code="model_unavailable",
        )
        assert (await runtime.raw_state(document_id))["active_candidate"] == staged
        _, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責管理採購作業。",
        )
        assert should_process is True
        assert (await runtime.raw_state(document_id))["active_candidate"] == staged

        replay = await runtime.stage_candidate_revision(
            document_id=document_id,
            request=first_request,
        )
        replacement = await runtime.stage_candidate_revision(
            document_id=document_id,
            request=_candidate_stage_request(
                run_id=run_id,
                source_id=source_id,
                baseline_revision=admitted.revision,
                base_candidate_revision=1,
                tool_call_id="candidate-tool-2",
                summary="重新整理同一 run 的候選文件。",
            ),
        )
        after_replacement = await runtime.reopen_document(document_id)
        active_replacement = CandidateWorkspace.model_validate(
            (await runtime.raw_state(document_id))["active_candidate"]
        )

        assert replay == first_receipt
        assert replacement.candidate_revision == 2
        assert active_replacement.candidate_revision == 2
        assert active_replacement.baseline_revision == admitted.revision
        assert after_replacement.approved_document == approved_before
        assert after_replacement.review_queue == queue_before

        await runtime.mark_consultant_run_failed(
            document_id=document_id,
            run_id=run_id,
            error_code="invalid_employee_input",
        )
        corrected, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=uuid4(),
            source_id=uuid4(),
            text="更正：我是每週管理採購作業。",
            supersedes_source_id=source_id,
        )

        assert should_process is True
        assert corrected.latest_run is not None
        assert (await runtime.raw_state(document_id))["active_candidate"] is None


@pytest.mark.asyncio
async def test_store_first_correction_blocks_old_failed_run_until_retry_reconciles(
    consultant_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = uuid4()
    failed_run_id = uuid4()
    failed_source_id = uuid4()
    correction_run_id = uuid4()
    correction_source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        admitted, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=failed_run_id,
            source_id=failed_source_id,
            text="我負責管理採購作業。",
        )
        request = _candidate_stage_request(
            run_id=failed_run_id,
            source_id=failed_source_id,
            baseline_revision=admitted.revision,
        )
        await runtime.stage_candidate_revision(
            document_id=document_id,
            request=request,
        )
        await runtime.mark_consultant_run_failed(
            document_id=document_id,
            run_id=failed_run_id,
            error_code="invalid_employee_input",
        )
        failed_state = await runtime.raw_state(document_id)
        active_candidate = failed_state["active_candidate"]
        approved_before = admitted.approved_document
        queue_before = admitted.review_queue

        async def fail_after_store(_source: EmployeeSource) -> None:
            raise RuntimeError("correction-after-store")

        monkeypatch.setattr(runtime, "_after_source_store", fail_after_store)
        with pytest.raises(RuntimeError, match="correction-after-store"):
            await runtime.admit_employee_answer(
                document_id=document_id,
                run_id=correction_run_id,
                source_id=correction_source_id,
                text="更正：我是每週管理採購作業。",
                supersedes_source_id=failed_source_id,
            )

        failed_source = await runtime.get_source(document_id, failed_source_id)
        pending_correction = await runtime.get_source(
            document_id, correction_source_id
        )
        assert failed_source.validity is SourceValidity.SUPERSEDED
        assert pending_correction.processing_status is SourceProcessingStatus.PENDING

        with pytest.raises(PendingSourceRequiresReconciliation):
            await runtime.admit_employee_answer(
                document_id=document_id,
                run_id=failed_run_id,
                source_id=failed_source_id,
                text="我負責管理採購作業。",
            )

        rejected_restart_state = await runtime.raw_state(document_id)
        rejected_restart = await runtime.reopen_document(document_id)
        assert rejected_restart_state["latest_run"]["status"] == RunStatus.FAILED.value
        assert rejected_restart_state["active_candidate"] == active_candidate
        assert rejected_restart.approved_document == approved_before
        assert rejected_restart.review_queue == queue_before
        with pytest.raises(ActiveConsultantRun):
            await runtime.stage_candidate_revision(
                document_id=document_id,
                request=request,
            )

        monkeypatch.setattr(runtime, "_after_source_store", runtime._noop_source_hook)
        corrected, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=correction_run_id,
            source_id=correction_source_id,
            text="更正：我是每週管理採購作業。",
            supersedes_source_id=failed_source_id,
        )

        assert should_process is True
        assert corrected.latest_run is not None
        assert corrected.latest_run["run_id"] == str(correction_run_id)
        assert corrected.approved_document == approved_before
        assert corrected.review_queue == queue_before
        assert (await runtime.raw_state(document_id))["active_candidate"] is None
        assert (
            await runtime.get_source(document_id, correction_source_id)
        ).processing_status is SourceProcessingStatus.COMMITTED


@pytest.mark.asyncio
async def test_candidate_exact_replay_revalidates_persisted_evidence_source(
    consultant_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    correction_source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        admitted, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責管理採購作業。",
        )
        request = _candidate_stage_request(
            run_id=run_id,
            source_id=source_id,
            baseline_revision=admitted.revision,
        )
        await runtime.stage_candidate_revision(
            document_id=document_id,
            request=request,
        )
        staged = (await runtime.raw_state(document_id))["active_candidate"]

        async def fail_after_store(_source: EmployeeSource) -> None:
            raise RuntimeError("correction-after-store")

        monkeypatch.setattr(runtime, "_after_source_store", fail_after_store)
        with pytest.raises(RuntimeError, match="correction-after-store"):
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=correction_source_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="更正：我是每週管理採購作業。",
                supersedes_source_id=source_id,
            )

        with pytest.raises(CandidateEditRejected) as rejected:
            await runtime.stage_candidate_revision(
                document_id=document_id,
                request=request,
            )
        assert rejected.value.baseline_revision == admitted.revision
        assert rejected.value.candidate_revision == CandidateWorkspace.model_validate(
            staged
        ).candidate_revision
        assert rejected.value.issues == (
            f"source {source_id} was superseded before candidate staging",
        )
        assert isinstance(rejected.value.__cause__, SourceConflict)
        assert str(rejected.value.__cause__) == (
            f"source {source_id} was superseded before candidate staging"
        )

        after_replay = await runtime.reopen_document(document_id)
        assert (await runtime.raw_state(document_id))["active_candidate"] == staged
        assert after_replay.approved_document == admitted.approved_document
        assert after_replay.review_queue == admitted.review_queue


@pytest.mark.asyncio
async def test_candidate_exact_replay_revalidates_its_own_receipt_evidence(
    consultant_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_a_id = uuid4()
    source_b_id = uuid4()
    correction_source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        admitted, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_a_id,
            text="我負責管理採購作業。",
        )
        source_b_snapshot = await runtime.record_employee_source(
            document_id=document_id,
            source_id=source_b_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="我每週檢視採購需求。",
        )
        first_request = _candidate_stage_request(
            run_id=run_id,
            source_id=source_a_id,
            baseline_revision=source_b_snapshot.revision,
            tool_call_id="candidate-tool-a",
        )
        first = await runtime.stage_candidate_revision(
            document_id=document_id,
            request=first_request,
        )
        second_request = _candidate_stage_request(
            run_id=run_id,
            source_id=source_b_id,
            baseline_revision=source_b_snapshot.revision,
            base_candidate_revision=1,
            tool_call_id="candidate-tool-b",
            summary="以第二則來源更新候選文件。",
        )
        second = await runtime.stage_candidate_revision(
            document_id=document_id,
            request=second_request,
        )

        async def fail_after_store(_source: EmployeeSource) -> None:
            raise RuntimeError("correction-after-store")

        monkeypatch.setattr(runtime, "_after_source_store", fail_after_store)
        with pytest.raises(RuntimeError, match="correction-after-store"):
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=correction_source_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="更正：我改為每日管理採購作業。",
                supersedes_source_id=source_b_id,
            )

        raw_before_replay = await runtime.raw_state(document_id)
        snapshot_before_replay = await runtime.reopen_document(document_id)
        active_before_replay = CandidateWorkspace.model_validate(
            raw_before_replay["active_candidate"]
        )
        assert active_before_replay.candidate_revision == second.candidate_revision == 2
        assert active_before_replay.changeset.source_ids == (source_b_id,)

        now = datetime.now(UTC)
        with pytest.raises(SourceConflict, match=str(source_b_id)):
            await runtime.commit_verified_consultant_result(
                document_id=document_id,
                expected_revision=source_b_snapshot.revision,
                commit=VerifiedConsultantCommit(
                    run_id=run_id,
                    answer_source_id=source_a_id,
                    started_at=now,
                    completed_at=now,
                    result=_publication_result(source_a_id, _publication(second)),
                ),
            )
        assert (await runtime.raw_state(document_id)) == raw_before_replay
        assert await runtime.reopen_document(document_id) == snapshot_before_replay

        assert (
            await runtime.stage_candidate_revision(
                document_id=document_id,
                request=first_request,
            )
            == first
        )
        with pytest.raises(CandidateEditRejected) as rejected:
            await runtime.stage_candidate_revision(
                document_id=document_id,
                request=second_request,
            )
        assert rejected.value.baseline_revision == source_b_snapshot.revision
        assert rejected.value.candidate_revision == second.candidate_revision
        assert rejected.value.issues == (
            f"source {source_b_id} was superseded before candidate staging",
        )
        assert isinstance(rejected.value.__cause__, SourceConflict)
        assert str(rejected.value.__cause__) == (
            f"source {source_b_id} was superseded before candidate staging"
        )

        snapshot_after_replay = await runtime.reopen_document(document_id)
        assert first.candidate_revision == 1
        assert (await runtime.raw_state(document_id)) == raw_before_replay
        assert snapshot_after_replay.approved_document == snapshot_before_replay.approved_document
        assert snapshot_after_replay.review_queue == snapshot_before_replay.review_queue


@pytest.mark.asyncio
async def test_direct_edit_clears_candidate_workspace(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        admitted, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責管理採購作業。",
        )
        await runtime.stage_candidate_revision(
            document_id=document_id,
            request=_candidate_stage_request(
                run_id=run_id,
                source_id=source_id,
                baseline_revision=admitted.revision,
            ),
        )

        edited = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=admitted.revision,
            document=admitted.approved_document.model_copy(
                update={"job_title": "採購管理師"}
            ),
            source_id=uuid4(),
        )

        assert edited.approved_document.job_title == "採購管理師"
        assert (await runtime.raw_state(document_id))["active_candidate"] is None


@pytest.mark.parametrize(
    "decision",
    ("accept_changes", "edit_and_accept_changes", "reject_changes", "defer_changes"),
)
@pytest.mark.asyncio
async def test_every_employee_review_decision_clears_candidate_workspace(
    consultant_database_url: str,
    decision: str,
) -> None:
    document_id = uuid4()
    evidence_source_id = uuid4()
    candidate_source_id = uuid4()
    now = datetime.now(UTC)
    basis = AnalysisBasis(
        source_ids=(evidence_source_id,),
        skill_ids=("task-boundary",),
    )
    result = ConsultantResult(
        visible_reply="我整理了一項 Duty 建議。",
        reply_basis=basis,
        used_skill_ids=("task-boundary",),
        sufficiency=SufficiencyRecommendation(
            currently_enough=False,
            reason="仍有工作待盤點。",
            remaining_gap_reasons=(GapReason.WORK_COVERAGE_MISSING,),
            continuing_benefit="繼續訪談可補齊工作。",
            basis=basis,
        ),
    )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        proposal_run_id = uuid4()
        sourced, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=proposal_run_id,
            source_id=evidence_source_id,
            text="我負責執行採購作業。",
        )
        proposed = await _stage_and_publish(
            runtime,
            document_id=document_id,
            run_id=proposal_run_id,
            source_id=evidence_source_id,
            baseline_revision=sourced.revision,
            result=result,
        )
        bundle = proposed.document_review.bundles[0]
        old_action = bundle.actions[0]
        candidate_run_id = uuid4()
        admitted, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=candidate_run_id,
            source_id=candidate_source_id,
            text="候選版本還要補上供應商管理。",
        )
        await runtime.stage_candidate_revision(
            document_id=document_id,
            request=_candidate_stage_request(
                run_id=candidate_run_id,
                source_id=candidate_source_id,
                baseline_revision=admitted.revision,
                changes=(
                    _candidate_wire_change(
                        depends_on_action_ids=(old_action.action_id,),
                    ),
                ),
            ),
        )
        kwargs: dict[str, object] = {}
        if decision == "edit_and_accept_changes":
            assert isinstance(old_action.after, dict)
            kwargs["edited_after_by_action_id"] = {
                old_action.action_id: {
                    **old_action.after,
                    "statement": "員工修訂後的採購作業",
                }
            }
            kwargs["source_id"] = uuid4()
        elif decision == "reject_changes":
            kwargs["rejection_reason"] = "這不是我的主要工作。"

        await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=admitted.revision,
            action=decision,
            changeset_id=bundle.changeset_id,
            action_ids=(old_action.action_id,),
            **kwargs,
        )

        assert (await runtime.raw_state(document_id))["active_candidate"] is None


@pytest.mark.asyncio
async def test_setup_is_strict_and_does_not_create_a_second_artifact_store(
    consultant_database_url: str,
) -> None:
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.setup()
        await runtime.setup()
        invariants = runtime.connection_invariants()
        assert invariants == {
            "saver_autocommit": True,
            "saver_dict_rows": True,
            "store_autocommit": True,
            "store_dict_rows": True,
            "strict_msgpack": True,
        }

    async with await psycopg.AsyncConnection.connect(
        consultant_database_url, autocommit=True
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name LIKE 'consultant_%'
                ORDER BY table_name
                """
            )
            assert [row[0] for row in await cursor.fetchall()] == [
                "consultant_documents"
            ]


@pytest.mark.asyncio
async def test_strict_serializer_rejects_an_unapproved_runtime_type(
    consultant_database_url: str,
) -> None:
    class UnsafeValue:
        pass

    class UnsafeState(TypedDict, total=False):
        payload: object

    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        builder = StateGraph(UnsafeState)
        builder.add_node("persist", lambda state: state)
        builder.add_edge(START, "persist")
        builder.add_edge("persist", END)
        graph = builder.compile(checkpointer=runtime.saver)

        with pytest.raises(TypeError, match="not msgpack serializable"):
            await graph.ainvoke({"payload": UnsafeValue()}, config)
        await runtime.saver.adelete_thread(thread_id)


@pytest.mark.asyncio
async def test_completed_checkpoint_opens_under_an_additive_state_schema(
    consultant_database_url: str,
) -> None:
    class StateV1(TypedDict, total=False):
        document_id: str
        revision: int

    class StateV2(StateV1, total=False):
        schema_version: int
        future_projection: dict[str, str]

    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        v1_builder = StateGraph(StateV1)
        v1_builder.add_node("persist", lambda state: state)
        v1_builder.add_edge(START, "persist")
        v1_builder.add_edge("persist", END)
        v1_graph = v1_builder.compile(checkpointer=runtime.saver)
        await v1_graph.ainvoke({"document_id": thread_id, "revision": 3}, config)

        v2_builder = StateGraph(StateV2)
        v2_builder.add_node(
            "upgrade",
            lambda _state: {
                "schema_version": 2,
                "future_projection": {"status": "available"},
            },
        )
        v2_builder.add_edge(START, "upgrade")
        v2_builder.add_edge("upgrade", END)
        v2_graph = v2_builder.compile(checkpointer=runtime.saver)

        reopened = await v2_graph.aget_state(config)
        assert reopened.values == {"document_id": thread_id, "revision": 3}
        await v2_graph.ainvoke({}, config)
        upgraded = await v2_graph.aget_state(config)
        assert upgraded.values["document_id"] == thread_id
        assert upgraded.values["schema_version"] == 2
        assert upgraded.values["future_projection"] == {"status": "available"}
        await runtime.saver.adelete_thread(thread_id)


async def _storage_bytes(database_url: str, document_id: UUID) -> int:
    prefix = ".".join(("caliburn", "consultant", str(document_id), "sources"))
    thread_id = str(document_id)
    async with await psycopg.AsyncConnection.connect(
        database_url, autocommit=True
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT
                    COALESCE((SELECT SUM(pg_column_size(checkpoint) + pg_column_size(metadata))
                              FROM checkpoints WHERE thread_id = %s), 0)
                  + COALESCE((SELECT SUM(COALESCE(octet_length(blob), 0))
                              FROM checkpoint_blobs WHERE thread_id = %s), 0)
                  + COALESCE((SELECT SUM(COALESCE(octet_length(blob), 0))
                              FROM checkpoint_writes WHERE thread_id = %s), 0)
                  + COALESCE((SELECT SUM(pg_column_size(value))
                              FROM store WHERE prefix = %s), 0)
                """,
                (thread_id, thread_id, thread_id, prefix),
            )
            row = await cursor.fetchone()
            assert row is not None
            return int(row[0])


@pytest.mark.asyncio
async def test_store_owned_source_payload_has_linear_growth(
    consultant_database_url: str,
) -> None:
    short_document = uuid4()
    long_document = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(short_document, title="短")
        await runtime.create_document(long_document, title="長")
        for document_id, count in ((short_document, 12), (long_document, 24)):
            for index in range(count):
                await runtime.record_employee_source(
                    document_id=document_id,
                    source_id=uuid4(),
                    kind=EmployeeSourceKind.EMPLOYEE_TURN,
                    text=f"{index:03d}:" + ("員工逐字工作內容。" * 80),
                )

        short_bytes = await _storage_bytes(consultant_database_url, short_document)
        long_bytes = await _storage_bytes(consultant_database_url, long_document)
        assert 1.4 < long_bytes / short_bytes < 2.6
        assert "員工逐字工作內容" not in json.dumps(
            await runtime.raw_state(long_document), ensure_ascii=False, default=str
        )

        await runtime.delete_document(short_document)
        await runtime.delete_document(long_document)


@pytest.mark.asyncio
async def test_checked_candidate_stale_digest_run_and_baseline_leave_review_queue_empty(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    direct_edit_source_id = uuid4()
    later_direct_edit_source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="候選 publication stale")
        recorded = await runtime.record_employee_source(
            document_id=document_id,
            source_id=source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="員工說明採購工作。",
        )
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=recorded.revision,
            document=_document(document_id),
            source_id=direct_edit_source_id,
        )
        admitted, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=uuid4(),
            text="請檢查職務標題。",
        )
        assert should_process is True
        assert admitted.revision == seeded.revision + 1
        current_sources = await runtime.list_sources(document_id)
        catalog = WorkspaceCatalog.from_snapshot(
            admitted.approved_document,
            sources=current_sources,
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
            tool_call_id="stale-check-001",
            selected_skill_ids=CONSULTANT_SKILL_IDS,
            loaded_skill_ids=CONSULTANT_SKILL_IDS,
        )
        assert checked.status == "checked", checked.issues
        assert (await runtime.reopen_document(document_id)).review_queue == {}

        mutated = dict(files)
        mutated[header_path] = mutated[header_path].replace(
            "資深採購管理專員", "後續修改的標題"
        )
        with pytest.raises(CandidatePublicationStale, match="digest"):
            await runtime.publish_checked_candidate(
                document_id=document_id,
                run_id=run_id,
                files=mutated,
            )
        assert (await runtime.reopen_document(document_id)).review_queue == {}

        with pytest.raises(CandidatePublicationStale, match="run"):
            await runtime.publish_checked_candidate(
                document_id=document_id,
                run_id=uuid4(),
                files=files,
            )
        assert (await runtime.reopen_document(document_id)).review_queue == {}

        current = await runtime.reopen_document(document_id)
        await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=current.revision,
            document=current.approved_document.model_copy(
                update={"job_title": "員工已修正的標題"}
            ),
            source_id=later_direct_edit_source_id,
        )
        with pytest.raises(CandidatePublicationStale, match="baseline"):
            await runtime.publish_checked_candidate(
                document_id=document_id,
                run_id=run_id,
                files=files,
            )
        assert (await runtime.reopen_document(document_id)).review_queue == {}
