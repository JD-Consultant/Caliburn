"""HTTP control boundaries use real PG owners; model work is not part of this router suite."""

import asyncio
from contextlib import contextmanager
from dataclasses import replace
from functools import partial
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.adapters.process_lock import PostgresProcessLock
from caliburn.agent_execution.tool_steps import PausedResponseLoop, run_response_loop
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import (
    AgentRole,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.interviews.models import SubmitInterviewInput
from caliburn.workflows.consultant_controls import (
    ConsultantControlWorkflow,
    run_consultant_with_controls,
)
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor
from caliburn.workflows.execution_controls import ConsultantExecutionControls
from tests.fixtures.response_capacity import CapacityProbe, request_fixture
from tests.integration.test_consultant_completion import complete, start_turn

pytestmark = pytest.mark.postgres


def accept(client: TestClient) -> ExecutionScope:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "HTTP控制",
                "employee_name": "合成人員",
            },
        ).json()["job_file_id"]
    )
    result = client.portal.call(
        client.app.state.interview_input_workflow.accept,
        SubmitInterviewInput(file_id, uuid4(), "原始待確認輸入"),
    )
    return ExecutionScope(file_id, result.accepted.execution_id, ExecutionKind.CONSULTANT_TURN)


def path(scope: ExecutionScope) -> str:
    return f"/api/job-files/{scope.job_file_id}/consultant-turns/{scope.execution_id}"


@contextmanager
def attached_controls(client: TestClient, *, saver=None, run=None):
    db = client.app.state.database

    async def idle(writer):
        await asyncio.Event().wait()  # Synthetic blocked model boundary, not a fake control owner.

    supervisor = ConsultantSupervisor(
        sessions=db.sessions,
        run=run or idle,
        process_lock=PostgresProcessLock(db.settings),
    )
    controls = ConsultantControlWorkflow(db.sessions, saver or InMemorySaver(), supervisor)
    previous = getattr(client.app.state, "consultant_control_workflow", None)
    client.app.state.consultant_control_workflow = controls
    try:
        client.portal.call(supervisor.start)
        yield controls
    finally:
        client.portal.call(supervisor.close)
        client.app.state.consultant_control_workflow = previous


def public_turn(response, *, status: str) -> dict:
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {
        "job_file_id",
        "execution_id",
        "status",
        "pause_requested",
        "input_text",
        "allowed_controls",
        "commentary",
        "candidate",
    }
    assert body["status"] == status
    return body


def test_http_pause_reports_pending_not_acknowledged_pause(client: TestClient) -> None:
    scope = accept(client)
    with attached_controls(client):
        assert public_turn(client.get(path(scope)), status="active")["allowed_controls"] == [
            "pause",
            "cancel",
        ]
        pending = public_turn(client.post(path(scope) + "/pause"), status="active")
        assert pending["pause_requested"] is True
        assert client.get(path(scope)).json()["pause_requested"] is True
        assert pending["allowed_controls"] == ["cancel"]
        assert pending["input_text"] == "原始待確認輸入"

        async def read():
            async with client.app.state.database.sessions() as session:
                return await executions.read_execution(session, scope)

        assert client.portal.call(read).pause_requested


def test_http_cancel_is_public_scoped_and_repeatable(client: TestClient) -> None:
    scope = accept(client)
    with attached_controls(client):
        first = public_turn(client.post(path(scope) + "/cancel"), status="cancelled")
        second = public_turn(client.post(path(scope) + "/cancel"), status="cancelled")
        assert second == first
        assert first["pause_requested"] is False
        assert first["allowed_controls"] == [] and first["candidate"] is None
        assert (
            len(client.get(f"/api/job-files/{scope.job_file_id}/interviews").json()["messages"])
            == 1
        )


def test_http_cancel_does_not_roll_back_already_completed_turn(client: TestClient) -> None:
    turn = start_turn(client)
    original = complete(client, turn)
    with attached_controls(client):
        result = public_turn(client.post(path(turn.writer.scope) + "/cancel"), status="completed")
        assert result["allowed_controls"] == []
        assert complete(client, turn) == original


