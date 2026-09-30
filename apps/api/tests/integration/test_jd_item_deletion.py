"""A deletes scoped draft items; replay never deletes another item or formal content."""

from uuid import UUID, uuid4

import pytest

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.job_description.areas import CreateArea, EditJdAreas
from caliburn.features.job_description.capabilities import (
    CapabilityInUseError,
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
from caliburn.features.job_description.navigation import jd_read_ref
from caliburn.features.job_description.tasks import CreateTask, EditJdTasks
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_item_deletion import JdItemDeletionWorkflow
from caliburn.workflows.memory_reads import PublishedMemoryRead

pytestmark = pytest.mark.postgres


def test_area_delete_preserves_tasks_replays_original_and_rejects_used_capability(client):
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "刪除測試",
                "employee_name": "合成",
            },
        ).json()["job_file_id"]
    )
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={
            "command_id": str(uuid4()),
            "text": "合成案例",
        },
    ).json()
    scope = ExecutionScope(file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN)

    async def scenario():
        sessions = client.app.state.database.sessions
        async with sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        candidate = JdCandidateWorkflow(sessions)
        position = await candidate.start(writer)
        position = await candidate.edit(
            writer,
            position.scope,
            EditJdAreas(
                uuid4(),
                position.revision_id,
                CreateArea("例行盤點", "庫存核對"),
            ),
        )
        area = (await candidate.read(scope)).work.areas[0]
        position = await candidate.edit(
            writer,
            position.scope,
            EditJdTasks(
                uuid4(),
                position.revision_id,
                CreateTask(area.area_id, "核對庫存", "逐項核對", (), ()),
            ),
        )
        deletion = JdItemDeletionWorkflow(sessions)
        prepared = await deletion.prepare(
            PublishedMemoryRead(scope, None, 1), command_id=uuid4(), read_ref=jd_read_ref(area)
        )
        result = await deletion.execute(writer, prepared)
        preview = await candidate.read(scope)
        assert not preview.work.areas
        assert preview.work.tasks[0].area_id is None
        assert "1" in result and "未歸屬" in result
        assert await deletion.execute(writer, prepared) == result
        assert (await candidate.read(scope)).position == preview.position

        position = await candidate.edit(
            writer,
            preview.position.scope,
            EditJdCapabilities(
                uuid4(),
                preview.position.revision_id,
                CreateCapability(CapabilityKind.KNOWLEDGE, "庫存概念", "理解帳物關係"),
            ),
        )
        capability = (await candidate.read(scope)).work.capabilities[0]
        position = await candidate.edit(
            writer,
            position.scope,
            EditJdCapabilities(
                uuid4(),
                position.revision_id,
                SetTaskCapability(preview.work.tasks[0].task_id, capability.capability_id, True),
            ),
        )
        with pytest.raises(CapabilityInUseError):
            await deletion.prepare(
                PublishedMemoryRead(scope, None, 1),
                command_id=uuid4(),
                read_ref=jd_read_ref(capability),
            )
        assert (await candidate.read(scope)).position == position

    client.portal.call(scenario)
    assert client.get(f"/api/job-files/{file_id}/jd/work").json()["areas"] == []


def test_task_collaborator_and_condition_delete_keep_shared_knowledge_and_replay_once(client):
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "刪除三類項目",
                "employee_name": "合成",
            },
        ).json()["job_file_id"]
    )
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "合成案例"},
    ).json()
    scope = ExecutionScope(file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN)

    async def scenario():
        sessions = client.app.state.database.sessions
        async with sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        candidate = JdCandidateWorkflow(sessions)
        position = await candidate.start(writer)

        async def edit(command_type, change):
            nonlocal position
            position = await candidate.edit(
                writer, position.scope, command_type(uuid4(), position.revision_id, change)
            )
            return (await candidate.read(scope)).work

        await edit(
            EditJdTasks, CreateTask(None, "核對庫存", "逐項核對", ("盤點報表",), ("雙人覆核",))
        )
        work = await edit(
            EditJdCapabilities,
            CreateCapability(CapabilityKind.KNOWLEDGE, "庫存概念", "理解帳物關係"),
        )
        task, knowledge = work.tasks[0], work.capabilities[0]
        assert len(task.details) == 2
        await edit(
            EditJdCapabilities, SetTaskCapability(task.task_id, knowledge.capability_id, True)
        )
        await edit(EditJdCollaborators, CreateCollaborator("倉管", "每日對帳"))
        work = await edit(
            EditJdConditions, CreateCondition(ConditionKind.WORK_ENVIRONMENT, "倉庫作業")
        )
        collaborator, condition = work.collaborators[0], work.conditions[0]

        deletion = JdItemDeletionWorkflow(sessions)
        binding = PublishedMemoryRead(scope, None, 1)

        async def delete(item):
            prepared = await deletion.prepare(
                binding, command_id=uuid4(), read_ref=jd_read_ref(item)
            )
            result = await deletion.execute(writer, prepared)
            after = await candidate.read(scope)
            # The same prepared operation returns its original result and changes nothing.
            assert await deletion.execute(writer, prepared) == result
            assert (await candidate.read(scope)).position == after.position
            return after.work

        work = await delete(task)
        # The task's own details and its knowledge link are gone; the shared definition stays.
        assert work.tasks == ()
        assert work.task_links == ()
        assert [item.capability_id for item in work.capabilities] == [knowledge.capability_id]
        assert [item.collaborator_id for item in work.collaborators] == [
            collaborator.collaborator_id
        ]
        assert [item.condition_id for item in work.conditions] == [condition.condition_id]

        work = await delete(collaborator)
        assert work.collaborators == ()
        assert [item.condition_id for item in work.conditions] == [condition.condition_id]

        work = await delete(condition)
        assert work.conditions == ()
        assert [item.capability_id for item in work.capabilities] == [knowledge.capability_id]

    client.portal.call(scenario)
    formal = client.get(f"/api/job-files/{file_id}/jd/work").json()
    assert formal["tasks"] == [] and formal["collaborators"] == [] and formal["conditions"] == []
