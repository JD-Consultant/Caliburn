from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio

from app.adapters.langgraph.postgres import (
    ConsultantRunAlreadyActive,
    open_postgres_consultant_runtime,
)
from app.config import Settings
from app.consultant.context import (
    ContextRequest,
    DocumentSourceLookup,
    build_consultant_context,
)
from app.consultant.run_service import (
    build_configured_execution,
    execute_admitted_consultant_turn,
)
from app.consultant.skill_backend import CONSULTANT_SKILL_IDS
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedTask,
    EmployeeSourceKind,
    RunStatus,
    SourceValidity,
)
from app.consultant.workspace_authority import (
    WorkspaceAuthorityError,
    WorkspaceAuthorityService,
    WorkspaceDecisionKind,
    WorkspaceReviewCommand,
)
from app.consultant.workspace_backend import build_consultant_workspace_backend
from app.consultant.workspace_resources import WorkspaceCatalog
from app.consultant.workspace_state import (
    StoreBackedWorkspace,
    WorkspaceValidationStatus,
)
from app.consultant.workspace_validation import WorkspaceValidationService
from app.consultant.views import WorkspaceReviewStatus


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
        work_description="負責採購資料核對與回報。",
        duties=(
            ApprovedDuty(
                duty_id=duty_id,
                statement="採購資料管理",
                display_order=0,
            ),
        ),
        tasks=(
            ApprovedTask(
                task_id=uuid4(),
                duty_id=duty_id,
                statement="核對訂單",
                action="核對",
                object="訂單",
                display_order=0,
            ),
            ApprovedTask(
                task_id=uuid4(),
                duty_id=duty_id,
                statement="回報結果",
                action="回報",
                object="結果",
                display_order=1,
            ),
        ),
    )


async def _validator(runtime: Any, document_id: UUID) -> WorkspaceValidationService:
    snapshot = await runtime.reopen_document(document_id)
    sources = await runtime.list_sources(document_id)
    return WorkspaceValidationService(
        workspace=StoreBackedWorkspace(store=runtime.store, document_id=document_id),
        catalog=WorkspaceCatalog.from_snapshot(
            snapshot.approved_document,
            sources=sources,
        ),
        source_loader=lambda: runtime.list_sources(document_id),
        selected_skill_ids=CONSULTANT_SKILL_IDS,
    )


class TimeoutAfterInvalidWorkspaceWrite:
    skill_backend = SimpleNamespace(loaded_skill_ids=())

    def __init__(self, workspace: Any) -> None:
        self.workspace = workspace

    async def ainvoke(self, payload: Any, *, context: Any, config: Any) -> Any:
        del payload, context, config
        path = "/workspace/header.json"
        current = await self.workspace.workspace_backend.aread(path)
        assert current.error is None
        assert current.file_data is not None
        result = await self.workspace.workspace_backend.aedit(
            path,
            current.file_data["content"],
            "{provider-timeout-after-write\n",
        )
        assert result.error is None
        raise TimeoutError("provider timed out after a successful Store write")


@pytest.mark.asyncio
async def test_provider_timeout_workspace_survives_runtime_rebuild_and_is_repairable(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    execution = build_configured_execution(
        Settings(_env_file=None, openrouter_api_key="test-key")
    )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Timeout recovery")
        approved_before = created.approved_document
        await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責核對訂單。",
        )
        with pytest.raises(TimeoutError):
            await execute_admitted_consultant_turn(
                runtime=runtime,
                document_id=document_id,
                run_id=run_id,
                source_id=source_id,
                execution=execution,
                model=object(),
                agent_factory=lambda **kwargs: TimeoutAfterInvalidWorkspaceWrite(
                    kwargs["workspace_binding"]
                ),
            )
        failed = await runtime.reopen_document(document_id)
        assert failed.latest_run is not None
        assert failed.latest_run["status"] == RunStatus.FAILED.value
        assert failed.approved_document == approved_before

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        reopened = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        actual = await reopened.read_snapshot()
        assert actual.files["/workspace/header.json"] == (
            "{provider-timeout-after-write\n"
        )
        validation = await (await _validator(runtime, document_id)).validate_current(
            loaded_skill_ids=CONSULTANT_SKILL_IDS
        )
        assert validation.manifest.validation_status is WorkspaceValidationStatus.INVALID
        assert validation.diagnostics[0].code == "json-syntax"
        assert await runtime.export_approved_document(document_id) == approved_before


