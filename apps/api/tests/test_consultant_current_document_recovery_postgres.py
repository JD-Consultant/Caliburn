from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio

from app.adapters.langgraph.postgres import (
    StaleRevision,
    open_postgres_consultant_runtime,
)
from app.consultant.skill_backend import CONSULTANT_SKILL_IDS
from app.consultant.document_commands import CreateDuty, UndoDocumentCommand
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedTask,
    CommandReceipt,
    EmployeeSourceKind,
    SourceProcessingStatus,
)
from app.consultant.workspace_resources import (
    WorkspaceCatalog,
    WorkspaceDutyResource,
    WorkspaceTaskResource,
    canonical_resource_json,
)
from app.consultant.workspace_authority import (
    WorkspaceDecisionKind,
    WorkspaceReviewCommand,
)
from app.consultant.workspace_state import StoreBackedWorkspace
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


def _document(document_id: UUID) -> ApprovedJobDocument:
    duty_id = uuid4()
    return ApprovedJobDocument(
        document_id=document_id,
        job_title="採購專員",
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
                display_order=0,
            ),
        ),
    )


def _receipt() -> CommandReceipt:
    return CommandReceipt(
        command_id=uuid4(),
        command_kind="current_document_edit",
        payload_sha256=uuid4().hex * 2,
    )


async def _seed(runtime, document_id: UUID):
    created = await runtime.create_document(document_id, title="目前 JD recovery")
    return await runtime.apply_direct_edit(
        document_id=document_id,
        expected_revision=created.revision,
        document=_document(document_id),
        source_id=uuid4(),
    )


