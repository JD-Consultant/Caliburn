"""Manual diffs use completed A history and fixed formal revisions, not candidate text."""

import json
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.executions import history
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.job_description.models import ProfileField, ReviseJdProfile, SetProfileField
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_changes import JdChangesWorkflow
from caliburn.workflows.memory_reads import PublishedMemoryRead
from tests.integration.test_consultant_completion import complete, start_turn, transact

pytestmark = pytest.mark.postgres


def manual_profile(client, file_id, field, value):
    url = f"/api/job-files/{file_id}/jd/profile"
    before = client.get(url).json()
    response = client.post(
        url,
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": before["revision_id"],
            "changes": [{"action": "set_field", "field": field, "value": value}],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def tools_for(client, turn):
    from caliburn.transport.model_tools.jd_changes import JdChangesTools

    return JdChangesTools(
        JdChangesWorkflow(client.app.state.database.sessions),
        PublishedMemoryRead(turn.writer.scope, None, 100),
        manual_jd_start_revision_id=turn.candidate.base_revision_id,
    )


def read_manual(client, tools, scope=None):
    return client.portal.call(
        tools.invoke,
        "read_jd_changes",
        json.dumps(
            {
                "query": {"kind": "manual", "scope": scope or {"kind": "all"}},
            }
        ),
    )


def test_manual_keeps_success_base_through_cancelled_preparation_and_candidate_edits(
    client: TestClient,
):
    first = start_turn(client)
    complete(client, first)
    file_id = first.writer.scope.job_file_id
    manual_profile(client, file_id, "job_title", "人工職稱")
    cancelled = start_turn(client, file_id=file_id)
    client.portal.call(
        ConsultantCompletionWorkflow(client.app.state.database.sessions).stop,
        cancelled.writer,
        ExecutionStatus.CANCELLED,
    )
    manual_profile(client, file_id, "purpose", "人工使命")
    current = start_turn(client, file_id=file_id)
    tools = tools_for(client, current)
    output = read_manual(client, tools)
    assert "人工操作：2" in output and "人工職稱" in output and "人工使命" in output
    assert "上一成功 A" in output and "本 Turn 起點" in output
    assert "未確認" in output
    candidates = JdCandidateWorkflow(client.app.state.database.sessions)
    client.portal.call(
        candidates.edit,
        current.writer,
        current.candidate.scope,
        ReviseJdProfile(
            uuid4(),
            current.candidate.revision_id,
            (SetProfileField(ProfileField.PURPOSE, "候選改動不得混入"),),
        ),
    )
    assert read_manual(client, tools) == output
    assert "候選改動不得混入" not in output
    assert tools.names == ("read_jd_changes",)
    assert tools.definitions()[0]["name"] == "read_jd_changes"


def test_change_back_and_noop_are_activity_not_no_operations_and_baseline_advances_only_on_success(
    client: TestClient,
):
    first = start_turn(client)
    complete(client, first)
    file_id = first.writer.scope.job_file_id
    manual_profile(client, file_id, "job_title", "臨時職稱")
    manual_profile(client, file_id, "job_title", "前端工程師")
    manual_profile(client, file_id, "job_title", "前端工程師")  # Original operation, no revision.
    current = start_turn(client, file_id=file_id)
    tools = tools_for(client, current)
    output = read_manual(client, tools)
    assert "人工操作：3" in output and "淨差異：無" in output
    assert "臨時職稱" in output and "結果未改變" in output
    assert "受影響範圍：profile.job_title" in output
    untouched = read_manual(client, tools, {"kind": "profile_field", "field": "purpose"})
    assert "沒有人工操作" in untouched and "臨時職稱" not in untouched
    complete(client, current)
    later = start_turn(client, file_id=file_id)
    assert "沒有人工操作" in read_manual(client, tools_for(client, later))


def test_first_turn_compares_initial_empty_jd_and_mismatched_start_is_rejected(client: TestClient):
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "初次", "employee_name": "合成"},
    )
    file_id = UUID(created.json()["job_file_id"])
    manual_profile(client, file_id, "purpose", "首輪之前的使命")
    current = start_turn(client, file_id=file_id)
    tools = tools_for(client, current)
    output = read_manual(client, tools)
    assert "初始空 JD" in output and "首輪之前的使命" in output and "新增" in output
    tools.manual_jd_start_revision_id = uuid4()
    assert read_manual(client, tools).startswith("rejected: scope_not_allowed")