def test_http_resume_consumes_only_original_native_interrupt(client: TestClient) -> None:
    scope = accept(client)
    sessions = client.app.state.database.sessions
    saver = InMemorySaver()
    provider = CapacityProbe([100], final=True)
    resumed = asyncio.Event()
    resume_ids = []
    thread_id = context_thread_id(scope, AgentRole.JOB_CONSULTANT, HistoryWindowKind.COMPLETED_WORK)

    async def native_run(writer, *, resume_interrupt_id=None, request=None):
        control = ConsultantExecutionControls(sessions, writer)
        result = await run_response_loop(
            saver,
            thread_id=thread_id,
            request=request,
            runtime=replace(provider.runtime(), ensure_active=control.ensure_active),
            max_tool_calls=2,
            max_model_steps=3,
            controls=control.loop_controls(),
            resume_interrupt_id=resume_interrupt_id,
        )
        if resume_interrupt_id is not None:
            resume_ids.append(resume_interrupt_id)
            resumed.set()
        return result

    async def prepare_pause():
        async with sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            await executions.request_pause(session, scope)
        paused = await native_run(writer, request=request_fixture())
        assert isinstance(paused, PausedResponseLoop)
        return paused.interrupt_id

    original_interrupt = client.portal.call(prepare_pause)
    wrapped = partial(
        run_consultant_with_controls, sessions=sessions, checkpointer=saver, run=native_run
    )
    with attached_controls(client, saver=saver, run=wrapped) as controls:
        assert public_turn(client.get(path(scope)), status="paused")["allowed_controls"] == [
            "resume",
            "cancel",
        ]
        response = public_turn(client.post(path(scope) + "/resume"), status="active")
        assert response["pause_requested"] is False
        assert response["allowed_controls"] == ["pause", "cancel"]

        async def wait_for_native_resume():
            await asyncio.wait_for(resumed.wait(), timeout=2)

        client.portal.call(wait_for_native_resume)
        assert resume_ids == [original_interrupt]
        assert not controls.supervisor.failures
        assert len(provider.model_requests) == 1


def test_http_controls_reject_foreign_file_and_memory_scope(client: TestClient) -> None:
    scope = accept(client)

    async def memory_scope():
        memory = ExecutionScope(scope.job_file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
        async with client.app.state.database.sessions.begin() as session:
            await executions.admit_execution(session, memory)
        return memory

    memory = client.portal.call(memory_scope)
    foreign = ExecutionScope(uuid4(), scope.execution_id, ExecutionKind.CONSULTANT_TURN)
    with attached_controls(client):
        for target in (foreign, memory):
            for action in ("pause", "cancel", "resume"):
                response = client.post(path(target) + f"/{action}")
                assert response.status_code == 404
                assert response.json() == {"detail": {"code": "consultant_turn_not_found"}}
        assert client.get(path(scope)).json()["status"] == "active"


def test_http_controls_reject_body_query_and_malformed_scope(client: TestClient) -> None:
    scope = accept(client)
    with attached_controls(client):
        spec = client.get("/openapi.json").json()
        for action in ("pause", "cancel", "resume"):
            operation = spec["paths"][
                "/api/job-files/{job_file_id}/consultant-turns/{execution_id}/" + action
            ]["post"]
            assert "requestBody" not in operation
            assert {(param["name"], param["in"]) for param in operation["parameters"]} == {
                ("job_file_id", "path"),
                ("execution_id", "path"),
            }
        for kwargs in (
            {"json": {"writer_id": str(uuid4())}},
            {"params": {"checkpoint_id": "private"}},
        ):
            rejected = client.post(path(scope) + "/cancel", **kwargs)
            assert rejected.status_code == 422
            assert rejected.json() == {"detail": {"code": "unexpected_control_arguments"}}
        assert (
            client.post(
                f"/api/job-files/{scope.job_file_id}/consultant-turns/not-a-uuid/cancel"
            ).status_code
            == 422
        )
        assert client.get(path(scope)).json()["status"] == "active"


def test_http_resume_pending_pause_is_conflict_not_success(client: TestClient) -> None:
    scope = accept(client)
    with attached_controls(client):
        assert client.post(path(scope) + "/pause").status_code == 200
        refused = client.post(path(scope) + "/resume")
        assert refused.status_code == 409
        assert refused.json() == {"detail": {"code": "consultant_control_conflict"}}
        assert public_turn(client.get(path(scope)), status="active")["allowed_controls"] == [
            "cancel"
        ]


def test_http_controls_unconfigured_are_unavailable_not_advertised(client: TestClient) -> None:
    scope = accept(client)
    assert public_turn(client.get(path(scope)), status="active")["allowed_controls"] == []
    for action in ("pause", "cancel", "resume"):
        response = client.post(path(scope) + f"/{action}")
        assert response.status_code == 503
        assert response.json() == {"detail": {"code": "consultant_controls_unavailable"}}


def test_http_cancel_only_when_supervisor_stopped_does_not_invent_pause(client: TestClient) -> None:
    scope = accept(client)
    with attached_controls(client) as controls:
        client.portal.call(controls.supervisor.close)
        stopped = public_turn(client.get(path(scope)), status="active")
        assert stopped["allowed_controls"] == ["cancel"]
        assert stopped["pause_requested"] is False
        cancelled = public_turn(client.post(path(scope) + "/cancel"), status="cancelled")
        assert cancelled["pause_requested"] is False
