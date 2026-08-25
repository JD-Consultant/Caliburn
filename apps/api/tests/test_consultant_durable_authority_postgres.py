from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, TypedDict
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from deepagents.backends import StoreBackend
from langgraph.graph import END, START, StateGraph

from app.adapters.langgraph.postgres import (
    DocumentNotFound,
    IdempotencyConflict,
    PendingSourceRequiresReconciliation,
    SourceConflict,
    StaleRevision,
    open_postgres_consultant_runtime,
)
from app.consultant.document_authority import apply_document_actions
from app.consultant.interview import VerifiedConsultantCommit
from app.consultant.skill_backend import CONSULTANT_SKILL_IDS
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
    ApprovedOpksItem,
    ApprovedOpksKind,
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
from app.consultant.workspace_resources import (
    WorkspaceCatalog,
    WorkspaceDutyResource,
    WorkspaceEvidenceReference,
    WorkspaceTaskResource,
    canonical_resource_json,
    project_workspace_files,
)
from app.consultant.workspace_authority import (
    WorkspaceAuthorityError,
    WorkspaceAuthorityService,
    WorkspaceDecisionKind,
    WorkspaceReviewCommand,
)
from app.consultant.workspace_state import StoreBackedWorkspace, WorkspaceValidationStatus
from app.consultant.workspace_validation import WorkspaceValidationService


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


async def _validated_workspace_review(
    runtime: Any,
    document_id: UUID,
) -> tuple[Any, StoreBackedWorkspace, Any, Any]:
    workspace = StoreBackedWorkspace(
        store=runtime.store,
        document_id=document_id,
    )
    snapshot = await runtime._snapshot(document_id)
    sources = await runtime.list_sources(document_id)
    validator = WorkspaceValidationService(
        workspace=workspace,
        catalog=WorkspaceCatalog.from_snapshot(
            snapshot.approved_document,
            sources=sources,
        ),
        source_loader=lambda: runtime.list_sources(document_id),
        selected_skill_ids=CONSULTANT_SKILL_IDS,
    )
    validation = await validator.validate_current(
        loaded_skill_ids=CONSULTANT_SKILL_IDS,
    )
    assert validation.document is not None
    _, _, workspace_snapshot, projection = await WorkspaceAuthorityService(
        runtime
    )._review_context(document_id)
    assert not projection.diagnostics
    return snapshot, workspace, workspace_snapshot, projection


def _workspace_command(
    *,
    document_id: UUID,
    snapshot: Any,
    workspace_snapshot: Any,
    group: Any,
    decision: WorkspaceDecisionKind,
    action_id: UUID,
    edited_after: str | None = None,
    reason: str | None = None,
) -> WorkspaceReviewCommand:
    edited = {action_id: edited_after} if edited_after is not None else {}
    return WorkspaceReviewCommand(
        command_id=uuid4(),
        document_id=document_id,
        decision=decision,
        approved_revision=snapshot.revision,
        workspace_generation=workspace_snapshot.manifest.generation,
        workspace_digest=workspace_snapshot.manifest.resource_digest,
        changeset_id=group.changeset.changeset_id,
        group_digest=group.group_digest,
        selected_action_ids=(action_id,),
        edited_after_by_action_id=edited,
        reason=reason,
    )


async def _edit_task_statement(
    workspace: StoreBackedWorkspace,
    value: str,
) -> None:
    await _edit_task_field(workspace, "statement", value)


async def _edit_task_field(
    workspace: StoreBackedWorkspace,
    field: str,
    value: str,
) -> None:
    path = "/workspace/tasks/task-001.json"
    current = await workspace.read_snapshot()
    before = json.loads(current.files[path])[field]
    result = await workspace.backend.aedit(
        path,
        json.dumps(before, ensure_ascii=False),
        json.dumps(value, ensure_ascii=False),
    )
    assert result.error is None


@pytest.mark.asyncio
async def test_store_snapshot_projects_valid_workspace_progress_and_review_counts(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Workspace progress")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=seeded.approved_document,
            approved_revision=seeded.revision,
        )
        await _edit_task_statement(workspace, "AI 候選工作內容")
        await _validated_workspace_review(runtime, document_id)

        snapshot = await runtime.reopen_document(document_id)

        assert snapshot.approved_document.tasks[0].statement != "AI 候選工作內容"
        assert snapshot.semantic_progress.currently_known_work_count == 1
        assert snapshot.semantic_progress.employee_decisions.pending == 1
        assert snapshot.semantic_progress.coverage[0].status == (
            "awaiting_employee_decision"
        )