@pytest.mark.asyncio
@pytest.mark.parametrize("validate_before_close", [False, True])
async def test_interruption_or_invalid_close_recovers_actual_workspace_and_diagnostics(
    consultant_database_url: str,
    validate_before_close: bool,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    valid_header = ""
    approved_before: ApprovedJobDocument

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Interrupted recovery")
        sourced = await runtime.record_employee_source(
            document_id=document_id,
            source_id=source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="我會核對採購資料。",
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=sourced.approved_document,
            approved_revision=sourced.revision,
        )
        valid_header = (await workspace.read_snapshot()).files["/workspace/header.json"]
        assert (
            await workspace.backend.awrite(
                "/workspace/header.json",
                "{interrupted-before-validation\n",
            )
        ).error is None
        approved_before = await runtime.export_approved_document(document_id)
        if validate_before_close:
            invalid = await (await _validator(runtime, document_id)).validate_current(
                loaded_skill_ids=CONSULTANT_SKILL_IDS
            )
            assert invalid.diagnostics[0].code == "json-syntax"

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        actual = await workspace.read_snapshot()
        assert actual.files["/workspace/header.json"] == (
            "{interrupted-before-validation\n"
        )
        recovered = await (await _validator(runtime, document_id)).validate_current(
            loaded_skill_ids=CONSULTANT_SKILL_IDS
        )
        assert recovered.diagnostics[0].code == "json-syntax"
        assert await runtime.export_approved_document(document_id) == approved_before
        assert (
            await workspace.backend.awrite("/workspace/header.json", valid_header)
        ).error is None
        repaired = await (await _validator(runtime, document_id)).validate_current(
            loaded_skill_ids=CONSULTANT_SKILL_IDS
        )
        assert repaired.manifest.validation_status is WorkspaceValidationStatus.VALID


def _review_command(
    *,
    document_id: UUID,
    approved_revision: int,
    workspace_snapshot: Any,
    group: Any,
) -> WorkspaceReviewCommand:
    return WorkspaceReviewCommand(
        command_id=uuid4(),
        document_id=document_id,
        decision=WorkspaceDecisionKind.ACCEPT,
        approved_revision=approved_revision,
        workspace_generation=workspace_snapshot.manifest.generation,
        workspace_digest=workspace_snapshot.manifest.resource_digest,
        changeset_id=group.changeset.changeset_id,
        group_digest=group.group_digest,
        selected_action_ids=tuple(action.action_id for action in group.actions),
    )


@pytest.mark.asyncio
async def test_source_correction_stales_only_affected_review_and_next_turn_sees_lineage(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    original_source_id = uuid4()
    unrelated_source_id = uuid4()
    correction_source_id = uuid4()
    original_text = "核對訂單，核對訂單。"
    unrelated_text = "回報缺料結果。"
    correction_text = "更正：核對後只需回報結果。"
    document = _document(document_id)

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Correction recovery")
        edited = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=document,
            source_id=uuid4(),
        )
        first = await runtime.record_employee_source(
            document_id=document_id,
            source_id=original_source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text=original_text,
        )
        second = await runtime.record_employee_source(
            document_id=document_id,
            source_id=unrelated_source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text=unrelated_text,
        )
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=second.approved_document,
            approved_revision=second.revision,
        )
        sources = await runtime.list_sources(document_id)
        catalog = WorkspaceCatalog.from_snapshot(document, sources=sources)
        task_edits = (
            (
                "/workspace/tasks/task-001.json",
                original_text,
                original_source_id,
                "核對訂單",
            ),
            (
                "/workspace/tasks/task-002.json",
                unrelated_text,
                unrelated_source_id,
                "回報缺料結果",
            ),
        )
        for path, statement, evidence_source_id, quote in task_edits:
            before = (await workspace.read_snapshot()).files[path]
            payload = json.loads(before)
            payload["statement"] = statement
            payload["evidence"] = [
                {
                    "source_handle": catalog.source_handle_for_id(evidence_source_id),
                    "quote": quote,
                    "occurrence": 1,
                    "skill_ids": ["output"],
                }
            ]
            assert (
                await workspace.backend.awrite(
                    path,
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                )
            ).error is None
        initial = await (await _validator(runtime, document_id)).validate_current(
            loaded_skill_ids=CONSULTANT_SKILL_IDS
        )
        assert initial.document is not None

        corrected_snapshot = await runtime.record_employee_source(
            document_id=document_id,
            source_id=correction_source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text=correction_text,
            supersedes_source_id=original_source_id,
        )
        await workspace.ensure_initialized(
            approved_document=corrected_snapshot.approved_document,
            approved_revision=corrected_snapshot.revision,
        )
        corrected = await (await _validator(runtime, document_id)).validate_current(
            loaded_skill_ids=CONSULTANT_SKILL_IDS
        )
        snapshot, binding, workspace_snapshot, projection = await (
            WorkspaceAuthorityService(runtime)._review_context(document_id)
        )
        del binding
        first_task_id, second_task_id = (item.task_id for item in document.tasks)
        affected = next(
            group
            for group in projection.groups
            if any(str(first_task_id) in action.path for action in group.actions)
        )
        unrelated = next(
            group
            for group in projection.groups
            if any(str(second_task_id) in action.path for action in group.actions)
        )
        assert affected.diagnostics[0].code == "evidence-source-stale"
        assert unrelated.diagnostics == ()
        assert snapshot.document_review is not None
        assert (
            snapshot.document_review.workspace_status
            is WorkspaceReviewStatus.CONFLICTED
        )
        assert (
            affected.changeset.changeset_id
            in snapshot.document_review.acceptance_blocked_changeset_ids
        )

        current_sources = await DocumentSourceLookup(runtime).current_sources(document_id)
        assert original_source_id not in {source.source_id for source in current_sources}
        assert correction_source_id in {source.source_id for source in current_sources}
        lineage = await DocumentSourceLookup(runtime).lineage(
            document_id,
            correction_source_id,
        )
        assert tuple(source.source_id for source in lineage) == (
            original_source_id,
            correction_source_id,
        )
        current_catalog = WorkspaceCatalog.from_snapshot(
            document,
            sources=await runtime.list_sources(document_id),
        )
        correction_handle = current_catalog.source_handle_for_id(correction_source_id)
        context = await build_consultant_context(
            runtime=runtime,
            snapshot=corrected_snapshot,
            execution=build_configured_execution(
                Settings(_env_file=None, openrouter_api_key="test-key")
            ),
            request=ContextRequest(
                run_id=uuid4(),
                current_source_id=correction_source_id,
                current_source_handle=correction_handle,
                selected_skill_ids=CONSULTANT_SKILL_IDS,
            ),
            workspace_validation=corrected.summary,
        )
        assert context.messages[0].content == correction_text
        assert original_text not in context.system_prompt
        assert "evidence-source-stale" in context.system_prompt
        workspace_binding = build_consultant_workspace_backend(
            runtime=runtime,
            document_id=document_id,
            workspace=workspace,
            catalog=current_catalog,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
        )
        lineage_file = await workspace_binding.composite_backend.aread(
            f"/sources/lineages/{correction_handle}/001.txt"
        )
        assert lineage_file.error is None
        assert lineage_file.file_data is not None
        assert original_text in lineage_file.file_data["content"]

        with pytest.raises(WorkspaceAuthorityError, match="blocked by a diagnostic"):
            await runtime.decide_workspace_changes(
                _review_command(
                    document_id=document_id,
                    approved_revision=snapshot.revision,
                    workspace_snapshot=workspace_snapshot,
                    group=affected,
                )
            )
        accepted = await runtime.decide_workspace_changes(
            _review_command(
                document_id=document_id,
                approved_revision=snapshot.revision,
                workspace_snapshot=workspace_snapshot,
                group=unrelated,
            )
        )
        approved_tasks = {item.task_id: item for item in accepted.approved_document.tasks}
        assert approved_tasks[first_task_id].statement == "核對訂單"
        assert approved_tasks[second_task_id].statement == unrelated_text
        assert (
            await runtime.get_source(document_id, original_source_id)
        ).validity is SourceValidity.SUPERSEDED