async def _stage_ai_task_fields(runtime, document_id: UUID, **updates: str):
    workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
    workspace_snapshot = await workspace.read_snapshot()
    task_path = next(
        path for path in workspace_snapshot.files if path.startswith("/workspace/tasks/")
    )
    payload = json.loads(workspace_snapshot.files[task_path])
    payload.update(updates)
    write = await workspace.backend.awrite(
        task_path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    assert write.error is None
    snapshot = await runtime._snapshot(document_id)
    latest_workspace = await workspace.read_snapshot()
    validator = WorkspaceValidationService(
        workspace=workspace,
        catalog=WorkspaceCatalog.from_snapshot(
            snapshot.approved_document,
            sources=await runtime.list_sources(document_id),
            handle_registry=latest_workspace.manifest.entity_ids_by_handle,
        ),
        source_loader=lambda: runtime.list_sources(document_id),
        selected_skill_ids=CONSULTANT_SKILL_IDS,
    )
    validation = await validator.validate_current(
        loaded_skill_ids=CONSULTANT_SKILL_IDS,
    )
    assert validation.document is not None
    return await runtime.reopen_document(document_id)


async def _stage_ai_task_statement(runtime, document_id: UUID, statement: str):
    return await _stage_ai_task_fields(runtime, document_id, statement=statement)


async def _stage_ai_task_add(runtime, document_id: UUID):
    workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
    write = await workspace.backend.awrite(
        "/workspace/tasks/task-999.json",
        canonical_resource_json(
            WorkspaceTaskResource(
                handle="task-999",
                statement="AI 彙整採購需求",
                action="AI 彙整",
                object="採購需求",
            )
        ),
    )
    assert write.error is None
    snapshot = await runtime._snapshot(document_id)
    latest_workspace = await workspace.read_snapshot()
    validator = WorkspaceValidationService(
        workspace=workspace,
        catalog=WorkspaceCatalog.from_snapshot(
            snapshot.approved_document,
            sources=await runtime.list_sources(document_id),
            handle_registry=latest_workspace.manifest.entity_ids_by_handle,
        ),
        source_loader=lambda: runtime.list_sources(document_id),
        selected_skill_ids=CONSULTANT_SKILL_IDS,
    )
    validation = await validator.validate_current(
        loaded_skill_ids=CONSULTANT_SKILL_IDS,
    )
    assert validation.document is not None
    return await runtime.reopen_document(document_id)


async def _stage_ai_duty(runtime, document_id: UUID, statement: str):
    workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
    write = await workspace.backend.awrite(
        "/workspace/duties/duty-999.json",
        canonical_resource_json(
            WorkspaceDutyResource(
                handle="duty-999",
                statement=statement,
                display_order=1,
            )
        ),
    )
    assert write.error is None
    snapshot = await runtime._snapshot(document_id)
    latest_workspace = await workspace.read_snapshot()
    validator = WorkspaceValidationService(
        workspace=workspace,
        catalog=WorkspaceCatalog.from_snapshot(
            snapshot.approved_document,
            sources=await runtime.list_sources(document_id),
            handle_registry=latest_workspace.manifest.entity_ids_by_handle,
        ),
        source_loader=lambda: runtime.list_sources(document_id),
        selected_skill_ids=CONSULTANT_SKILL_IDS,
    )
    validation = await validator.validate_current(
        loaded_skill_ids=CONSULTANT_SKILL_IDS,
    )
    assert validation.document is not None
    return await runtime.reopen_document(document_id)


async def _edit(runtime, snapshot, document, *, receipt=None, source_id=None):
    return await runtime.apply_current_document_edit(
        document_id=snapshot.document_id,
        expected_revision=snapshot.revision,
        workspace_generation=snapshot.document_review.workspace_generation,
        workspace_digest=snapshot.document_review.workspace_digest,
        document=document,
        source_id=source_id or uuid4(),
        command_receipt=receipt or _receipt(),
    )


@pytest.mark.asyncio
async def test_plan_before_graph_crash_is_discarded_without_changing_current_or_approved(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        seeded = await _seed(runtime, document_id)
        current = await runtime.reopen_document(document_id)
        submitted = current.current_document.model_copy(update={"notes": "員工備註"})

        class InjectedFailure(RuntimeError):
            pass

        async def fail_after_plan() -> None:
            raise InjectedFailure("after current-document plan")

        runtime._after_workspace_decision_record = fail_after_plan
        with pytest.raises(InjectedFailure):
            await _edit(runtime, current, submitted)
        runtime._after_workspace_decision_record = runtime._noop_workspace_hook

        reopened = await runtime.reopen_document(document_id)
        assert reopened.revision == seeded.revision
        assert reopened.approved_document.notes is None
        assert reopened.current_document.notes is None
        assert not [
            item
            for item in await runtime.list_sources(document_id)
            if item.kind is EmployeeSourceKind.DIRECT_EDIT
            and item.text == "員工備註"
        ]


@pytest.mark.asyncio
async def test_graph_before_store_crash_recovers_pending_only_current_edit_once(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        seeded = await _seed(runtime, document_id)
        current = await _stage_ai_task_statement(runtime, document_id, "AI 待審內容")
        submitted = current.current_document.model_copy(
            update={
                "tasks": (
                    current.current_document.tasks[0].model_copy(
                        update={"statement": "員工修改 AI 草稿"}
                    ),
                )
            }
        )

        class InjectedFailure(RuntimeError):
            pass

        async def fail_after_graph() -> None:
            raise InjectedFailure("after graph checkpoint")

        runtime._after_workspace_authority_checkpoint = fail_after_graph
        with pytest.raises(InjectedFailure):
            await _edit(runtime, current, submitted)
        runtime._after_workspace_authority_checkpoint = runtime._noop_workspace_hook

        reopened = await runtime.reopen_document(document_id)
        assert reopened.revision == seeded.revision + 1
        assert reopened.approved_document.tasks[0].statement == "檢查缺料並安排採購"
        assert reopened.current_document.tasks[0].statement == "員工修改 AI 草稿"
        sources = [
            item
            for item in await runtime.list_sources(document_id)
            if item.kind is EmployeeSourceKind.DIRECT_EDIT
            and item.text == "員工修改 AI 草稿"
        ]
        assert len(sources) == 1
        assert sources[0].processing_status is SourceProcessingStatus.COMMITTED


@pytest.mark.asyncio
async def test_store_before_response_crash_and_request_replay_are_idempotent(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    receipt = _receipt()
    source_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await _seed(runtime, document_id)
        current = await runtime.reopen_document(document_id)
        submitted = current.current_document.model_copy(update={"notes": "可重播備註"})

        class InjectedFailure(RuntimeError):
            pass

        async def fail_after_store() -> None:
            raise InjectedFailure("after current-document Store commit")

        runtime._after_current_document_store = fail_after_store
        with pytest.raises(InjectedFailure):
            await _edit(
                runtime,
                current,
                submitted,
                receipt=receipt,
                source_id=source_id,
            )
        runtime._after_current_document_store = runtime._noop_workspace_hook

        reopened = await runtime.reopen_document(document_id)
        replayed = await _edit(
            runtime,
            current,
            submitted,
            receipt=receipt,
            source_id=source_id,
        )
        assert replayed.revision == reopened.revision
        assert replayed.approved_document.notes == "可重播備註"
        assert replayed.current_document.notes == "可重播備註"


@pytest.mark.asyncio
@pytest.mark.parametrize("stale_part", ["revision", "generation", "digest"])
async def test_current_document_edit_rejects_every_server_owned_stale_guard(
    consultant_database_url: str,
    stale_part: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await _seed(runtime, document_id)
        current = await runtime.reopen_document(document_id)
        kwargs = {
            "document_id": document_id,
            "expected_revision": current.revision,
            "workspace_generation": current.document_review.workspace_generation,
            "workspace_digest": current.document_review.workspace_digest,
            "document": current.current_document.model_copy(update={"notes": "不得寫入"}),
            "source_id": uuid4(),
            "command_receipt": _receipt(),
        }
        if stale_part == "revision":
            kwargs["expected_revision"] += 1
        elif stale_part == "generation":
            kwargs["workspace_generation"] += 1
        else:
            kwargs["workspace_digest"] = "0" * 64

        with pytest.raises(StaleRevision):
            await runtime.apply_current_document_edit(**kwargs)

        unchanged = await runtime.reopen_document(document_id)
        assert unchanged.approved_document.notes is None
        assert unchanged.current_document.notes is None


@pytest.mark.asyncio
async def test_structural_command_updates_one_current_jd_and_undo_restores_it(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await _seed(runtime, document_id)
        before = await runtime.reopen_document(document_id)
        created, undo_token = await runtime.apply_document_structure_command(
            document_id=document_id,
            expected_revision=before.revision,
            workspace_generation=before.document_review.workspace_generation,
            workspace_digest=before.document_review.workspace_digest,
            command=CreateDuty(name="法遵管理"),
            source_id=uuid4(),
            command_receipt=CommandReceipt(
                command_id=uuid4(),
                command_kind="current_document_structure",
                payload_sha256=uuid4().hex * 2,
            ),
        )

        assert undo_token is not None
        assert created.current_document == created.approved_document
        assert [item.statement for item in created.current_document.duties] == [
            "物料供應管理",
            "法遵管理",
        ]

        restored, next_undo = await runtime.apply_document_structure_command(
            document_id=document_id,
            expected_revision=created.revision,
            workspace_generation=created.document_review.workspace_generation,
            workspace_digest=created.document_review.workspace_digest,
            command=UndoDocumentCommand(undo_token=undo_token),
            source_id=uuid4(),
            command_receipt=CommandReceipt(
                command_id=uuid4(),
                command_kind="current_document_structure",
                payload_sha256=uuid4().hex * 2,
            ),
        )

        assert next_undo is None
        assert restored.current_document == before.current_document
        assert restored.approved_document == before.approved_document

        with pytest.raises(StaleRevision, match="undo token is stale"):
            await runtime.apply_document_structure_command(
                document_id=document_id,
                expected_revision=restored.revision,
                workspace_generation=restored.document_review.workspace_generation,
                workspace_digest=restored.document_review.workspace_digest,
                command=UndoDocumentCommand(undo_token=undo_token),
                source_id=uuid4(),
                command_receipt=CommandReceipt(
                    command_id=uuid4(),
                    command_kind="current_document_structure",
                    payload_sha256=uuid4().hex * 2,
                ),
            )


@pytest.mark.asyncio
async def test_two_current_autosaves_remain_pending_until_one_group_accept(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await _seed(runtime, document_id)
        pending = await _stage_ai_task_add(runtime, document_id)
        task_id = next(
            task.task_id
            for task in pending.current_document.tasks
            if task.statement == "AI 彙整採購需求"
        )

        first_document = pending.current_document.model_copy(
            update={
                "tasks": tuple(
                    task.model_copy(update={"statement": "員工彙整採購需求"})
                    if task.task_id == task_id
                    else task
                    for task in pending.current_document.tasks
                )
            }
        )
        first = await _edit(runtime, pending, first_document)
        assert len(first.approved_document.tasks) == 1
        assert first.document_review.unresolved_action_count > 0

        second_document = first.current_document.model_copy(
            update={
                "tasks": tuple(
                    task.model_copy(update={"action": "彙整並確認"})
                    if task.task_id == task_id
                    else task
                    for task in first.current_document.tasks
                )
            }
        )
        second = await _edit(runtime, first, second_document)
        assert len(second.approved_document.tasks) == 1
        assert second.document_review.unresolved_action_count > 0

        snapshot, _workspace, workspace_snapshot, projection = (
            await runtime.workspace_review_context(document_id)
        )
        group = next(
            group
            for group in projection.groups
            if any(
                isinstance(action.after, dict)
                and action.after.get("task_id") == str(task_id)
                for action in group.actions
            )
        )
        accepted = await runtime.decide_workspace_changes(
            WorkspaceReviewCommand(
                command_id=uuid4(),
                document_id=document_id,
                decision=WorkspaceDecisionKind.ACCEPT,
                approved_revision=snapshot.revision,
                workspace_generation=workspace_snapshot.manifest.generation,
                workspace_digest=workspace_snapshot.manifest.resource_digest,
                changeset_id=group.changeset.changeset_id,
                group_digest=group.group_digest,
                selected_action_ids=tuple(
                    action.action_id for action in group.actions
                ),
            )
        )

        accepted_task = next(
            task for task in accepted.approved_document.tasks if task.task_id == task_id
        )
        assert accepted_task.statement == "員工彙整採購需求"
        assert accepted_task.action == "彙整並確認"
        assert accepted.current_document == accepted.approved_document
        assert accepted.document_review.unresolved_action_count == 0


@pytest.mark.asyncio
async def test_create_with_ai_pending_sibling_never_diverges_approved_order(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await _seed(runtime, document_id)
        pending = await _stage_ai_duty(runtime, document_id, "AI 待審職責")

        created, _undo_token = await runtime.apply_document_structure_command(
            document_id=document_id,
            expected_revision=pending.revision,
            workspace_generation=pending.document_review.workspace_generation,
            workspace_digest=pending.document_review.workspace_digest,
            command=CreateDuty(name="員工新增職責"),
            source_id=uuid4(),
            command_receipt=CommandReceipt(
                command_id=uuid4(),
                command_kind="current_document_structure",
                payload_sha256=uuid4().hex * 2,
            ),
        )

        assert [item.statement for item in created.approved_document.duties] == [
            "物料供應管理"
        ]
        assert {
            item.statement: item.display_order
            for item in created.current_document.duties
        } == {
            "物料供應管理": 0,
            "AI 待審職責": 1,
            "員工新增職責": 2,
        }
