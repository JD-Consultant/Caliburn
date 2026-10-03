"""Candidate navigation keeps map and target resolution on the original fixed-revision owner."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_description.areas import CreateArea, DeleteArea, EditJdAreas
from caliburn.features.job_description.navigation import (
    JdReadTargetNotFoundError,
    resolve_jd_read_ref,
)
from caliburn.features.job_description.tasks import CreateTask, EditJdTasks
from caliburn.transport.model_tools.jd_navigation import project_jd_map
from caliburn.workflows.jd_candidates import JdCandidateWorkflow

pytestmark = pytest.mark.postgres


def start_writer(client: TestClient) -> ExecutionWriter:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "導航測試", "employee_name": "合成員工"},
    )
    file_id = UUID(created.json()["job_file_id"])
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "我維護網站。"},
    )
    scope = ExecutionScope(
        file_id, UUID(accepted.json()["execution_id"]), ExecutionKind.CONSULTANT_TURN
    )

    async def claim() -> ExecutionWriter:
        async with client.app.state.database.sessions.begin() as session:
            return await executions.claim_writer(session, scope, writer_id=uuid4())

    return client.portal.call(claim)


def test_candidate_map_moves_tasks_without_losing_identity_or_changing_formal_jd(
    client: TestClient,
) -> None:
    writer = start_writer(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(workflow.start, writer)
    area_position = client.portal.call(
        workflow.edit,
        writer,
        start.scope,
        EditJdAreas(uuid4(), start.revision_id, CreateArea("網站交付", "前端範圍")),
    )
    area = client.portal.call(workflow.read, writer.scope).work.areas[0]
    task_position = client.portal.call(
        workflow.edit,
        writer,
        start.scope,
        EditJdTasks(
            uuid4(),
            area_position.revision_id,
            CreateTask(area.area_id, "實作頁面", "依確認稿交付", ("頁面", "說明"), ("符合設計稿",)),
        ),
    )
    before = client.portal.call(workflow.read, writer.scope)
    first_map = project_jd_map(before.profile, before.work)
    task_ref = first_map.responsibility_areas[0].work_tasks[0].read_ref
    area_ref = first_map.responsibility_areas[0].read_ref
    client.portal.call(
        workflow.edit,
        writer,
        start.scope,
        EditJdAreas(uuid4(), task_position.revision_id, DeleteArea(area.area_id)),
    )
    after = client.portal.call(workflow.read, writer.scope)
    second_map = project_jd_map(after.profile, after.work)
    assert second_map.responsibility_areas == []
    assert second_map.unassigned_work_tasks[0].read_ref == task_ref
    assert second_map.unassigned_work_tasks[0].outcome_count == 2
    assert resolve_jd_read_ref(after.work, task_ref) == after.work.tasks[0]
    with pytest.raises(JdReadTargetNotFoundError):
        resolve_jd_read_ref(after.work, area_ref)
    assert first_map.responsibility_areas[0].work_tasks[0].read_ref == task_ref
    assert before.position.revision_id == task_position.revision_id
    formal = client.get(f"/api/job-files/{writer.scope.job_file_id}/jd/work").json()
    assert formal["areas"] == []
    assert formal["tasks"] == []
    assert formal["revision_id"] == str(start.revision_id)


def test_map_ref_from_other_file_cannot_resolve_even_with_same_title(client: TestClient) -> None:
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    readers = []
    for _ in range(2):
        writer = start_writer(client)
        start = client.portal.call(workflow.start, writer)
        client.portal.call(
            workflow.edit,
            writer,
            start.scope,
            EditJdAreas(uuid4(), start.revision_id, CreateArea("同名職責", None)),
        )
        readers.append(client.portal.call(workflow.read, writer.scope))
    first, second = readers
    reference = project_jd_map(first.profile, first.work).responsibility_areas[0].read_ref
    with pytest.raises(JdReadTargetNotFoundError):
        resolve_jd_read_ref(second.work, reference)


def test_cancelled_execution_cannot_provide_a_fresh_navigation_base(client: TestClient) -> None:
    writer = start_writer(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    client.portal.call(workflow.start, writer)

    async def cancel() -> None:
        async with client.app.state.database.sessions.begin() as session:
            await executions.finish_execution(session, writer, ExecutionStatus.CANCELLED)

    client.portal.call(cancel)
    with pytest.raises(ExecutionStateError):
        client.portal.call(workflow.read, writer.scope)