def test_history_query_follows_exact_prepared_reference_without_parsing_native_id(
    client: TestClient,
):
    first = start_turn(client)
    complete(client, first)
    cancelled = start_turn(client, file_id=first.writer.scope.job_file_id)
    client.portal.call(
        ConsultantCompletionWorkflow(client.app.state.database.sessions).stop,
        cancelled.writer,
        ExecutionStatus.CANCELLED,
    )
    current = start_turn(client, file_id=first.writer.scope.job_file_id)
    found = transact(
        client,
        lambda session: history.read_previous_completed_execution(
            session, current.writer.scope, AgentRole.JOB_CONSULTANT
        ),
    )
    assert found == first.writer.scope


def test_manual_item_area_and_sources_show_moves_unlinks_deletions_without_alignment(
    client: TestClient,
):
    from caliburn.features.interviews import queries as interviews
    from caliburn.features.job_description import source_persistence
    from caliburn.features.job_description.areas import CreateArea, DeleteArea, EditJdAreas
    from caliburn.features.job_description.capabilities import (
        CapabilityKind,
        CreateCapability,
        EditJdCapabilities,
        SetTaskCapability,
    )
    from caliburn.features.job_description.conditions import (
        ConditionKind,
        CreateCondition,
        EditJdConditions,
    )
    from caliburn.features.job_description.sources import (
        AddJdSource,
        InterviewSource,
        JdSourceTarget,
        ReviseJdSources,
        SourceTargetKind,
    )
    from caliburn.features.job_description.tasks import (
        CreateTask,
        EditJdTasks,
        MoveTask,
        SetTaskField,
        TaskField,
    )
    from caliburn.workflows.jd_editing import JdEditingWorkflow

    file_id = UUID(
        client.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": "混合改動", "employee_name": "合成"},
        ).json()["job_file_id"]
    )
    editing = JdEditingWorkflow(client.app.state.database.sessions)

    def head():
        return client.portal.call(editing.read_profile, file_id).revision_id

    area_a = client.portal.call(
        editing.edit_areas, file_id, EditJdAreas(uuid4(), head(), CreateArea("舊分組", None))
    ).areas[0]
    area_b = client.portal.call(
        editing.edit_areas, file_id, EditJdAreas(uuid4(), head(), CreateArea("新分組", None))
    ).areas[1]
    task = client.portal.call(
        editing.edit_tasks,
        file_id,
        EditJdTasks(uuid4(), head(), CreateTask(area_a.area_id, "維護網站", None, (), ())),
    ).tasks[0]
    capability = client.portal.call(
        editing.edit_capabilities,
        file_id,
        EditJdCapabilities(
            uuid4(), head(), CreateCapability(CapabilityKind.KNOWLEDGE, "介面知識", None)
        ),
    ).capabilities[0]
    client.portal.call(
        editing.edit_capabilities,
        file_id,
        EditJdCapabilities(
            uuid4(), head(), SetTaskCapability(task.task_id, capability.capability_id, True)
        ),
    )
    first = start_turn(client, file_id=file_id)
    original_input = transact(
        client,
        lambda session: interviews.read_execution_input(
            session, job_file_id=file_id, execution_id=first.writer.scope.execution_id
        ),
    )
    candidate = client.portal.call(
        JdCandidateWorkflow(client.app.state.database.sessions).edit,
        first.writer,
        first.candidate.scope,
        ReviseJdSources(
            uuid4(),
            first.candidate.revision_id,
            JdSourceTarget(SourceTargetKind.TASK, task.task_id),
            (AddJdSource(InterviewSource(original_input.source_id)),),
        ),
    )
    complete(client, replace(first, candidate=candidate))
    client.portal.call(
        editing.edit_tasks,
        file_id,
        EditJdTasks(
            uuid4(),
            head(),
            MoveTask(
                task.task_id,
                area_b.area_id,
                None,
                (SetTaskField(TaskField.DESCRIPTION, "新增人工描述"),),
            ),
        ),
    )
    client.portal.call(
        editing.edit_capabilities,
        file_id,
        EditJdCapabilities(
            uuid4(), head(), SetTaskCapability(task.task_id, capability.capability_id, False)
        ),
    )
    client.portal.call(
        editing.edit_areas, file_id, EditJdAreas(uuid4(), head(), DeleteArea(area_a.area_id))
    )
    client.portal.call(
        editing.edit_conditions,
        file_id,
        EditJdConditions(
            uuid4(), head(), CreateCondition(ConditionKind.WORK_ENVIRONMENT, "機房工作")
        ),
    )
    current = start_turn(client, file_id=file_id)
    tools = tools_for(client, current)
    references = transact(
        client,
        lambda session: source_persistence.read_source_references(
            session, file_id, current.candidate.base_revision_id
        ),
    )
    assert references[0].needs_review is True
    output = read_manual(client, tools)
    assert "人工操作：4" in output and "刪除（歷史定位，不可編輯）" in output
    canonical = (
        f"area_{area_a.area_id.hex}",
        f"area_{area_b.area_id.hex}",
        f"task_{task.task_id.hex}",
    )
    aliases = client.portal.call(tools.references.assign, canonical)
    area_a_ref, area_b_ref, task_ref = (aliases[ref] for ref in canonical)
    assert area_b_ref in output and "新增人工描述" in output
    assert "來源改為待核對" in output and "機房工作" in output
    assert any(
        "來源改為待核對" in line and task_ref in line and "citation_" in line
        for line in output.splitlines()
    )
    task_output = read_manual(client, tools, {"kind": "item", "read_ref": task_ref})
    assert "人工操作：2" in task_output and "新增人工描述" in task_output
    assert "介面知識" in task_output and "機房工作" not in task_output
    area_output = read_manual(client, tools, {"kind": "area", "view": "responsibility_areas"})
    assert area_a_ref in area_output and "機房工作" not in area_output
    deleted = read_manual(client, tools, {"kind": "item", "read_ref": area_a_ref})
    assert deleted.startswith("rejected: target_not_found")
    assert (
        transact(
            client,
            lambda session: source_persistence.read_source_references(
                session, file_id, current.candidate.base_revision_id
            ),
        )
        == references
    )
    tools.max_result_characters = 1
    assert read_manual(client, tools).startswith("rejected: read_limit_exceeded")


