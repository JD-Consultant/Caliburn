"""Completed-turn undo is JD-only, conditional and replayable on real PostgreSQL."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.interviews import queries as interviews
from caliburn.features.job_description import persistence, revision_editing, source_persistence
from caliburn.features.job_description.areas import CreateArea, DeleteArea, EditJdAreas
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
    JdProfileRevision,
    ProfileField,
    ReviseJdProfile,
    SetProfileField,
    StaleJdRevisionError,
)
from caliburn.features.job_description.sources import (
    AddJdSource,
    InterviewSource,
    JdSourceTarget,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.features.job_description.tasks import CreateTask, DeleteTask, EditJdTasks
from caliburn.features.job_files import service as job_files
from caliburn.features.work_memory import candidate_queries as memory
from caliburn.transport.http.jd_undo import router
from caliburn.transport.model_tools.jd_changes import project_jd_manual_changes
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_changes import AllManualChanges, JdChangesWorkflow
from caliburn.workflows.jd_editing import JdEditingWorkflow
from caliburn.workflows.jd_undo import JdUndoWorkflow
from caliburn.workflows.memory_reads import PublishedMemoryRead
from tests.integration.test_consultant_completion import (
    Turn,
    complete,
    read_head,
    start_turn,
    transact,
)
from tests.integration.test_consultant_context_binding import publish_memory

pytestmark = pytest.mark.postgres


@pytest.fixture
def undo_client(client: TestClient) -> TestClient:
    client.app.state.jd_undo_workflow = JdUndoWorkflow(client.app.state.database.sessions)
    client.app.include_router(router)
    return client


def url(turn: Turn) -> str:
    scope = turn.writer.scope
    return f"/api/job-files/{scope.job_file_id}/consultant-turns/{scope.execution_id}/undo-jd"


def profile_url(turn: Turn) -> str:
    return f"/api/job-files/{turn.writer.scope.job_file_id}/jd/profile"


def test_undo_restores_base_as_new_revision_without_rewinding_interview_or_context(
    undo_client: TestClient,
) -> None:
    turn = start_turn(undo_client)
    complete(undo_client, turn)
    assert turn.candidate is not None
    scope = turn.writer.scope
    before_history = undo_client.get(f"/api/job-files/{scope.job_file_id}/interviews").json()
    response = undo_client.post(url(turn))
    assert response.status_code == 200, response.text
    assert response.json()["profile"]["job_title"] is None
    revision = UUID(response.json()["revision_id"])
    assert revision not in {turn.candidate.base_revision_id, turn.candidate.revision_id}
    assert undo_client.get(profile_url(turn)).json() == response.json()
    assert (
        undo_client.get(f"/api/job-files/{scope.job_file_id}/interviews").json() == before_history
    )
    assert read_head(undo_client, turn) == turn.completed
    assert transact(undo_client, lambda s: executions.read_execution(s, scope)).status == (
        ExecutionStatus.COMPLETED
    )
    # Saved final result and old fixed JD must remain readable, without republishing.
    complete(undo_client, turn)
    assert undo_client.get(profile_url(turn)).json() == response.json()
    assert (
        transact(
            undo_client,
            lambda s: persistence.read_revision(s, scope.job_file_id, turn.candidate.revision_id),
        ).profile.job_title
        == "前端工程師"
    )


@pytest.mark.parametrize("field", ["job_title", "purpose"])
def test_later_manual_edit_conflicts_without_overwriting_it(
    undo_client: TestClient, field: str
) -> None:
    turn = start_turn(undo_client)
    complete(undo_client, turn)
    old = undo_client.get(profile_url(turn)).json()
    edited = undo_client.post(
        profile_url(turn),
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": old["revision_id"],
            "changes": [{"action": "set_field", "field": field, "value": "人工定稿"}],
        },
    )
    assert edited.status_code == 200
    response = undo_client.post(url(turn))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "jd_undo_conflict"
    assert undo_client.get(profile_url(turn)).json() == edited.json()


def test_replay_after_later_edit_returns_original_without_moving_head(
    undo_client: TestClient,
) -> None:
    turn = start_turn(undo_client)
    complete(undo_client, turn)
    result = undo_client.post(url(turn))
    assert result.status_code == 200
    edited = undo_client.post(
        profile_url(turn),
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": result.json()["revision_id"],
            "changes": [{"action": "set_field", "field": "job_title", "value": "撤回後續改"}],
        },
    )
    assert edited.status_code == 200
    assert undo_client.post(url(turn)).json() == result.json()
    assert undo_client.get(profile_url(turn)).json() == edited.json()


@pytest.mark.parametrize("paused", [False, True])
def test_active_or_paused_turn_blocks_a_new_undo(undo_client: TestClient, paused: bool) -> None:
    turn = start_turn(undo_client)
    complete(undo_client, turn)
    later = start_turn(undo_client, file_id=turn.writer.scope.job_file_id)
    if paused:
        transact(undo_client, lambda s: executions.request_pause(s, later.writer.scope))
        # This owner-level fixture supplies the already-durable safe-point qualification.
        transact(undo_client, lambda s: executions.pause_execution(s, later.writer))
    response = undo_client.post(url(turn))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "consultant_turn_active"


def test_uncompleted_or_foreign_turn_is_not_an_undo_target(undo_client: TestClient) -> None:
    turn = start_turn(undo_client)
    assert undo_client.post(url(turn)).status_code == 409
    other = start_turn(undo_client)
    complete(undo_client, other)
    wrong = url(other).replace(
        str(other.writer.scope.job_file_id), str(turn.writer.scope.job_file_id)
    )
    assert undo_client.post(wrong).status_code == 404
    assert undo_client.post(url(other), json={"revision_id": str(uuid4())}).status_code == 422
    assert undo_client.post(url(other) + "?target_revision_id=" + str(uuid4())).status_code == 422


def test_concurrent_duplicate_undo_has_one_result(undo_client: TestClient) -> None:
    turn = start_turn(undo_client)
    complete(undo_client, turn)
    barrier = Barrier(2)

    def send() -> object:
        barrier.wait(timeout=10)
        response = undo_client.post(url(turn))
        assert response.status_code == 200, response.text
        return response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(send), pool.submit(send)
        assert first.result(timeout=20) == second.result(timeout=20)


def test_undo_restores_relations_and_sources_but_keeps_new_memory(undo_client: TestClient) -> None:
    client = undo_client
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": "撤回關聯", "employee_name": "合成"},
        ).json()["job_file_id"]
    )
    editing = JdEditingWorkflow(client.app.state.database.sessions)
    candidates = JdCandidateWorkflow(client.app.state.database.sessions)

    def head():
        return client.portal.call(editing.read_profile, file_id).revision_id

    area = client.portal.call(
        editing.edit_areas, file_id, EditJdAreas(uuid4(), head(), CreateArea("交付", "既有職責"))
    ).areas[0]
    task = client.portal.call(
        editing.edit_tasks,
        file_id,
        EditJdTasks(
            uuid4(),
            head(),
            CreateTask(area.area_id, "驗收", "既有任務", ("交付合格",), ("雙人核對",)),
        ),
    ).tasks[0]
    capability = client.portal.call(
        editing.edit_capabilities,
        file_id,
        EditJdCapabilities(
            uuid4(), head(), CreateCapability(CapabilityKind.SKILL, "驗收能力", "既有說明")
        ),
    ).capabilities[0]
    client.portal.call(
        editing.edit_capabilities,
        file_id,
        EditJdCapabilities(
            uuid4(), head(), SetTaskCapability(task.task_id, capability.capability_id, True)
        ),
    )
    client.portal.call(
        editing.edit_collaborators,
        file_id,
        EditJdCollaborators(uuid4(), head(), CreateCollaborator("同事", "共同核對")),
    )
    client.portal.call(
        editing.edit_conditions,
        file_id,
        EditJdConditions(
            uuid4(), head(), CreateCondition(ConditionKind.WORK_ENVIRONMENT, "辦公室")
        ),
    )
    first = start_turn(client, file_id=file_id)
    assert first.candidate is not None
    source = transact(
        client,
        lambda s: interviews.read_execution_input(
            s, job_file_id=file_id, execution_id=first.writer.scope.execution_id
        ),
    )
    position = client.portal.call(
        candidates.edit,
        first.writer,
        first.candidate.scope,
        ReviseJdSources(
            uuid4(),
            first.candidate.revision_id,
            JdSourceTarget(SourceTargetKind.TASK, task.task_id),
            (AddJdSource(InterviewSource(source.source_id)),),
        ),
    )
    complete(client, replace(first, candidate=position))
    original_work = client.portal.call(editing.read_work, file_id)
    original_sources = transact(
        client,
        lambda s: source_persistence.read_source_references(s, file_id, original_work.revision_id),
    )
    assert original_sources and original_work.task_links

    second = start_turn(client, file_id=file_id)
    assert second.candidate is not None
    position = client.portal.call(
        candidates.edit,
        second.writer,
        second.candidate.scope,
        EditJdTasks(uuid4(), second.candidate.revision_id, DeleteTask(task.task_id)),
    )
    position = client.portal.call(
        candidates.edit,
        second.writer,
        position.scope,
        EditJdAreas(uuid4(), position.revision_id, DeleteArea(area.area_id)),
    )
    second = replace(second, candidate=position)
    exchange = complete(client, second)
    published = client.portal.call(
        publish_memory,
        client.app.state.database,
        file_id,
        exchange.employee_input.source_id,
        "撤回也必須保留的理解來源",
    )
    response = client.post(url(second))
    assert response.status_code == 200, response.text
    result_id = UUID(response.json()["revision_id"])
    restored = client.portal.call(editing.read_work, file_id)
    assert replace(restored, revision_id=original_work.revision_id) == original_work
    assert restored.tasks[0].title == "驗收"
    assert [detail.text for detail in restored.tasks[0].details] == ["交付合格", "雙人核對"]
    assert (
        transact(client, lambda s: source_persistence.read_source_references(s, file_id, result_id))
        == original_sources
    )
    assert transact(client, lambda s: memory.read_latest_snapshot(s, file_id)) == published
    assert complete(client, second) == exchange


def test_failure_after_recording_rolls_back_all_jd_effects(
    undo_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    turn = start_turn(undo_client)
    complete(undo_client, turn)
    before = undo_client.get(profile_url(turn)).json()
    record = revision_editing.record_edit

    async def fail_after_record(*args, **kwargs):
        await record(*args, **kwargs)
        raise OperationalError("synthetic", {}, RuntimeError("not public"))

    with monkeypatch.context() as patch:
        patch.setattr(revision_editing, "record_edit", fail_after_record)
        response = undo_client.post(url(turn))
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "jd_undo_unconfirmed"
        assert "not public" not in response.text
    assert undo_client.get(profile_url(turn)).json() == before
    assert undo_client.post(url(turn)).status_code == 200


def test_next_turn_can_read_undo_as_manual_effect(undo_client: TestClient) -> None:
    first = start_turn(undo_client)
    exchange = complete(undo_client, first)
    result = undo_client.post(url(first))
    assert result.status_code == 200
    current = start_turn(undo_client, file_id=first.writer.scope.job_file_id)
    assert current.candidate is not None
    reader = JdChangesWorkflow(undo_client.app.state.database.sessions)

    async def read():
        return await reader.read_manual(
            PublishedMemoryRead(
                current.writer.scope, None, exchange.consultant_reply.interview_sequence
            ),
            manual_jd_start_revision_id=current.candidate.base_revision_id,
            scope=AllManualChanges(),
        )

    changes = undo_client.portal.call(read)
    assert len(changes.interval.operations) == 1
    assert changes.interval.operations[0].kind == "undo_completed_turn"
    projection = project_jd_manual_changes(changes)
    assert "人工操作：1" in projection
    assert "前端工程師" in projection and "刪除" in projection


@pytest.mark.parametrize("first_action", ["undo", "edit"])
def test_racing_manual_edit_and_undo_only_apply_the_first_locked_base(
    undo_client: TestClient, monkeypatch: pytest.MonkeyPatch, first_action: str
) -> None:
    turn = start_turn(undo_client)
    complete(undo_client, turn)
    assert turn.candidate is not None
    file_id = turn.writer.scope.job_file_id
    command = ReviseJdProfile(
        uuid4(),
        turn.candidate.revision_id,
        (SetProfileField(ProfileField.JOB_TITLE, "競爭人工定稿"),),
    )
    lock = job_files.lock_job_file

    async def race():
        acquired, second_entered, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        attempts = 0

        async def hold_first(session, selected_file):
            nonlocal attempts
            attempts += 1
            first = attempts == 1
            if not first:
                second_entered.set()
            await lock(session, selected_file)
            if first:
                acquired.set()
                await release.wait()

        async with asyncio.timeout(10):
            with monkeypatch.context() as patch:
                patch.setattr(job_files, "lock_job_file", hold_first)
                undo = undo_client.app.state.jd_undo_workflow
                editing = JdEditingWorkflow(undo_client.app.state.database.sessions)
                actions = {
                    "undo": lambda: undo.undo(file_id, turn.writer.scope.execution_id),
                    "edit": lambda: editing.revise_profile(file_id, command),
                }
                first = asyncio.create_task(actions[first_action]())
                await acquired.wait()
                second = asyncio.create_task(
                    actions["edit" if first_action == "undo" else "undo"]()
                )
                await second_entered.wait()
                release.set()
                return await asyncio.gather(first, second, return_exceptions=True)

    first, second = undo_client.portal.call(race)
    assert isinstance(first, JdProfileRevision)
    assert isinstance(second, StaleJdRevisionError)
    current = undo_client.get(profile_url(turn)).json()
    assert current["revision_id"] == str(first.revision_id)
    assert current["profile"]["job_title"] == (None if first_action == "undo" else "競爭人工定稿")
