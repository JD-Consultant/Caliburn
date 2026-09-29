"""Candidate positions are recoverable without exposing edits through the formal JD head."""

from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
    StaleWriterError,
)
from caliburn.features.job_description import candidate_service, persistence
from caliburn.features.job_description.areas import CreateArea, DeleteArea, EditJdAreas
from caliburn.features.job_description.candidates import CandidateStateError
from caliburn.features.job_description.capabilities import (
    CapabilityKind,
    CreateCapability,
    EditJdCapabilities,
    SetTaskCapability,
)
from caliburn.features.job_description.collaborators import CreateCollaborator, EditJdCollaborators
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
    StaleJdRevisionError,
)
from caliburn.features.job_description.tasks import CreateTask, EditJdTasks
from caliburn.workflows.interview_completion import record_formal_interview
from caliburn.workflows.jd_candidates import JdCandidateWorkflow, adopt_candidate_jd

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


def start_writer(client: TestClient) -> ExecutionWriter:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "候選測試", "employee_name": "合成員工"},
    )
    file_id = UUID(created.json()["job_file_id"])
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "我維護前端網站。"},
    )
    assert accepted.status_code == 202
    scope = ExecutionScope(
        file_id, UUID(accepted.json()["execution_id"]), ExecutionKind.CONSULTANT_TURN
    )
    return transact(client, lambda s: executions.claim_writer(s, scope, writer_id=uuid4()))


def profile_edit(revision_id: UUID, text: str) -> ReviseJdProfile:
    return ReviseJdProfile(uuid4(), revision_id, (SetProfileField(ProfileField.JOB_TITLE, text),))