@pytest.mark.asyncio
async def test_process_local_admission_keeps_other_documents_parallel_and_releases(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    other_document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        first = await runtime.create_document(document_id, title="Busy document")
        other = await runtime.create_document(other_document_id, title="Parallel document")

        async with runtime.active_consultant_run(document_id):
            with pytest.raises(ConsultantRunAlreadyActive):
                await runtime.apply_direct_edit(
                    document_id=document_id,
                    expected_revision=first.revision,
                    document=first.approved_document.model_copy(
                        update={"job_title": "不得交錯"}
                    ),
                    source_id=uuid4(),
                )
            parallel = await runtime.apply_direct_edit(
                document_id=other_document_id,
                expected_revision=other.revision,
                document=other.approved_document.model_copy(
                    update={"job_title": "可平行"}
                ),
                source_id=uuid4(),
            )
            assert parallel.approved_document.job_title == "可平行"

        try:
            async with runtime.active_consultant_run(document_id):
                raise RuntimeError("provider failure")
        except RuntimeError:
            pass
        async with runtime.active_consultant_run(document_id):
            pass
        released = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=first.revision,
            document=first.approved_document.model_copy(
                update={"job_title": "失敗後可編輯"}
            ),
            source_id=uuid4(),
        )
        assert released.approved_document.job_title == "失敗後可編輯"