@pytest.mark.asyncio
async def test_pending_task_review_survives_reopen_and_unrelated_ai_workspace_mutation(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    task_statement = "AI 尚待確認的工作內容"
    updated_job_title = "AI 更新的採購管理職稱"

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Durable pending review")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=seeded.approved_document,
            approved_revision=seeded.revision,
        )
        await _edit_task_statement(workspace, task_statement)
        _, _, _, projection = await _validated_workspace_review(runtime, document_id)
        task_group = next(
            group
            for group in projection.groups
            if any(action.path.endswith("/statement") for action in group.actions)
        )
        task_semantic_fingerprint = task_group.semantic_fingerprint

        assert {action.status.value for action in task_group.actions} == {"pending"}
        assert not await runtime.store.asearch(
            runtime.workspace_decision_namespace(document_id),
            limit=1000,
        )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        reopened = await runtime.reopen_document(document_id)
        assert any(
            action.path.endswith("/statement") and action.status.value == "pending"
            for bundle in reopened.document_review.bundles
            for action in bundle.actions
        )

        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        before_mutation = await workspace.read_snapshot()
        header_path = "/workspace/header.json"
        previous_job_title = json.loads(before_mutation.files[header_path])["job_title"]
        edit = await workspace.backend.aedit(
            header_path,
            json.dumps(previous_job_title, ensure_ascii=False),
            json.dumps(updated_job_title, ensure_ascii=False),
        )
        assert edit.error is None

        _, _, _, projection = await _validated_workspace_review(runtime, document_id)
        task_group = next(
            group
            for group in projection.groups
            if any(action.path.endswith("/statement") for action in group.actions)
        )
        header_group = next(
            group
            for group in projection.groups
            if any(action.path == "/job_title" for action in group.actions)
        )

        assert task_group.semantic_fingerprint == task_semantic_fingerprint
        assert {action.status.value for action in task_group.actions} == {"pending"}
        assert {action.status.value for action in header_group.actions} == {"pending"}
        assert not await runtime.store.asearch(
            runtime.workspace_decision_namespace(document_id),
            limit=1000,
        )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        reopened = await runtime.reopen_document(document_id)
        task_actions = tuple(
            action
            for bundle in reopened.document_review.bundles
            for action in bundle.actions
            if action.path.endswith("/statement")
        )

        assert reopened.current_document.tasks[0].statement == task_statement
        assert reopened.current_document.job_title == updated_job_title
        assert reopened.approved_document.tasks[0].statement != task_statement
        assert task_actions
        assert {action.status.value for action in task_actions} == {"pending"}
        assert not await runtime.store.asearch(
            runtime.workspace_decision_namespace(document_id),
            limit=1000,
        )


@pytest.mark.asyncio
async def test_deep_agents_store_backend_is_application_accessible_and_restart_safe(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    other_document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="Store workspace")
        await runtime.create_document(other_document_id, title="Isolated workspace")
        first = StoreBackend(
            namespace=lambda _runtime: runtime.workspace_namespace(document_id),
            store=runtime.store,
        )

        assert (await first.awrite("/workspace/header.json", "{}\n")).error is None
        assert (
            await first.aedit(
                "/workspace/header.json",
                "{}",
                '{"job_title":"採購"}',
            )
        ).error is None

        reopened = StoreBackend(
            namespace=lambda _runtime: runtime.workspace_namespace(document_id),
            store=runtime.store,
        )
        reopened_read = await reopened.aread("/workspace/header.json")
        assert reopened_read.error is None
        assert reopened_read.file_data is not None
        assert reopened_read.file_data["content"] == '{"job_title":"採購"}\n'

        isolated = StoreBackend(
            namespace=lambda _runtime: runtime.workspace_namespace(other_document_id),
            store=runtime.store,
        )
        isolated_read = await isolated.aread("/workspace/header.json")
        assert isolated_read.error is None
        assert isolated_read.file_data is not None
        assert isolated_read.file_data["content"] != '{"job_title":"採購"}\n'
        assert (await reopened.adelete("/workspace/header.json")).error is None
        assert (await reopened.aread("/workspace/header.json")).error is not None


@pytest.mark.asyncio
async def test_store_backend_workspace_survives_postgres_runtime_restart_byte_exact(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    other_document_id = uuid4()
    new_task_path = "/workspace/tasks/task-new-001.json"
    new_task = (
        '{"handle":"task-new-001","statement":"追蹤交期",'
        '"action":"追蹤","object":"交期"}\n'
    )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Store workspace")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=seeded.approved_document,
            approved_revision=seeded.revision,
        )
        assert (await workspace.backend.awrite(new_task_path, new_task)).error is None
        before_restart = await workspace.read_snapshot()
        approved_before = await runtime.export_approved_document(document_id)

        other = await runtime.create_document(other_document_id, title="Other workspace")
        other_workspace = StoreBackedWorkspace(
            store=runtime.store,
            document_id=other_document_id,
        )
        await other_workspace.ensure_initialized(
            approved_document=other.approved_document,
            approved_revision=other.revision,
        )
        assert new_task_path not in (await other_workspace.read_snapshot()).files

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        reopened = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        after_restart = await reopened.read_snapshot()

        assert after_restart.files == before_restart.files
        assert after_restart.files[new_task_path] == new_task
        assert await runtime.export_approved_document(document_id) == approved_before
        assert new_task_path not in (
            await StoreBackedWorkspace(
                store=runtime.store,
                document_id=other_document_id,
            ).read_snapshot()
        ).files