def test_candidate_is_private_and_original_edit_can_be_recovered(client: TestClient) -> None:
    writer = start_writer(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(workflow.start, writer)
    command = profile_edit(start.revision_id, "前端工程師")
    first = client.portal.call(workflow.edit, writer, start.scope, command)
    second = client.portal.call(
        workflow.edit, writer, start.scope, profile_edit(first.revision_id, "網站工程師")
    )
    assert first.revision_id != start.revision_id
    assert second.revision_id != first.revision_id
    assert client.portal.call(workflow.edit, writer, start.scope, command) == first
    preview = client.portal.call(workflow.read, writer.scope)
    assert preview.position.revision_id == second.revision_id
    assert preview.profile.job_title == "網站工程師"
    formal = client.get(f"/api/job-files/{writer.scope.job_file_id}/jd/profile").json()
    assert formal["revision_id"] == str(start.revision_id)
    assert formal["profile"]["job_title"] is None


def test_restore_revokes_old_generation_and_is_itself_replayable(client: TestClient) -> None:
    writer = start_writer(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(workflow.start, writer)
    first_command = profile_edit(start.revision_id, "安全點")
    first = client.portal.call(workflow.edit, writer, start.scope, first_command)
    second = client.portal.call(
        workflow.edit, writer, start.scope, profile_edit(first.revision_id, "未完成")
    )
    restore_id = uuid4()
    restored = client.portal.call(workflow.restore, writer, second, first.revision_id, restore_id)
    assert restored.scope.generation_id != start.scope.generation_id
    assert restored.revision_id == first.revision_id
    with pytest.raises(CandidateStateError):
        client.portal.call(workflow.edit, writer, start.scope, first_command)
    newer = client.portal.call(
        workflow.edit, writer, restored.scope, profile_edit(restored.revision_id, "接續")
    )
    assert (
        client.portal.call(workflow.restore, writer, second, first.revision_id, restore_id)
        == restored
    )
    assert client.portal.call(workflow.read, writer.scope).position == newer


def test_pause_disallows_edits_but_keeps_preview(client: TestClient) -> None:
    writer = start_writer(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(workflow.start, writer)
    transact(client, lambda s: executions.pause_execution(s, writer))
    assert client.portal.call(workflow.read, writer.scope).position == start
    with pytest.raises(ExecutionStateError):
        client.portal.call(
            workflow.edit, writer, start.scope, profile_edit(start.revision_id, "不應保存")
        )
    transact(client, lambda s: executions.resume_execution(s, writer))
    assert (
        client.portal.call(
            workflow.edit, writer, start.scope, profile_edit(start.revision_id, "恢復")
        ).revision_id
        != start.revision_id
    )


def test_discard_is_not_formal_undo_and_cannot_reopen(client: TestClient) -> None:
    writer = start_writer(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(workflow.start, writer)
    changed = client.portal.call(
        workflow.edit, writer, start.scope, profile_edit(start.revision_id, "放棄")
    )
    operation_id = uuid4()
    client.portal.call(workflow.discard, writer, changed, operation_id)
    client.portal.call(workflow.discard, writer, changed, operation_id)
    with pytest.raises(CandidateStateError):
        client.portal.call(workflow.start, writer)
    with pytest.raises(CandidateStateError):
        client.portal.call(workflow.read, writer.scope)
    with pytest.raises(CandidateStateError):
        client.portal.call(
            workflow.edit, writer, start.scope, profile_edit(changed.revision_id, "遲到")
        )
    transact(client, lambda s: executions.finish_execution(s, writer, ExecutionStatus.CANCELLED))
    formal = client.get(f"/api/job-files/{writer.scope.job_file_id}/jd/profile").json()
    assert formal["revision_id"] == str(start.revision_id)


def test_all_collection_edits_reuse_candidate_and_preserve_unaffected_relations(
    client: TestClient,
) -> None:
    writer = start_writer(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(workflow.start, writer)
    area = client.portal.call(
        workflow.edit,
        writer,
        start.scope,
        EditJdAreas(uuid4(), start.revision_id, CreateArea("網站交付", None)),
    )
    area_id = client.portal.call(workflow.read, writer.scope).work.areas[0].area_id
    task = client.portal.call(
        workflow.edit,
        writer,
        start.scope,
        EditJdTasks(
            uuid4(),
            area.revision_id,
            CreateTask(area_id, "實作頁面", None, ("已交付頁面",), ("符合設計稿",)),
        ),
    )
    task_id = client.portal.call(workflow.read, writer.scope).work.tasks[0].task_id
    capability = client.portal.call(
        workflow.edit,
        writer,
        start.scope,
        EditJdCapabilities(
            uuid4(), task.revision_id, CreateCapability(CapabilityKind.KNOWLEDGE, "API 狀態", None)
        ),
    )
    capability_id = (
        client.portal.call(workflow.read, writer.scope).work.capabilities[0].capability_id
    )
    linked = client.portal.call(
        workflow.edit,
        writer,
        start.scope,
        EditJdCapabilities(
            uuid4(), capability.revision_id, SetTaskCapability(task_id, capability_id, True)
        ),
    )
    collaborator = client.portal.call(
        workflow.edit,
        writer,
        start.scope,
        EditJdCollaborators(
            uuid4(), linked.revision_id, CreateCollaborator("後端工程師", "確認資料契約")
        ),
    )
    condition = client.portal.call(
        workflow.edit,
        writer,
        start.scope,
        EditJdConditions(
            uuid4(),
            collaborator.revision_id,
            CreateCondition(ConditionKind.SHARED_AUTHORITY, "不更改後端資料庫"),
        ),
    )
    deleted = client.portal.call(
        workflow.edit,
        writer,
        start.scope,
        EditJdAreas(uuid4(), condition.revision_id, DeleteArea(area_id)),
    )
    final = client.portal.call(
        workflow.edit, writer, start.scope, profile_edit(deleted.revision_id, "前端工程師")
    )
    preview = client.portal.call(workflow.read, writer.scope)
    assert preview.position == final
    assert preview.work.areas == ()
    assert preview.work.tasks[0].area_id is None
    assert len(preview.work.tasks[0].details) == 2
    assert preview.work.task_links[0].capability_id == capability_id
    assert preview.work.collaborators[0].name == "後端工程師"
    assert preview.work.conditions[0].text == "不更改後端資料庫"
    formal = client.get(f"/api/job-files/{writer.scope.job_file_id}/jd/work").json()
    assert formal["revision_id"] == str(start.revision_id)
    assert all(
        formal[key] == []
        for key in ("areas", "tasks", "capabilities", "task_links", "collaborators", "conditions")
    )


def test_adoption_joins_formal_interview_transaction_and_recovery(client: TestClient) -> None:
    writer = start_writer(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(workflow.start, writer)
    changed = client.portal.call(
        workflow.edit, writer, start.scope, profile_edit(start.revision_id, "前端工程師")
    )
    operation_id = uuid4()

    async def complete(session: AsyncSession) -> None:
        await adopt_candidate_jd(session, writer, changed, operation_id)
        await record_formal_interview(session, writer, reply_text="頁面交付時通常怎麼驗收？")
        await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)

    async def fail_after_effects(session: AsyncSession) -> None:
        await complete(session)
        raise RuntimeError("injected before commit")

    with pytest.raises(RuntimeError, match="injected"):
        transact(client, fail_after_effects)
    assert client.portal.call(workflow.read, writer.scope).position == changed
    assert client.get(f"/api/job-files/{writer.scope.job_file_id}/jd/profile").json()[
        "revision_id"
    ] == str(start.revision_id)
    assert (
        transact(
            client, lambda s: persistence.read_operation(s, writer.scope.job_file_id, operation_id)
        )
        is None
    )
    transact(client, complete)
    transact(client, complete)
    assert client.get(f"/api/job-files/{writer.scope.job_file_id}/jd/profile").json()[
        "revision_id"
    ] == str(changed.revision_id)
    assert (
        transact(client, lambda s: executions.read_execution(s, writer.scope)).status
        == ExecutionStatus.COMPLETED
    )
    # This is a composition test, not the T08 production final/background/source workflow.


def test_restore_cannot_select_other_turn_or_discarded_branch(client: TestClient) -> None:
    writer = start_writer(client)
    other = start_writer(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(workflow.start, writer)
    foreign = client.portal.call(workflow.start, other)
    with pytest.raises(CandidateStateError):
        client.portal.call(workflow.restore, writer, start, foreign.revision_id, uuid4())
    first = client.portal.call(
        workflow.edit, writer, start.scope, profile_edit(start.revision_id, "舊分支")
    )
    restored = client.portal.call(workflow.restore, writer, first, start.revision_id, uuid4())
    with pytest.raises(CandidateStateError):
        client.portal.call(workflow.restore, writer, restored, first.revision_id, uuid4())
    with pytest.raises(CandidateStateError):
        client.portal.call(
            workflow.edit, other, start.scope, profile_edit(start.revision_id, "別份檔案")
        )


def test_new_writer_can_recover_but_old_writer_cannot_write(client: TestClient) -> None:
    writer = start_writer(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(workflow.start, writer)
    command = profile_edit(start.revision_id, "原效果")
    changed = client.portal.call(workflow.edit, writer, start.scope, command)
    replacement = transact(
        client,
        lambda s: executions.claim_writer(
            s, writer.scope, writer_id=uuid4(), replaces_writer_id=writer.writer_id
        ),
    )
    assert client.portal.call(workflow.edit, replacement, start.scope, command) == changed
    with pytest.raises(StaleWriterError):
        client.portal.call(
            workflow.edit, writer, start.scope, profile_edit(changed.revision_id, "遲到結果")
        )


def test_candidate_command_identity_cannot_be_used_for_a_manual_edit(client: TestClient) -> None:
    writer = start_writer(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(workflow.start, writer)
    command = profile_edit(start.revision_id, "原效果")
    client.portal.call(workflow.edit, writer, start.scope, command)
    with pytest.raises(JdCommandConflictError):
        client.portal.call(
            workflow.edit,
            writer,
            start.scope,
            replace(command, changes=(SetProfileField(ProfileField.JOB_TITLE, "不同意圖"),)),
        )
    response = client.post(
        f"/api/job-files/{writer.scope.job_file_id}/jd/profile",
        json={
            "command_id": str(command.command_id),
            "expected_revision_id": str(command.expected_revision_id),
            "changes": [{"action": "set_field", "field": "job_title", "value": "原效果"}],
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "jd_command_conflict"


def test_parallel_edits_only_one_can_advance_the_same_candidate_base(client: TestClient) -> None:
    writer = start_writer(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(workflow.start, writer)

    def edit(index: int) -> bool:
        try:
            client.portal.call(
                workflow.edit, writer, start.scope, profile_edit(start.revision_id, f"工作{index}")
            )
            return True
        except StaleJdRevisionError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(edit, (1, 2))).count(True) == 1


def test_abandonment_can_join_execution_cancellation_from_pause(client: TestClient) -> None:
    writer = start_writer(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(workflow.start, writer)
    transact(client, lambda s: executions.pause_execution(s, writer))

    async def cancel(session: AsyncSession) -> None:
        await executions.lock_unfinished_writer(session, writer)
        await candidate_service.discard_candidate(session, writer.scope.job_file_id, start, uuid4())
        await executions.finish_execution(session, writer, ExecutionStatus.CANCELLED)

    transact(client, cancel)
    with pytest.raises(ExecutionStateError):
        client.portal.call(workflow.read, writer.scope)