async def _store_metrics(
    connection: Any,
    namespace: tuple[str, ...],
) -> tuple[int, int]:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT count(*)::int,
                   COALESCE(sum(pg_column_size(prefix) + pg_column_size(key)
                                + pg_column_size(value)), 0)::bigint
            FROM store
            WHERE prefix = %s
            """,
            (".".join(namespace),),
        )
        row = await cursor.fetchone()
    assert row is not None
    return int(row[0]), int(row[1])


async def _checkpoint_metrics(connection: Any, document_id: UUID) -> tuple[int, int]:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT
              ((SELECT count(*) FROM checkpoints WHERE thread_id = %s)
               + (SELECT count(*) FROM checkpoint_blobs WHERE thread_id = %s)
               + (SELECT count(*) FROM checkpoint_writes WHERE thread_id = %s))::int,
              (COALESCE((SELECT sum(pg_column_size(checkpoint) + pg_column_size(metadata))
                         FROM checkpoints WHERE thread_id = %s), 0)
               + COALESCE((SELECT sum(COALESCE(octet_length(blob), 0))
                           FROM checkpoint_blobs WHERE thread_id = %s), 0)
               + COALESCE((SELECT sum(COALESCE(octet_length(blob), 0))
                           FROM checkpoint_writes WHERE thread_id = %s), 0))::bigint
            """,
            (str(document_id),) * 6,
        )
        row = await cursor.fetchone()
    assert row is not None
    return int(row[0]), int(row[1])


@pytest.mark.asyncio
async def test_fifty_small_workspace_edits_measure_store_and_checkpoint_growth(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="Growth measurement")
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        await workspace.ensure_initialized(
            approved_document=created.approved_document,
            approved_revision=created.revision,
        )
        async with await psycopg.AsyncConnection.connect(
            consultant_database_url,
            autocommit=True,
        ) as connection:
            namespaces = {
                "workspace": runtime.workspace_namespace(document_id),
                "manifest": runtime.workspace_metadata_namespace(document_id),
                "decision": runtime.workspace_decision_namespace(document_id),
            }
            before = {
                name: await _store_metrics(connection, namespace)
                for name, namespace in namespaces.items()
            }
            checkpoints_before = await _checkpoint_metrics(connection, document_id)

            path = "/workspace/header.json"
            for index in range(50):
                current = await workspace.read_snapshot()
                payload = json.loads(current.files[path])
                payload["notes"] = f"小幅編輯-{index + 1:02d}"
                result = await workspace.backend.awrite(
                    path,
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                )
                assert result.error is None
                await workspace.read_snapshot()

            after = {
                name: await _store_metrics(connection, namespace)
                for name, namespace in namespaces.items()
            }
            checkpoints_after = await _checkpoint_metrics(connection, document_id)
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT DISTINCT channel FROM checkpoint_blobs WHERE thread_id = %s",
                    (str(document_id),),
                )
                checkpoint_channels = {row[0] for row in await cursor.fetchall()}

        authority_state = await runtime.raw_state(document_id)
        measurement = {
            "workspace": {"before": before["workspace"], "after": after["workspace"]},
            "manifest": {"before": before["manifest"], "after": after["manifest"]},
            "decision": {"before": before["decision"], "after": after["decision"]},
            "checkpoint": {"before": checkpoints_before, "after": checkpoints_after},
        }
        print("TASK8_GROWTH=" + json.dumps(measurement, sort_keys=True))
        assert after["workspace"][0] == before["workspace"][0]
        assert after["manifest"][0] == before["manifest"][0] == 1
        assert after["decision"] == before["decision"] == (0, 0)
        assert checkpoints_after == checkpoints_before
        assert "files" not in checkpoint_channels
        assert "files" not in authority_state
        assert "小幅編輯-50" not in json.dumps(
            authority_state,
            ensure_ascii=False,
            default=str,
        )