@pytest.mark.asyncio
async def test_same_document_workspace_preserves_scratch_across_turn_bindings(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    scratch_path = "/workspace/opks/o/scratch-001.json"

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Persistent workspace")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        first = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await first.ensure_initialized(
            approved_document=seeded.approved_document,
            approved_revision=seeded.revision,
        )
        assert (await first.backend.awrite(scratch_path, '{"text":"first-turn"}\n')).error is None
        assert (await first.backend.aread(scratch_path)).file_data is not None

        second = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        reread = await second.backend.aread(scratch_path)
        assert reread.error is None
        assert reread.file_data is not None
        assert "first-turn" in reread.file_data["content"]


@pytest.mark.asyncio
async def test_direct_edit_rebases_against_ai_workspace_without_reseeding(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    employee_source_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Direct rebase")
        approved = _document(document_id)
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=approved,
            source_id=source_id,
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=seeded.approved_document,
            approved_revision=seeded.revision,
        )
        task_path = "/workspace/tasks/task-001.json"
        task_before = (await workspace.read_snapshot()).files[task_path]
        assert (await workspace.backend.aedit(
            task_path,
            '"檢查缺料並安排採購"',
            '"AI工作B"',
        )).error is None

        employee_document = approved.model_copy(
            update={
                "tasks": (
                    approved.tasks[0].model_copy(update={"statement": "員工C"}),
                )
            }
        )
        result = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=seeded.revision,
            document=employee_document,
            source_id=employee_source_id,
        )

        assert result.approved_document.tasks[0].statement == "員工C"
        snapshot = await workspace.read_snapshot()
        assert snapshot.files[task_path] != task_before
        assert '"statement": "AI工作B"' in snapshot.files[task_path]
        assert snapshot.manifest.validation_status is WorkspaceValidationStatus.CONFLICTED
        assert any(
            diagnostic.code == "workspace-rebase-conflict"
            for diagnostic in snapshot.manifest.diagnostics
        )
        assert result.document_review.workspace_generation == snapshot.manifest.generation
        assert result.document_review.workspace_status == "conflicted"
        review_snapshot, _, review_workspace, projection = await _validated_workspace_review(
            runtime,
            document_id,
        )
        conflicted_groups = [group for group in projection.groups if group.diagnostics]
        assert len(conflicted_groups) == 1
        conflicted_group = conflicted_groups[0]
        reject = _workspace_command(
            document_id=document_id,
            snapshot=review_snapshot,
            workspace_snapshot=review_workspace,
            group=conflicted_group,
            decision=WorkspaceDecisionKind.REJECT,
            action_id=conflicted_group.actions[0].action_id,
            reason="拒絕 AI working 差異",
        )
        rejected = await runtime.decide_workspace_changes(reject)
        assert rejected.approved_document.tasks[0].statement == "員工C"
        converged = await workspace.read_snapshot()
        assert json.loads(converged.files[task_path])["statement"] == "員工C"
        assert converged.manifest.validation_status is WorkspaceValidationStatus.VALID
        assert not converged.manifest.diagnostics


@pytest.mark.asyncio
async def test_workspace_authority_applies_partial_decisions_and_exact_replay(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Workspace authority")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=seeded.approved_document,
            approved_revision=seeded.revision,
        )
        task_path = "/workspace/tasks/task-001.json"

        await _edit_task_statement(workspace, "AI接受")
        snapshot, _, workspace_snapshot, projection = await _validated_workspace_review(
            runtime,
            document_id,
        )
        assert len(projection.groups) == 1
        group = projection.groups[0]
        action = group.actions[0]
        accept = _workspace_command(
            document_id=document_id,
            snapshot=snapshot,
            workspace_snapshot=workspace_snapshot,
            group=group,
            decision=WorkspaceDecisionKind.ACCEPT,
            action_id=action.action_id,
            reason="員工接受",
        )
        accepted = await runtime.decide_workspace_changes(accept)
        assert accepted.approved_document.tasks[0].statement == "AI接受"
        assert json.loads((await workspace.read_snapshot()).files[task_path])["statement"] == "AI接受"
        assert (
            await runtime.store.aget(
                runtime.workspace_metadata_namespace(document_id),
                f"rebase:{accept.command_id}",
            )
            is None
        )
        replayed = await runtime.decide_workspace_changes(accept)
        assert replayed == accepted
        with pytest.raises(WorkspaceAuthorityError, match="reused"):
            await runtime.decide_workspace_changes(accept.model_copy(update={"reason": "另一個理由"}))

        await _edit_task_statement(workspace, "AI拒絕")
        snapshot, _, workspace_snapshot, projection = await _validated_workspace_review(
            runtime,
            document_id,
        )
        group = projection.groups[0]
        action = group.actions[0]
        reject = _workspace_command(
            document_id=document_id,
            snapshot=snapshot,
            workspace_snapshot=workspace_snapshot,
            group=group,
            decision=WorkspaceDecisionKind.REJECT,
            action_id=action.action_id,
            reason="不符合目前職務邊界",
        )
        rejected = await runtime.decide_workspace_changes(reject)
        assert rejected.approved_document.tasks[0].statement == "AI接受"
        rejected_workspace = await workspace.read_snapshot()
        expected_files = project_workspace_files(
            rejected.approved_document,
            handle_registry=rejected_workspace.manifest.entity_ids_by_handle,
        ).files
        assert json.loads(rejected_workspace.files[task_path]) == json.loads(
            expected_files[task_path]
        )

        await _edit_task_statement(workspace, "AI編輯前")
        snapshot, _, workspace_snapshot, projection = await _validated_workspace_review(
            runtime,
            document_id,
        )
        group = projection.groups[0]
        action = group.actions[0]
        edit_accept = _workspace_command(
            document_id=document_id,
            snapshot=snapshot,
            workspace_snapshot=workspace_snapshot,
            group=group,
            decision=WorkspaceDecisionKind.EDIT_ACCEPT,
            action_id=action.action_id,
            edited_after="員工編輯後",
            reason="員工修訂後接受",
        )
        edited = await runtime.decide_workspace_changes(edit_accept)
        assert edited.approved_document.tasks[0].statement == "員工編輯後"
        assert json.loads((await workspace.read_snapshot()).files[task_path])["statement"] == "員工編輯後"
        sources = await runtime.list_sources(document_id)
        direct_sources = [
            source
            for source in sources
            if source.kind is EmployeeSourceKind.DIRECT_EDIT
            and source.processing_status is SourceProcessingStatus.COMMITTED
            and source.text == "員工編輯後"
        ]
        assert len(direct_sources) == 1
        assert direct_sources[0].positions[0].document_path == action.path


