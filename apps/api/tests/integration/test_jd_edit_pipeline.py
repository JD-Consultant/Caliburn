"""共同內容入口保持原結果與意圖，SQL 觀察不作效能承諾。"""

import json
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event

from caliburn.features.job_description import persistence, revision_editing, source_service
from caliburn.features.job_description.areas import CreateArea, EditJdAreas
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
)
from caliburn.features.job_description.source_targets import source_target_contents
from caliburn.features.job_description.sources import (
    AddJdSource,
    InterviewSource,
    ReviseJdSources,
    TaskSourceContents,
)
from caliburn.features.job_description.tasks import CreateTask, EditJdTasks
from caliburn.features.job_files import service as job_files
from caliburn.workflows.job_description.manual_editing import JdEditingWorkflow
from tests.integration.test_jd_profile import create_file

pytestmark = pytest.mark.postgres

_EDITS = (
    (ReviseJdProfile, (SetProfileField(ProfileField.JOB_TITLE, "原職稱"),)),
    (EditJdAreas, CreateArea("原職責", None)),
    (EditJdTasks, CreateTask(None, "原任務", None, (), ())),
    (EditJdCapabilities, CreateCapability(CapabilityKind.SKILL, "原技能", None)),
    (EditJdCollaborators, CreateCollaborator("原協作", None)),
    (EditJdConditions, CreateCondition(ConditionKind.WORK_ENVIRONMENT, "原環境")),
)


@pytest.mark.parametrize(("command_type", "change"), _EDITS)
def test_common_content_owner_recovers_original_without_rewinding(client, command_type, change):
    apply = getattr(revision_editing, "apply_content_edit", None)
    recover = getattr(revision_editing, "recover_content_edit", None)
    assert callable(apply) and callable(recover), "六類內容應使用同一修訂入口"
    file_id = UUID(create_file(client))

    async def scenario():
        async with client.app.state.database.sessions.begin() as session:
            await job_files.lock_job_file(session, file_id)
            base = (await persistence.read_document(session, file_id)).current_revision_id
            command = command_type(uuid4(), base, change)
            assert await recover(session, file_id, command) is None
            original = await apply(session, file_id, command)
            later = await apply(
                session,
                file_id,
                ReviseJdProfile(
                    uuid4(),
                    original,
                    (SetProfileField(ProfileField.REPORTS_TO, "後續主管"),),
                ),
            )
            assert await recover(session, file_id, command) == original
            assert (await persistence.read_document(session, file_id)).current_revision_id == later
            with pytest.raises(JdCommandConflictError):
                await recover(session, file_id, replace(command, expected_revision_id=later))

    client.portal.call(scenario)


@pytest.mark.parametrize("fixture_kind", ("empty", "full", "full_with_sources"))
def test_profile_sql_observation_keeps_change_noop_and_replay(
    client, database_connection, fixture_kind
):
    file_id = UUID(create_file(client))
    workflow = JdEditingWorkflow(client.app.state.database.sessions)
    initial = client.portal.call(workflow.read_profile, file_id)
    if fixture_kind != "empty":
        initial = client.portal.call(
            workflow.revise_profile,
            file_id,
            ReviseJdProfile(
                uuid4(), initial.revision_id, (SetProfileField(ProfileField.JOB_TITLE, "原職稱"),)
            ),
        )
        areas = client.portal.call(
            workflow.edit_areas,
            file_id,
            EditJdAreas(uuid4(), initial.revision_id, CreateArea("原職責", "職責範圍")),
        )
        tasks = client.portal.call(
            workflow.edit_tasks,
            file_id,
            EditJdTasks(
                uuid4(),
                areas.revision_id,
                CreateTask(areas.areas[0].area_id, "原任務", "任務正文", ("產出",), ("要求",)),
            ),
        )
        capabilities = client.portal.call(
            workflow.edit_capabilities,
            file_id,
            EditJdCapabilities(
                uuid4(),
                tasks.revision_id,
                CreateCapability(CapabilityKind.SKILL, "原技能", "能力正文"),
            ),
        )
        linked = client.portal.call(
            workflow.edit_capabilities,
            file_id,
            EditJdCapabilities(
                uuid4(),
                capabilities.revision_id,
                SetTaskCapability(
                    tasks.tasks[0].task_id, capabilities.capabilities[0].capability_id, True
                ),
            ),
        )
        collaborators = client.portal.call(
            workflow.edit_collaborators,
            file_id,
            EditJdCollaborators(
                uuid4(), linked.revision_id, CreateCollaborator("原協作", "協作正文")
            ),
        )
        client.portal.call(
            workflow.edit_conditions,
            file_id,
            EditJdConditions(
                uuid4(),
                collaborators.revision_id,
                CreateCondition(ConditionKind.WORK_ENVIRONMENT, "原環境"),
            ),
        )
        initial = client.portal.call(workflow.read_profile, file_id)
    if fixture_kind == "full_with_sources":
        source_id = uuid4()
        database_connection.execute(
            "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) "
            "VALUES (%s,%s,'employee','合成來源')",
            (file_id, source_id),
        )
        database_connection.execute(
            "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) "
            "SELECT %s,coalesce(max(interview_sequence),0)+1,%s FROM formal_interviews "
            "WHERE job_file_id=%s",
            (file_id, source_id, file_id),
        )
        work = client.portal.call(workflow.read_work, file_id)
        targets = tuple(
            target
            for target, content in source_target_contents(initial.profile, work).items()
            if isinstance(content, TaskSourceContents)
            or any(value is not None for value in content)
        )

        async def seed_references():
            async with client.app.state.database.sessions.begin() as session:
                await job_files.lock_job_file(session, file_id)
                revision = initial.revision_id
                for target in targets:
                    revision = await source_service.revise_sources(
                        session,
                        file_id,
                        ReviseJdSources(
                            uuid4(), revision, target, (AddJdSource(InterviewSource(source_id)),)
                        ),
                    )

        client.portal.call(seed_references)
        initial = client.portal.call(workflow.read_profile, file_id)
    statements = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split(None, 1)[0].upper())

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", observe)
    try:
        command = ReviseJdProfile(
            uuid4(), initial.revision_id, (SetProfileField(ProfileField.JOB_TITLE, "職稱"),)
        )
        changed = client.portal.call(workflow.revise_profile, file_id, command)
        measurements = {"change": {"sql": len(statements), "select": statements.count("SELECT")}}
        statements.clear()
        unchanged = client.portal.call(
            workflow.revise_profile,
            file_id,
            replace(command, command_id=uuid4(), expected_revision_id=changed.revision_id),
        )
        measurements["noop"] = {"sql": len(statements), "select": statements.count("SELECT")}
        statements.clear()
        original = client.portal.call(workflow.revise_profile, file_id, command)
        measurements["replay"] = {"sql": len(statements), "select": statements.count("SELECT")}
        assert original == changed == unchanged
        print(json.dumps({fixture_kind: measurements}))
    finally:
        event.remove(engine, "before_cursor_execute", observe)