def test_missing_history_endpoint_is_not_initial_and_reused_preparation_is_not_completion(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from caliburn.features.executions import history_persistence
    from caliburn.features.executions import service as executions
    from caliburn.features.executions.history_models import (
        ContextPosition,
        HistoryWindowKind,
        context_thread_id,
    )
    from caliburn.features.executions.models import ExecutionKind, ExecutionScope
    from tests.integration.test_consultant_completion import Turn

    first = start_turn(client)
    complete(client, first)
    file_id = first.writer.scope.job_file_id
    cancelled = start_turn(client, file_id=file_id)
    client.portal.call(
        ConsultantCompletionWorkflow(client.app.state.database.sessions).stop,
        cancelled.writer,
        ExecutionStatus.CANCELLED,
    )
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "重用先前準備"},
    ).json()
    scope = ExecutionScope(file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN)
    writer = transact(
        client, lambda session: executions.claim_writer(session, scope, writer_id=uuid4())
    )
    bound = transact(
        client,
        lambda session: history.bind_context_history(session, writer, AgentRole.JOB_CONSULTANT),
    )
    assert bound.base == cancelled.prepared
    transact(
        client,
        lambda session: history.adopt_prepared_context(
            session, writer, AgentRole.JOB_CONSULTANT, bound.base
        ),
    )
    candidate = client.portal.call(
        JdCandidateWorkflow(client.app.state.database.sessions).start, writer
    )
    completed = ContextPosition(
        context_thread_id(scope, AgentRole.JOB_CONSULTANT, HistoryWindowKind.COMPLETED_WORK),
        "completion",
        HistoryWindowKind.COMPLETED_WORK,
    )
    tools = tools_for(client, Turn(writer, bound.base, completed, candidate))
    assert "沒有人工操作" in read_manual(client, tools)

    async def unavailable(*args, **kwargs):
        return None

    monkeypatch.setattr(history_persistence, "read_position_origin", unavailable)
    result = read_manual(client, tools)
    assert result.startswith("rejected: source_not_available")
    assert "沒有人工操作" not in result
