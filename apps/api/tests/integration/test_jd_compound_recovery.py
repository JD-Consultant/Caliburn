"""複合 JD 用例只保存一次、整包回滾，並唯讀恢復舊 checkpoint 的原操作鏈。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from uuid import UUID, uuid4, uuid5

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions.models import ExecutionWriter
from caliburn.features.job_description import source_persistence, work_queries
from caliburn.features.job_description.areas import CreateArea, EditJdAreas
from caliburn.features.job_description.candidates import JdCandidatePosition
from caliburn.features.job_description.capabilities import (
    CapabilityKind,
    CreateCapability,
    EditJdCapabilities,
    SetTaskCapability,
)
from caliburn.features.job_description.collaborators import CreateCollaborator, EditJdCollaborators
from caliburn.features.job_description.compound_edits import (
    AddedDetailSources,
    BoundItemSources,
    BoundProfileSources,
    BoundTaskCapability,
)
from caliburn.features.job_description.conditions import (
    ConditionKind,
    CreateCondition,
    EditJdConditions,
)
from caliburn.features.job_description.models import (
    JdCommandConflictError,
    ProfileField,
    ReviseJdProfile,
    SetProfileField,
)
from caliburn.features.job_description.navigation import jd_read_ref
from caliburn.features.job_description.sources import (
    AddJdSource,
    AlignJdSource,
    JdSourceReference,
    JdSourceTarget,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.features.job_description.tasks import (
    AddTaskDetail,
    CreateTask,
    DetailKind,
    EditJdTasks,
    ReviseTask,
    SetTaskField,
    TaskField,
)
from caliburn.transport.model_tools.jd_write_checkpoint import restore_jd_write, snapshot_jd_write
from caliburn.workflows.jd_candidates import (
    JdCandidateEdit,
    JdCandidateWorkflow,
    apply_candidate_edit,
)
from caliburn.workflows.jd_item_creation import JdItemCreationWorkflow, PreparedItemCreation
from caliburn.workflows.jd_item_revision import JdItemRevisionWorkflow, PreparedItemRevision
from caliburn.workflows.jd_profile_writes import JdProfileWriteWorkflow, PreparedProfileWrite
from caliburn.workflows.jd_sources import CurrentInputSourceSelection, resolve_jd_source
from caliburn.workflows.jd_task_writes import JdTaskWriteWorkflow, PreparedTaskWrite
from tests.integration.test_jd_item_creation import start_turn, transact

pytestmark = pytest.mark.postgres

type PreparedCompound = (
    PreparedProfileWrite | PreparedTaskWrite | PreparedItemCreation | PreparedItemRevision
)
type CompoundWorkflow = (
    JdProfileWriteWorkflow | JdTaskWriteWorkflow | JdItemCreationWorkflow | JdItemRevisionWorkflow
)

_TABLES = (
    "jd_revisions",
    "jd_operations",
    "jd_area_selections",
    "jd_task_selections",
    "jd_capability_selections",
    "jd_task_capabilities",
    "jd_collaborator_selections",
    "jd_condition_selections",
    "jd_source_references",
    "jd_area_revisions",
    "jd_task_revisions",
    "jd_task_details",
    "jd_capability_revisions",
    "jd_collaborator_revisions",
    "jd_condition_revisions",
)


def _counts(connection: psycopg.Connection, file_id: UUID) -> tuple[int, ...]:
    return tuple(
        connection.execute(
            sql.SQL("SELECT count(*) FROM {} WHERE job_file_id = %s").format(sql.Identifier(table)),
            (file_id,),
        ).fetchone()[0]
        for table in _TABLES
    )


def _case(
    client: TestClient, kind: str
) -> tuple[ExecutionWriter, JdCandidateWorkflow, CompoundWorkflow, PreparedCompound]:
    writer, binding = start_turn(client)
    sessions = client.app.state.database.sessions
    candidates = JdCandidateWorkflow(sessions)
    initial = client.portal.call(candidates.read, writer.scope).position
    revision = initial.revision_id
    for command_type, change in (
        (EditJdAreas, CreateArea("交付", "原職責")),
        (EditJdTasks, CreateTask(None, "原任務", "交付頁面", (), ())),
        (EditJdCapabilities, CreateCapability(CapabilityKind.SKILL, "React", "介面")),
        (EditJdCollaborators, CreateCollaborator("設計師", "共同交付")),
        (EditJdConditions, CreateCondition(ConditionKind.WORK_ENVIRONMENT, "辦公室")),
    ):
        revision = client.portal.call(
            candidates.edit, writer, initial.scope, command_type(uuid4(), revision, change)
        ).revision_id
    preview = client.portal.call(candidates.read, writer.scope)
    source = transact(
        client, lambda s: resolve_jd_source(s, binding, CurrentInputSourceSelection())
    )
    common = (uuid4(), initial.scope, revision)
    task, capability = preview.work.tasks[0], preview.work.capabilities[0]
    if kind == "profile":
        workflow = JdProfileWriteWorkflow(sessions)
        prepared = PreparedProfileWrite(
            *common,
            (
                SetProfileField(ProfileField.JOB_TITLE, "新職稱"),
                SetProfileField(ProfileField.PURPOSE, "新目的"),
            ),
            (
                BoundProfileSources(ProfileField.JOB_TITLE, (AddJdSource(source),)),
                BoundProfileSources(ProfileField.PURPOSE, (AddJdSource(source),)),
            ),
        )
    elif kind == "task":
        workflow = JdTaskWriteWorkflow(sessions)
        prepared = PreparedTaskWrite(
            *common,
            CreateTask(None, "新任務", "做新頁面", ("可用頁面",), ("交付標準",)),
            (source,),
            ((source,), (source,)),
            (BoundTaskCapability(capability.capability_id, (source,)),),
        )
    elif kind == "item_creation":
        workflow = JdItemCreationWorkflow(sessions)
        prepared = PreparedItemCreation(*common, CreateArea("新職責", "新範圍"), (source,))
    else:
        workflow = JdItemRevisionWorkflow(sessions)
        prepared = PreparedItemRevision(
            *common,
            ReviseTask(
                task.task_id,
                (
                    SetTaskField(TaskField.TITLE, "新任務名稱"),
                    AddTaskDetail(DetailKind.OUTCOME, "可用頁面"),
                ),
            ),
            (SetTaskCapability(task.task_id, capability.capability_id, True),),
            (
                BoundItemSources(
                    JdSourceTarget(SourceTargetKind.TASK, task.task_id), (AddJdSource(source),)
                ),
            ),
            (AddedDetailSources(DetailKind.OUTCOME, (source,)),),
        )
    return writer, candidates, workflow, prepared


def _later_edit(
    client: TestClient, writer: ExecutionWriter, candidates: JdCandidateWorkflow
) -> JdCandidatePosition:
    current = client.portal.call(candidates.read, writer.scope).position
    return client.portal.call(
        candidates.edit,
        writer,
        current.scope,
        ReviseJdProfile(
            uuid4(), current.revision_id, (SetProfileField(ProfileField.REPORTS_TO, "後續主管"),)
        ),
    )


@pytest.mark.parametrize("kind", ["profile", "task", "item_creation", "item_revision"])
def test_one_tool_saves_one_final_revision_and_replays_original_result_after_later_edit(
    client: TestClient, database_connection: psycopg.Connection, kind: str
) -> None:
    writer, candidates, workflow, prepared = _case(client, kind)
    file_id = writer.scope.job_file_id
    checkpoint = snapshot_jd_write(prepared)
    assert set(checkpoint) == {"kind", "payload"}
    before = _counts(database_connection, file_id)
    result = client.portal.call(workflow.execute, writer, prepared)
    preview = client.portal.call(candidates.read, writer.scope)
    after = _counts(database_connection, file_id)
    assert after[0] - before[0] == 1
    assert after[1] - before[1] == 1
    # 六個 selection 只保存最終集合一次，沒有不可見的中間修訂副本。
    expected = tuple(
        len(items)
        for items in (
            preview.work.areas,
            preview.work.tasks,
            preview.work.capabilities,
            preview.work.task_links,
            preview.work.collaborators,
            preview.work.conditions,
        )
    )
    assert tuple(a - b for a, b in zip(after[2:8], before[2:8], strict=True)) == expected
    references = transact(
        client,
        lambda s: source_persistence.read_source_references(
            s, file_id, preview.position.revision_id
        ),
    )
    assert references and all(
        r.reviewed_revision_id == preview.position.revision_id for r in references
    )
    later = _later_edit(client, writer, candidates)
    counts = _counts(database_connection, file_id)
    # 已提交但呼叫方未保存回覆：以原 checkpoint 重入仍取得同一建立身分／效果。
    assert client.portal.call(workflow.execute, writer, restore_jd_write(checkpoint)) == result
    assert client.portal.call(candidates.read, writer.scope).position == later
    assert _counts(database_connection, file_id) == counts
    with pytest.raises(JdCommandConflictError):
        client.portal.call(
            workflow.execute, writer, replace(prepared, expected_revision_id=later.revision_id)
        )


@pytest.mark.parametrize("kind", ["profile", "task", "item_creation", "item_revision"])
def test_unknown_commit_replays_persisted_result_without_duplicate_or_rewind(
    client: TestClient,
    database_connection: psycopg.Connection,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    writer, candidates, workflow, prepared = _case(client, kind)
    checkpoint = snapshot_jd_write(prepared)

    real_begin = workflow.sessions.begin

    @asynccontextmanager
    async def lose_commit_acknowledgement() -> AsyncIterator[AsyncSession]:
        async with real_begin() as session:
            yield session
        raise ConnectionError("commit acknowledgement lost after database commit")

    # 真實交易先完成 COMMIT 與連線歸還，才模擬 caller 沒有取得提交確認。
    with monkeypatch.context() as patch:
        patch.setattr(workflow.sessions, "begin", lose_commit_acknowledgement)
        with pytest.raises(ConnectionError, match="after database commit"):
            client.portal.call(workflow.execute, writer, prepared)
    metadata = database_connection.execute(
        "SELECT result_payload FROM jd_operations WHERE job_file_id = %s AND command_id = %s",
        (writer.scope.job_file_id, prepared.command_id),
    ).fetchone()[0]
    expected = (
        f"created · read_ref: {metadata['created_ref']}"
        if metadata["created_ref"] is not None
        else metadata["effect"]
    )
    later = _later_edit(client, writer, candidates)
    counts = _counts(database_connection, writer.scope.job_file_id)
    assert client.portal.call(workflow.execute, writer, restore_jd_write(checkpoint)) == expected
    assert _counts(database_connection, writer.scope.job_file_id) == counts
    assert client.portal.call(candidates.read, writer.scope).position == later


@pytest.mark.parametrize("kind", ["profile", "task", "item_creation", "item_revision"])
def test_late_source_failure_rolls_back_every_revision_selection_and_operation(
    client: TestClient,
    database_connection: psycopg.Connection,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    writer, candidates, workflow, prepared = _case(client, kind)
    before = _counts(database_connection, writer.scope.job_file_id)
    position = client.portal.call(candidates.read, writer.scope).position
    original = source_persistence.insert_source_references

    async def fail_after_insert(
        session: AsyncSession,
        job_file_id: UUID,
        revision_id: UUID,
        references: tuple[JdSourceReference, ...],
    ) -> None:
        await original(session, job_file_id, revision_id, references)
        raise ConnectionError("source write acknowledgement lost")

    with monkeypatch.context() as patch:
        patch.setattr(source_persistence, "insert_source_references", fail_after_insert)
        with pytest.raises(ConnectionError, match="acknowledgement"):
            client.portal.call(workflow.execute, writer, prepared)
    assert client.portal.call(candidates.read, writer.scope).position == position
    assert _counts(database_connection, writer.scope.job_file_id) == before
    client.portal.call(workflow.execute, writer, prepared)


async def _seed_old_transaction(
    session: AsyncSession, file_id: UUID, prepared: PreparedCompound
) -> tuple[UUID, str]:
    """固定舊版衍生 ID 規約作為資料 fixture；只在測試建立部署前操作。"""
    revision = prepared.expected_revision_id
    created = None

    async def apply(command: JdCandidateEdit) -> UUID:
        return await apply_candidate_edit(session, file_id, prepared.candidate, command)

    if isinstance(prepared, PreparedProfileWrite):
        if prepared.changes:
            revision = await apply(
                ReviseJdProfile(
                    uuid5(prepared.command_id, "profile_text"), revision, prepared.changes
                )
            )
        for group in prepared.sources:
            revision = await apply(
                ReviseJdSources(
                    uuid5(prepared.command_id, f"profile_source:{group.field}"),
                    revision,
                    JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=group.field),
                    group.changes,
                )
            )
    elif isinstance(prepared, PreparedTaskWrite):
        revision = await apply(
            EditJdTasks(uuid5(prepared.command_id, "task"), revision, prepared.task)
        )
        work = await work_queries.read_work_at(session, file_id, revision)
        created = work.tasks[-1]
        for cap in prepared.capabilities:
            revision = await apply(
                EditJdCapabilities(
                    uuid5(prepared.command_id, f"link:{cap.capability_id}"),
                    revision,
                    SetTaskCapability(created.task_id, cap.capability_id, True),
                )
            )
        groups = [(JdSourceTarget(SourceTargetKind.TASK, created.task_id), prepared.task_sources)]
        groups.extend(
            (
                JdSourceTarget(SourceTargetKind.DETAIL, detail.detail_id, task_id=created.task_id),
                sources,
            )
            for detail, sources in zip(created.details, prepared.detail_sources, strict=True)
        )
        groups.extend(
            (
                JdSourceTarget(
                    SourceTargetKind.TASK_CAPABILITY, cap.capability_id, task_id=created.task_id
                ),
                cap.sources,
            )
            for cap in prepared.capabilities
        )
        for index, (target, sources) in enumerate(groups):
            if sources:
                revision = await apply(
                    ReviseJdSources(
                        uuid5(prepared.command_id, f"source:{index}"),
                        revision,
                        target,
                        tuple(AddJdSource(s) for s in sources),
                    )
                )
    elif isinstance(prepared, PreparedItemCreation):
        revision = await apply(
            EditJdAreas(uuid5(prepared.command_id, "item"), revision, prepared.item)
        )
        work = await work_queries.read_work_at(session, file_id, revision)
        created = work.areas[-1]
        revision = await apply(
            ReviseJdSources(
                uuid5(prepared.command_id, "sources"),
                revision,
                JdSourceTarget(SourceTargetKind.AREA, created.area_id),
                tuple(AddJdSource(s) for s in prepared.sources),
            )
        )
    else:
        revision = await apply(
            EditJdTasks(uuid5(prepared.command_id, "content"), revision, prepared.content)
        )
        work = await work_queries.read_work_at(session, file_id, revision)
        task = work.tasks[0]
        for index, cap in enumerate(prepared.capabilities):
            revision = await apply(
                EditJdCapabilities(uuid5(prepared.command_id, f"capability:{index}"), revision, cap)
            )
        groups = (
            *prepared.sources,
            BoundItemSources(
                JdSourceTarget(
                    SourceTargetKind.DETAIL, task.details[-1].detail_id, task_id=task.task_id
                ),
                tuple(AddJdSource(s) for s in prepared.added_details[0].sources),
            ),
        )
        for index, group in enumerate(groups):
            revision = await apply(
                ReviseJdSources(
                    uuid5(prepared.command_id, f"source:{index}"),
                    revision,
                    group.target,
                    group.changes,
                )
            )
    return (
        revision,
        f"created · read_ref: {jd_read_ref(created)}" if created is not None else "updated",
    )


@pytest.mark.parametrize("kind", ["profile", "task", "item_creation", "item_revision"])
def test_old_unversioned_checkpoint_recovers_all_original_suboperations_without_new_writes(
    client: TestClient, database_connection: psycopg.Connection, kind: str
) -> None:
    writer, candidates, workflow, prepared = _case(client, kind)
    checkpoint = snapshot_jd_write(prepared)
    revision, result = transact(
        client, lambda s: _seed_old_transaction(s, writer.scope.job_file_id, prepared)
    )
    assert client.portal.call(candidates.read, writer.scope).position.revision_id == revision
    later = _later_edit(client, writer, candidates)
    before = _counts(database_connection, writer.scope.job_file_id)
    assert client.portal.call(workflow.execute, writer, restore_jd_write(checkpoint)) == result
    assert _counts(database_connection, writer.scope.job_file_id) == before
    assert client.portal.call(candidates.read, writer.scope).position == later


@pytest.mark.parametrize("kind", ["profile", "task", "item_creation", "item_revision"])
def test_omitting_a_legacy_source_tail_rejects_changed_intent_and_keeps_original_result(
    client: TestClient, database_connection: psycopg.Connection, kind: str
) -> None:
    writer, candidates, workflow, prepared = _case(client, kind)
    checkpoint = snapshot_jd_write(prepared)
    original_revision, original_result = transact(
        client, lambda s: _seed_old_transaction(s, writer.scope.job_file_id, prepared)
    )
    if isinstance(prepared, PreparedProfileWrite):
        altered = replace(prepared, sources=prepared.sources[:1])
    elif isinstance(prepared, PreparedTaskWrite):
        altered = replace(
            prepared, capabilities=tuple(replace(c, sources=()) for c in prepared.capabilities)
        )
    elif isinstance(prepared, PreparedItemCreation):
        altered = replace(prepared, sources=())
    else:
        altered = replace(
            prepared, added_details=tuple(replace(d, sources=()) for d in prepared.added_details)
        )
    before = _counts(database_connection, writer.scope.job_file_id)
    with pytest.raises(JdCommandConflictError):
        client.portal.call(workflow.execute, writer, altered)
    assert _counts(database_connection, writer.scope.job_file_id) == before
    assert (
        client.portal.call(candidates.read, writer.scope).position.revision_id == original_revision
    )
    assert (
        client.portal.call(workflow.execute, writer, restore_jd_write(checkpoint))
        == original_result
    )


def test_omitting_a_legacy_noop_tail_is_also_a_command_conflict(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    writer, candidates, workflow, prepared = _case(client, "profile")
    assert isinstance(prepared, PreparedProfileWrite)
    transact(client, lambda s: _seed_old_transaction(s, writer.scope.job_file_id, prepared))
    position = client.portal.call(candidates.read, writer.scope).position
    repeated = replace(prepared, command_id=uuid4(), expected_revision_id=position.revision_id)
    transact(client, lambda s: _seed_old_transaction(s, writer.scope.job_file_id, repeated))
    before = _counts(database_connection, writer.scope.job_file_id)
    with pytest.raises(JdCommandConflictError):
        client.portal.call(
            workflow.execute, writer, replace(repeated, sources=repeated.sources[:1])
        )
    assert _counts(database_connection, writer.scope.job_file_id) == before
    assert client.portal.call(workflow.execute, writer, repeated) == "unchanged"
    assert client.portal.call(candidates.read, writer.scope).position == position


def test_legacy_task_sparse_source_indexes_are_recovered_and_cannot_be_omitted(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    writer, candidates, workflow, prepared = _case(client, "task")
    assert isinstance(prepared, PreparedTaskWrite)
    sparse = replace(prepared, task_sources=(), detail_sources=((), ()))
    revision, result = transact(
        client, lambda s: _seed_old_transaction(s, writer.scope.job_file_id, sparse)
    )
    before = _counts(database_connection, writer.scope.job_file_id)
    assert client.portal.call(workflow.execute, writer, sparse) == result
    altered = replace(
        sparse, capabilities=tuple(replace(c, sources=()) for c in sparse.capabilities)
    )
    with pytest.raises(JdCommandConflictError):
        client.portal.call(workflow.execute, writer, altered)
    assert _counts(database_connection, writer.scope.job_file_id) == before
    assert client.portal.call(candidates.read, writer.scope).position.revision_id == revision


def test_new_first_step_cannot_rewrite_an_existing_source_only_legacy_noop(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    writer, candidates, workflow, prepared = _case(client, "profile")
    assert isinstance(prepared, PreparedProfileWrite)
    transact(client, lambda s: _seed_old_transaction(s, writer.scope.job_file_id, prepared))
    position = client.portal.call(candidates.read, writer.scope).position
    repeated = replace(
        prepared,
        command_id=uuid4(),
        expected_revision_id=position.revision_id,
        changes=(),
        sources=prepared.sources[:1],
    )
    transact(client, lambda s: _seed_old_transaction(s, writer.scope.job_file_id, repeated))
    altered = replace(repeated, changes=(SetProfileField(ProfileField.JOB_TITLE, "不同意圖"),))
    before = _counts(database_connection, writer.scope.job_file_id)
    with pytest.raises(JdCommandConflictError):
        client.portal.call(workflow.execute, writer, altered)
    assert _counts(database_connection, writer.scope.job_file_id) == before
    assert client.portal.call(workflow.execute, writer, repeated) == "unchanged"
    assert client.portal.call(candidates.read, writer.scope).position == position


def test_text_change_plus_explicit_alignment_uses_final_revision_as_reviewed_base(
    client: TestClient,
) -> None:
    writer, candidates, workflow, prepared = _case(client, "profile")
    client.portal.call(workflow.execute, writer, prepared)
    preview = client.portal.call(candidates.read, writer.scope)
    references = transact(
        client,
        lambda s: source_persistence.read_source_references(
            s, writer.scope.job_file_id, preview.position.revision_id
        ),
    )
    title = next(r for r in references if r.target.field == ProfileField.JOB_TITLE)
    revised = PreparedProfileWrite(
        uuid4(),
        prepared.candidate,
        preview.position.revision_id,
        (SetProfileField(ProfileField.JOB_TITLE, "修訂職稱"),),
        (
            BoundProfileSources(
                ProfileField.JOB_TITLE, (AlignJdSource(title.citation_id, title.source),)
            ),
        ),
    )
    assert client.portal.call(workflow.execute, writer, revised) == "updated"
    preview = client.portal.call(candidates.read, writer.scope)
    references = transact(
        client,
        lambda s: source_persistence.read_source_references(
            s, writer.scope.job_file_id, preview.position.revision_id
        ),
    )
    aligned = next(r for r in references if r.citation_id == title.citation_id)
    assert not aligned.needs_review
    assert aligned.reviewed_revision_id == preview.position.revision_id


def test_unchanged_compound_records_original_effect_without_new_revision(
    client, database_connection
):
    writer, candidates, workflow, prepared = _case(client, "profile")
    client.portal.call(workflow.execute, writer, prepared)
    position = client.portal.call(candidates.read, writer.scope).position
    unchanged = replace(prepared, command_id=uuid4(), expected_revision_id=position.revision_id)
    before = _counts(database_connection, writer.scope.job_file_id)
    assert client.portal.call(workflow.execute, writer, unchanged) == "unchanged"
    after = _counts(database_connection, writer.scope.job_file_id)
    assert after[0] == before[0]
    assert after[1] == before[1] + 1
    assert after[2:] == before[2:]
    later = _later_edit(client, writer, candidates)
    assert client.portal.call(workflow.execute, writer, unchanged) == "unchanged"
    assert client.portal.call(candidates.read, writer.scope).position == later


def test_incomplete_legacy_chain_is_rejected_without_rewriting_it(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    writer, candidates, workflow, prepared = _case(client, "profile")
    # 模擬損壞的舊資料：僅保存第一筆操作；既有不可變 trigger 不容刪改回執。
    transact(
        client,
        lambda s: apply_candidate_edit(
            s,
            writer.scope.job_file_id,
            prepared.candidate,
            ReviseJdProfile(
                uuid5(prepared.command_id, "profile_text"),
                prepared.expected_revision_id,
                prepared.changes,
            ),
        ),
    )
    before = _counts(database_connection, writer.scope.job_file_id)
    position = client.portal.call(candidates.read, writer.scope).position
    with pytest.raises(RuntimeError, match="missing suboperations"):
        client.portal.call(workflow.execute, writer, prepared)
    assert _counts(database_connection, writer.scope.job_file_id) == before
    assert client.portal.call(candidates.read, writer.scope).position == position


def test_formal_completion_adopts_compound_and_undo_restores_original_base(
    client: TestClient,
) -> None:
    from caliburn.workflows.jd_task_writes import CreateTaskInput, TaskDetailInput
    from caliburn.workflows.jd_undo import JdUndoWorkflow
    from caliburn.workflows.memory_reads import PublishedMemoryRead
    from tests.integration.test_consultant_completion import complete
    from tests.integration.test_consultant_completion import start_turn as start_completion_turn

    turn = start_completion_turn(client)
    sessions = client.app.state.database.sessions
    candidates = JdCandidateWorkflow(sessions)
    tasks = JdTaskWriteWorkflow(sessions)
    file_id = turn.writer.scope.job_file_id

    async def prepare() -> PreparedTaskWrite:
        return await tasks.prepare(
            PublishedMemoryRead(turn.writer.scope, None, 1),
            command_id=uuid4(),
            intent=CreateTaskInput(
                None,
                "完成工具操作",
                "保存任務與來源",
                outcomes=(TaskDetailInput("最終成果", (CurrentInputSourceSelection(),)),),
                sources=(CurrentInputSourceSelection(),),
            ),
        )

    prepared = client.portal.call(prepare)
    client.portal.call(tasks.execute, turn.writer, prepared)
    final = client.portal.call(candidates.read, turn.writer.scope).position
    complete(client, replace(turn, candidate=final))
    official = transact(client, lambda s: work_queries.read_work(s, file_id))
    assert official.revision_id == final.revision_id and len(official.tasks) == 1
    history = client.get(f"/api/job-files/{file_id}/interviews").json()
    undone = client.portal.call(
        JdUndoWorkflow(sessions).undo, file_id, turn.writer.scope.execution_id
    )
    assert undone.revision_id not in {final.base_revision_id, final.revision_id}
    assert undone.profile.job_title is None
    official = transact(client, lambda s: work_queries.read_work(s, file_id))
    assert official.tasks == () and official.revision_id == undone.revision_id
    assert (
        transact(
            client,
            lambda s: source_persistence.read_source_references(s, file_id, undone.revision_id),
        )
        == ()
    )
    assert client.get(f"/api/job-files/{file_id}/interviews").json() == history


@pytest.mark.parametrize("legacy", [False, True])
def test_owner_returns_original_created_item_and_final_revision_after_later_edit(
    client: TestClient, legacy: bool
) -> None:
    from caliburn.features.executions import service as executions
    from caliburn.features.job_description import compound_service, revision_editing
    from caliburn.features.job_description.compound_edits import (
        CreateTaskWithSources,
        JdCompoundEditResult,
    )
    from caliburn.features.job_description.tasks import WorkTask
    from caliburn.features.job_files import service as job_files

    writer, candidates, workflow, prepared = _case(client, "task")
    assert isinstance(prepared, PreparedTaskWrite)
    if legacy:
        original_revision, text = transact(
            client, lambda s: _seed_old_transaction(s, writer.scope.job_file_id, prepared)
        )
    else:
        text = client.portal.call(workflow.execute, writer, prepared)
        original_revision = client.portal.call(candidates.read, writer.scope).position.revision_id
    later = _later_edit(client, writer, candidates)
    command = CreateTaskWithSources(
        prepared.command_id,
        prepared.expected_revision_id,
        prepared.task,
        prepared.task_sources,
        prepared.detail_sources,
        prepared.capabilities,
    )

    async def replay(session: AsyncSession) -> JdCompoundEditResult:
        await job_files.lock_job_file(session, writer.scope.job_file_id)
        await executions.lock_active_writer(session, writer)
        await revision_editing.require_open_candidate(
            session, writer.scope.job_file_id, prepared.candidate
        )
        return await compound_service.apply_compound_edit(
            session, writer.scope.job_file_id, command, candidate=prepared.candidate
        )

    original = transact(client, replay)
    assert original.revision_id == original_revision
    assert original.effect == "created" and isinstance(original.created_item, WorkTask)
    assert f"created · read_ref: {jd_read_ref(original.created_item)}" == text
    assert original.created_item.title == prepared.task.title
    assert len(original.created_item.details) == 2
    assert client.portal.call(candidates.read, writer.scope).position == later