@pytest.mark.asyncio
async def test_partial_accept_keeps_sparse_workspace_handles_restart_safe(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    source_text = "我負責供應管理，平常會確認庫存，也會追蹤進度。"

    def evidence(quote: str) -> tuple[WorkspaceEvidenceReference, ...]:
        return (
            WorkspaceEvidenceReference(
                source_handle="source-001",
                quote=quote,
                occurrence=1,
                skill_ids=("task-boundary",),
            ),
        )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Sparse handles")
        await runtime.record_employee_source(
            document_id=document_id,
            source_id=source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text=source_text,
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=created.approved_document,
            approved_revision=created.revision,
        )
        resources = {
            "/workspace/duties/duty-001.json": canonical_resource_json(
                WorkspaceDutyResource(
                    handle="duty-001",
                    statement="供應管理",
                    evidence=evidence("供應管理"),
                )
            ),
            "/workspace/tasks/task-001.json": canonical_resource_json(
                WorkspaceTaskResource(
                    handle="task-001",
                    duty_handle="duty-001",
                    statement="確認庫存",
                    action="確認",
                    object="庫存",
                    evidence=evidence("確認庫存"),
                )
            ),
            "/workspace/tasks/task-002.json": canonical_resource_json(
                WorkspaceTaskResource(
                    handle="task-002",
                    duty_handle="duty-001",
                    statement="追蹤進度",
                    action="追蹤",
                    object="進度",
                    evidence=evidence("追蹤進度"),
                )
            ),
        }
        for path, content in resources.items():
            assert (await workspace.backend.awrite(path, content)).error is None

        snapshot, _, workspace_snapshot, projection = await _validated_workspace_review(
            runtime,
            document_id,
        )
        duty_id = workspace_snapshot.manifest.entity_ids_by_handle["duty-001"]
        accepted_task_id = workspace_snapshot.manifest.entity_ids_by_handle["task-002"]
        selected = tuple(
            action
            for group in projection.groups
            for action in group.actions
            if isinstance(action.after, dict)
            and (
                (action.path == "/duties" and action.after.get("duty_id") == str(duty_id))
                or (
                    action.path == "/tasks"
                    and action.after.get("task_id") == str(accepted_task_id)
                )
            )
        )
        assert len(selected) == 2
        group = next(
            group
            for group in projection.groups
            if {action.action_id for action in selected}
            <= {action.action_id for action in group.actions}
        )
        command = WorkspaceReviewCommand(
            command_id=uuid4(),
            document_id=document_id,
            decision=WorkspaceDecisionKind.ACCEPT,
            approved_revision=snapshot.revision,
            workspace_generation=workspace_snapshot.manifest.generation,
            workspace_digest=workspace_snapshot.manifest.resource_digest,
            changeset_id=group.changeset.changeset_id,
            group_digest=group.group_digest,
            selected_action_ids=tuple(action.action_id for action in selected),
            reason="接受職責與第二項工作",
        )

        accepted = await runtime.decide_workspace_changes(command)
        reopened = await runtime.reopen_document(document_id)
        after = await workspace.read_snapshot()

        assert accepted.approved_document == reopened.approved_document
        assert tuple(item.duty_id for item in reopened.approved_document.duties) == (
            duty_id,
        )
        assert tuple(item.task_id for item in reopened.approved_document.tasks) == (
            accepted_task_id,
        )
        assert "/workspace/tasks/task-001.json" in after.files
        assert "/workspace/tasks/task-002.json" in after.files
        assert (
            after.manifest.entity_ids_by_handle["task-001"]
            != after.manifest.entity_ids_by_handle["task-002"]
        )
        assert after.manifest.validation_status is WorkspaceValidationStatus.VALID
        assert not any(
            diagnostic.code == "workspace-rebase-conflict"
            for diagnostic in after.manifest.diagnostics
        )
        assert reopened.document_review.unresolved_action_count > 0
        assert (
            await runtime.store.aget(
                runtime.workspace_metadata_namespace(document_id),
                f"rebase:{command.command_id}",
            )
            is None
        )


@pytest.mark.asyncio
async def test_planned_workspace_decision_replays_authority_after_graph_receipt_gap(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Planned recovery")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=seeded.approved_document,
            approved_revision=seeded.revision,
        )
        await _edit_task_statement(workspace, "AI planned recovery")
        snapshot, _, workspace_snapshot, projection = await _validated_workspace_review(
            runtime,
            document_id,
        )
        group = projection.groups[0]
        action = group.actions[0]
        command = _workspace_command(
            document_id=document_id,
            snapshot=snapshot,
            workspace_snapshot=workspace_snapshot,
            group=group,
            decision=WorkspaceDecisionKind.ACCEPT,
            action_id=action.action_id,
            reason="接受 planned",
        )
        prospective = apply_document_actions(
            snapshot.approved_document,
            (action,),
        )
        authority = WorkspaceAuthorityService(runtime)
        plan = await authority._build_plan(
            command_id=command.command_id,
            old_approved=snapshot.approved_document,
            workspace_files=workspace_snapshot.files,
            new_approved=prospective,
            manifest=workspace_snapshot.manifest,
            approved_revision=snapshot.revision + 1,
        )
        record = authority._record(command, group, plan=plan)
        await authority._put_plan(document_id, plan)
        await authority._put_record(document_id, record)
        assert await authority._load_plan(document_id, command.command_id) is not None
        assert (await runtime.raw_state(document_id)).get("command_receipts", {}) == {}

        with pytest.raises(WorkspaceAuthorityError, match="reused"):
            await runtime.decide_workspace_changes(
                command.model_copy(update={"reason": "不同 payload"})
            )

        replayed = await runtime.decide_workspace_changes(command)

        assert replayed.approved_document.tasks[0].statement == "AI planned recovery"
        assert (
            await runtime.store.aget(
                runtime.workspace_metadata_namespace(document_id),
                f"rebase:{command.command_id}",
            )
            is None
        )


@pytest.mark.asyncio
async def test_workspace_authority_rejects_stale_identity_and_keeps_nonoverlap_decidable(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    initial_source_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Stale authority")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=initial_source_id,
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=seeded.approved_document,
            approved_revision=seeded.revision,
        )
        await _edit_task_statement(workspace, "AI語句")
        await _edit_task_field(workspace, "action", "AI動作")
        snapshot, _, workspace_snapshot, projection = await _validated_workspace_review(
            runtime,
            document_id,
        )
        assert len(projection.groups) == 2
        statement_group = next(
            group
            for group in projection.groups
            if group.actions[0].path.endswith("/statement")
        )
        action_group = next(
            group
            for group in projection.groups
            if group.actions[0].path.endswith("/action")
        )
        statement_command = _workspace_command(
            document_id=document_id,
            snapshot=snapshot,
            workspace_snapshot=workspace_snapshot,
            group=statement_group,
            decision=WorkspaceDecisionKind.ACCEPT,
            action_id=statement_group.actions[0].action_id,
            reason="接受語句",
        )
        with pytest.raises(WorkspaceAuthorityError, match="group digest"):
            await runtime.decide_workspace_changes(
                statement_command.model_copy(update={"group_digest": "0" * 64})
            )

        action_command = _workspace_command(
            document_id=document_id,
            snapshot=snapshot,
            workspace_snapshot=workspace_snapshot,
            group=action_group,
            decision=WorkspaceDecisionKind.ACCEPT,
            action_id=action_group.actions[0].action_id,
            reason="接受動作",
        )
        accepted_action = await runtime.decide_workspace_changes(action_command)
        assert accepted_action.approved_document.tasks[0].action == "AI動作"
        assert json.loads(
            (await workspace.read_snapshot()).files["/workspace/tasks/task-001.json"]
        )["statement"] == "AI語句"
        with pytest.raises(WorkspaceAuthorityError, match="stale"):
            await runtime.decide_workspace_changes(statement_command)

        snapshot, _, workspace_snapshot, projection = await _validated_workspace_review(
            runtime,
            document_id,
        )
        statement_group = next(
            group
            for group in projection.groups
            if group.actions[0].path.endswith("/statement")
        )
        fresh_statement_command = _workspace_command(
            document_id=document_id,
            snapshot=snapshot,
            workspace_snapshot=workspace_snapshot,
            group=statement_group,
            decision=WorkspaceDecisionKind.ACCEPT,
            action_id=statement_group.actions[0].action_id,
            reason="接受語句",
        )
        await runtime.record_employee_source(
            document_id=document_id,
            source_id=uuid4(),
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="更正證據",
            supersedes_source_id=initial_source_id,
        )
        with pytest.raises(WorkspaceAuthorityError, match="stale"):
            await runtime.decide_workspace_changes(fresh_statement_command)


@pytest.mark.asyncio
async def test_workspace_authority_recovers_after_approved_checkpoint_before_rebase(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Authority crash")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=seeded.approved_document,
            approved_revision=seeded.revision,
        )
        await _edit_task_statement(workspace, "AI崩潰窗")
        snapshot, _, workspace_snapshot, projection = await _validated_workspace_review(
            runtime,
            document_id,
        )
        group = projection.groups[0]
        action = group.actions[0]
        command = _workspace_command(
            document_id=document_id,
            snapshot=snapshot,
            workspace_snapshot=workspace_snapshot,
            group=group,
            decision=WorkspaceDecisionKind.ACCEPT,
            action_id=action.action_id,
            reason="接受",
        )

        class InjectedFailure(RuntimeError):
            pass

        async def fail_once() -> None:
            raise InjectedFailure("after authority checkpoint")

        runtime._after_workspace_authority_checkpoint = fail_once
        with pytest.raises(InjectedFailure):
            await runtime.decide_workspace_changes(command)
        runtime._after_workspace_authority_checkpoint = runtime._noop_workspace_hook

        reopened = await runtime.reopen_document(document_id)
        assert reopened.approved_document.tasks[0].statement == "AI崩潰窗"
        assert (await workspace.read_snapshot()).manifest.approved_baseline_revision == reopened.revision
        assert reopened.document_review.unresolved_action_count == 0


@pytest.mark.asyncio
async def test_edit_accept_source_store_crash_replays_one_deterministic_source(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Source crash")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=seeded.approved_document,
            approved_revision=seeded.revision,
        )
        await _edit_task_statement(workspace, "AI source crash")
        snapshot, _, workspace_snapshot, projection = await _validated_workspace_review(
            runtime,
            document_id,
        )
        group = projection.groups[0]
        action = group.actions[0]
        command = _workspace_command(
            document_id=document_id,
            snapshot=snapshot,
            workspace_snapshot=workspace_snapshot,
            group=group,
            decision=WorkspaceDecisionKind.EDIT_ACCEPT,
            action_id=action.action_id,
            edited_after="員工 source recovery",
            reason="員工確認",
        )

        class InjectedFailure(RuntimeError):
            pass

        async def fail_after_source_store(_source: EmployeeSource) -> None:
            raise InjectedFailure("after direct-edit source store")

        runtime._after_source_store = fail_after_source_store
        with pytest.raises(InjectedFailure):
            await runtime.decide_workspace_changes(command)
        runtime._after_source_store = runtime._noop_source_hook

        direct_sources = [
            source
            for source in await runtime.list_sources(document_id)
            if source.kind is EmployeeSourceKind.DIRECT_EDIT
            and source.text == "員工 source recovery"
        ]
        assert len(direct_sources) == 1
        assert direct_sources[0].processing_status is SourceProcessingStatus.PENDING

        different_payload = command.model_copy(
            update={"edited_after_by_action_id": {action.action_id: "另一個員工值"}}
        )
        with pytest.raises(SourceConflict):
            await runtime.decide_workspace_changes(different_payload)

        replayed = await runtime.decide_workspace_changes(command)
        assert replayed.approved_document.tasks[0].statement == "員工 source recovery"
        direct_sources = [
            source
            for source in await runtime.list_sources(document_id)
            if source.kind is EmployeeSourceKind.DIRECT_EDIT
            and source.text == "員工 source recovery"
        ]
        assert len(direct_sources) == 1
        assert direct_sources[0].processing_status is SourceProcessingStatus.COMMITTED


@pytest.mark.asyncio
async def test_workspace_reject_record_recovers_before_workspace_revert(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Reject crash")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=seeded.approved_document,
            approved_revision=seeded.revision,
        )
        await _edit_task_statement(workspace, "AI拒絕崩潰窗")
        snapshot, _, workspace_snapshot, projection = await _validated_workspace_review(
            runtime,
            document_id,
        )
        group = projection.groups[0]
        action = group.actions[0]
        command = _workspace_command(
            document_id=document_id,
            snapshot=snapshot,
            workspace_snapshot=workspace_snapshot,
            group=group,
            decision=WorkspaceDecisionKind.REJECT,
            action_id=action.action_id,
            reason="不採用",
        )

        class InjectedFailure(RuntimeError):
            pass

        async def fail_once() -> None:
            raise InjectedFailure("after decision record")

        runtime._after_workspace_decision_record = fail_once
        with pytest.raises(InjectedFailure):
            await runtime.decide_workspace_changes(command)
        runtime._after_workspace_decision_record = runtime._noop_workspace_hook

        reopened = await runtime.reopen_document(document_id)
        expected_files = project_workspace_files(
            reopened.approved_document,
            handle_registry=(await workspace.read_snapshot()).manifest.entity_ids_by_handle,
        ).files
        final_workspace = await workspace.read_snapshot()
        assert json.loads(final_workspace.files["/workspace/tasks/task-001.json"]) == json.loads(
            expected_files["/workspace/tasks/task-001.json"]
        )
        assert (
            await runtime.store.aget(
                runtime.workspace_metadata_namespace(document_id),
                f"rebase:{command.command_id}",
            )
            is None
        )


@pytest.mark.asyncio
async def test_workspace_store_backend_is_not_an_authority_checkpoint_files_channel(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="Store workspace")
        backend = StoreBackend(
            namespace=lambda _runtime: runtime.workspace_namespace(document_id),
            store=runtime.store,
        )

        assert (await backend.awrite("/workspace/header.json", "{}\n")).error is None

        assert "files" not in await runtime.raw_state(document_id)


@pytest.mark.asyncio
async def test_delete_document_clears_all_workspace_namespaces(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="Store workspace")
        namespaces = (
            runtime.workspace_namespace(document_id),
            runtime.workspace_metadata_namespace(document_id),
            runtime.workspace_decision_namespace(document_id),
        )
        for index, namespace in enumerate(namespaces):
            await runtime.store.aput(namespace, f"item-{index}", {"value": index})

        await runtime.delete_document(document_id)

        assert [await runtime.store.asearch(namespace) for namespace in namespaces] == [
            [],
            [],
            [],
        ]


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
async def test_current_document_edit_rejects_stale_workspace_without_writes(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="目前 JD stale")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        before = await workspace.read_snapshot()
        submitted = seeded.approved_document.model_copy(
            update={"job_title": "不應寫入"}
        )
        command = CommandReceipt(
            command_id=uuid4(),
            command_kind="direct_document_edit",
            payload_sha256="a" * 64,
        )

        approved_before = await runtime.export_approved_document(document_id)
        sources_before = await runtime.list_sources(document_id)
        with pytest.raises(StaleRevision):
            await runtime.apply_current_document_edit(
                document_id=document_id,
                expected_revision=seeded.revision,
                workspace_generation=before.manifest.generation + 1,
                workspace_digest=before.manifest.resource_digest,
                document=submitted,
                source_id=source_id,
                command_receipt=command,
            )
        assert await runtime.export_approved_document(document_id) == approved_before
        assert await runtime.list_sources(document_id) == sources_before
        assert (await workspace.read_snapshot()).files == before.files
        assert (await workspace.read_snapshot()).manifest.resource_digest == (
            before.manifest.resource_digest
        )


@pytest.mark.asyncio
async def test_current_document_edit_accepts_employee_added_opks_with_direct_edit_evidence(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="新增 OPKS")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        before = await workspace.read_snapshot()
        added = ApprovedOpksItem(
            item_id=uuid4(),
            kind=ApprovedOpksKind.KNOWLEDGE,
            text="員工新增的法規知識",
            display_order=0,
            evidence_source_ids=(source_id,),
        )
        submitted = seeded.approved_document.model_copy(update={"opks": (added,)})
        command = CommandReceipt(
            command_id=uuid4(),
            command_kind="direct_document_edit",
            payload_sha256="a" * 64,
        )

        result = await runtime.apply_current_document_edit(
            document_id=document_id,
            expected_revision=seeded.revision,
            workspace_generation=before.manifest.generation,
            workspace_digest=before.manifest.resource_digest,
            document=submitted,
            source_id=source_id,
            command_receipt=command,
        )

        assert result.approved_document.opks == (added,)
        source = await runtime.get_source(document_id, source_id)
        assert source.processing_status is SourceProcessingStatus.COMMITTED
        after = await workspace.read_snapshot()
        added_resource = next(
            json.loads(raw)
            for path, raw in after.files.items()
            if path.startswith("/workspace/opks/k/")
            and json.loads(raw).get("text") == added.text
        )
        assert added_resource["evidence"] == [
            {
                "source_handle": next(
                    handle
                    for handle, stable_id in after.manifest.entity_ids_by_handle.items()
                    if stable_id == source_id
                ),
                "quote": added.text,
                "occurrence": 1,
                "skill_ids": ["knowledge"],
            }
        ]
        assert after.manifest.validation_status is WorkspaceValidationStatus.VALID


@pytest.mark.asyncio
async def test_current_document_edit_replays_after_source_store_crash(
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
        created = await runtime.create_document(document_id, title="source crash")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        before = await workspace.read_snapshot()
        submitted = seeded.approved_document.model_copy(
            update={"work_description": "員工直接補充的工作描述"}
        )

        class InjectedFailure(RuntimeError):
            pass

        async def fail_after_source_store(_source: EmployeeSource) -> None:
            raise InjectedFailure("after current-document source store")

        runtime._after_source_store = fail_after_source_store
        with pytest.raises(InjectedFailure):
            await runtime.apply_current_document_edit(
                document_id=document_id,
                expected_revision=seeded.revision,
                workspace_generation=before.manifest.generation,
                workspace_digest=before.manifest.resource_digest,
                document=submitted,
                source_id=source_id,
                command_receipt=command,
            )
        runtime._after_source_store = runtime._noop_source_hook

        pending = [
            source
            for source in await runtime.list_sources(document_id)
            if source.source_id == source_id
        ]
        assert len(pending) == 1
        assert pending[0].processing_status is SourceProcessingStatus.PENDING
        assert await runtime.export_approved_document(document_id) == seeded.approved_document
        assert (await workspace.read_snapshot()).files == before.files

        replayed = await runtime.apply_current_document_edit(
            document_id=document_id,
            expected_revision=seeded.revision,
            workspace_generation=before.manifest.generation,
            workspace_digest=before.manifest.resource_digest,
            document=submitted,
            source_id=source_id,
            command_receipt=command,
        )
        assert replayed.approved_document == submitted
        assert replayed.revision == seeded.revision + 1
        sources = [
            source
            for source in await runtime.list_sources(document_id)
            if source.source_id == source_id
        ]
        assert len(sources) == 1
        assert sources[0].processing_status is SourceProcessingStatus.COMMITTED
        assert (await workspace.read_snapshot()).manifest.approved_baseline_revision == (
            replayed.revision
        )


@pytest.mark.asyncio
async def test_current_document_edit_recovers_after_approved_checkpoint_and_binds_replay(
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
        created = await runtime.create_document(document_id, title="checkpoint crash")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=uuid4(),
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        before = await workspace.read_snapshot()
        submitted = seeded.approved_document.model_copy(
            update={"job_title": "核准後可恢復"}
        )

        class InjectedFailure(RuntimeError):
            pass

        async def fail_after_checkpoint() -> None:
            raise InjectedFailure("after approved checkpoint")

        runtime._after_workspace_authority_checkpoint = fail_after_checkpoint
        with pytest.raises(InjectedFailure):
            await runtime.apply_current_document_edit(
                document_id=document_id,
                expected_revision=seeded.revision,
                workspace_generation=before.manifest.generation,
                workspace_digest=before.manifest.resource_digest,
                document=submitted,
                source_id=source_id,
                command_receipt=command,
            )
        runtime._after_workspace_authority_checkpoint = runtime._noop_workspace_hook

        checkpointed = (await runtime._snapshot(document_id)).approved_document
        assert checkpointed == submitted
        assert (await workspace.read_snapshot()).manifest.approved_baseline_revision != (
            seeded.revision + 1
        )

        recovered = await runtime.reopen_document(document_id)
        assert recovered.approved_document == submitted
        assert recovered.revision == seeded.revision + 1
        recovered_workspace = await workspace.read_snapshot()
        assert recovered_workspace.manifest.approved_baseline_revision == recovered.revision
        source = await runtime.get_source(document_id, source_id)
        assert source.processing_status is SourceProcessingStatus.COMMITTED

        replayed = await runtime.apply_current_document_edit(
            document_id=document_id,
            expected_revision=seeded.revision,
            workspace_generation=before.manifest.generation,
            workspace_digest=before.manifest.resource_digest,
            document=submitted,
            source_id=source_id,
            command_receipt=command,
        )
        assert replayed.revision == recovered.revision
        assert len(
            [
                source
                for source in await runtime.list_sources(document_id)
                if source.source_id == source_id
            ]
        ) == 1

        with pytest.raises(IdempotencyConflict):
            await runtime.apply_current_document_edit(
                document_id=document_id,
                expected_revision=recovered.revision,
                workspace_generation=recovered_workspace.manifest.generation,
                workspace_digest=recovered_workspace.manifest.resource_digest,
                document=submitted.model_copy(update={"job_title": "同 key 不得換 payload"}),
                source_id=source_id,
                command_receipt=command.model_copy(
                    update={"payload_sha256": "b" * 64}
                ),
            )
        assert await runtime.export_approved_document(document_id) == submitted


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
async def test_failed_postgres_run_restarts_and_exact_admission_replays(
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
            text="我負責核對訂單並回報結果。",
        )
        assert should_process is True
        failed = await runtime.mark_consultant_run_failed(
            document_id=document_id,
            run_id=run_id,
            error_code="model_timeout",
        )
        assert failed.latest_run is not None
        assert failed.latest_run["status"] == RunStatus.FAILED.value
        restarted, should_restart = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責核對訂單並回報結果。",
        )
        assert should_restart is True
        assert restarted.latest_run is not None
        assert restarted.latest_run["status"] == RunStatus.SOURCE_SAVED.value
        replay, should_replay = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責核對訂單並回報結果。",
        )
        assert should_replay is False
        assert replay.revision == restarted.revision


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
