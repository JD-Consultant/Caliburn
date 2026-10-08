"""File-scoped discovery reads existing PG admission and public status without running work."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStatus
from caliburn.features.interviews.models import SubmitInterviewInput
from caliburn.transport.http.consultant_turns import get_consultant_status_workflow
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.consultant_status import ConsultantStatusWorkflow
from tests.integration.test_consultant_completion import complete, start_turn, transact
from tests.integration.test_jd_capabilities import create_capability, edit

pytestmark = pytest.mark.postgres


def create_file(client: TestClient) -> UUID:
    response = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "找回處理", "employee_name": "合成人員"},
    )
    assert response.status_code == 201
    return UUID(response.json()["job_file_id"])


def accept_turn(client: TestClient, file_id: UUID) -> ExecutionScope:
    result = client.portal.call(
        client.app.state.interview_input_workflow.accept,
        SubmitInterviewInput(file_id, uuid4(), "已保存但尚未正式化的原始輸入"),
    )
    return ExecutionScope(file_id, result.accepted.execution_id, ExecutionKind.CONSULTANT_TURN)


def current_path(file_id: UUID) -> str:
    return f"/api/job-files/{file_id}/consultant-turns/current"


def read_current(client: TestClient, file_id: UUID) -> dict | None:
    response = client.get(current_path(file_id))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {"turn"}
    return response.json()["turn"]


def test_existing_file_without_turn_returns_explicit_null(client: TestClient) -> None:
    assert read_current(client, create_file(client)) is None


def test_missing_file_is_not_an_idle_file(client: TestClient) -> None:
    response = client.get(current_path(uuid4()))
    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "job_file_not_found"}}


def test_admitted_turn_is_discoverable_before_writer_or_candidate_exists(
    client: TestClient,
) -> None:
    file_id = create_file(client)
    scope = accept_turn(client, file_id)
    assert read_current(client, file_id) == {
        "job_file_id": str(file_id),
        "execution_id": str(scope.execution_id),
        "status": "active",
        "pause_requested": False,
        "input_text": "已保存但尚未正式化的原始輸入",
        "allowed_controls": [],
        "commentary": [],
        "plan_preview": None,
        "candidate": None,
    }
    execution = transact(client, lambda session: executions.read_execution(session, scope))
    assert execution.writer_id is None


@pytest.mark.parametrize(
    "status,pause_requested", [("active", False), ("active", True), ("paused", True)]
)
def test_discovery_preserves_public_status_and_candidate_projection(
    client: TestClient, status: str, pause_requested: bool
) -> None:
    turn = start_turn(client)
    scope = turn.writer.scope
    if pause_requested:
        transact(client, lambda session: executions.request_pause(session, scope))
    if status == "paused":
        transact(client, lambda session: executions.pause_execution(session, turn.writer))

    discovered = read_current(client, scope.job_file_id)
    assert discovered is not None
    assert discovered["execution_id"] == str(scope.execution_id)
    assert discovered["status"] == status
    assert discovered["pause_requested"] is pause_requested
    assert discovered["candidate"]["profile"]["job_title"] == "前端工程師"
    by_execution = client.get(
        f"/api/job-files/{scope.job_file_id}/consultant-turns/{scope.execution_id}"
    )
    assert by_execution.status_code == 200
    assert discovered == by_execution.json()


def test_discovery_is_scoped_to_file_and_never_returns_memory_work(client: TestClient) -> None:
    first, second, memory_only = (create_file(client) for _ in range(3))
    first_turn, second_turn = accept_turn(client, first), accept_turn(client, second)
    for file_id in (first, memory_only):
        scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
        transact(client, lambda session, scope=scope: executions.admit_execution(session, scope))

    assert read_current(client, first)["execution_id"] == str(first_turn.execution_id)
    assert read_current(client, second)["execution_id"] == str(second_turn.execution_id)
    assert read_current(client, memory_only) is None


@pytest.mark.parametrize("kind", ["knowledge", "skill"])
def test_current_candidate_with_capabilities_matches_by_execution(
    client: TestClient, kind: str
) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/capabilities"
    edit(client, url, client.get(url).json(), create_capability(kind))
    turn = start_turn(client, file_id=file_id)
    by_execution = client.get(
        f"/api/job-files/{file_id}/consultant-turns/{turn.writer.scope.execution_id}"
    )
    assert by_execution.status_code == 200
    expected = by_execution.json()
    assert expected["candidate"]["work"]["capabilities"][0]["kind"] == kind
    assert read_current(client, file_id) == expected


@pytest.mark.parametrize(
    "outcome", [ExecutionStatus.COMPLETED, ExecutionStatus.CANCELLED, ExecutionStatus.FAILED]
)
def test_terminal_history_is_not_current_and_later_admission_is_found(
    client: TestClient, outcome: ExecutionStatus
) -> None:
    turn = start_turn(client)
    file_id = turn.writer.scope.job_file_id
    if outcome == ExecutionStatus.COMPLETED:
        complete(client, turn)
    else:
        workflow = ConsultantCompletionWorkflow(client.app.state.database.sessions)
        client.portal.call(workflow.stop, turn.writer, outcome)

    assert read_current(client, file_id) is None
    later = accept_turn(client, file_id)
    assert read_current(client, file_id)["execution_id"] == str(later.execution_id)


def test_repeated_discovery_uses_read_only_pg_without_claiming_or_resuming(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    scope = turn.writer.scope
    transact(client, lambda session: executions.request_pause(session, scope))
    transact(client, lambda session: executions.pause_execution(session, turn.writer))
    before = transact(client, lambda session: executions.read_execution(session, scope))
    settings = client.app.state.database.settings
    engine = create_async_engine(
        settings.sqlalchemy_url,
        connect_args={
            "options": f"-c search_path={settings.schema} -c default_transaction_read_only=on"
        },
    )
    workflow = ConsultantStatusWorkflow(async_sessionmaker(engine, expire_on_commit=False))
    client.app.dependency_overrides[get_consultant_status_workflow] = lambda: workflow
    try:
        first = read_current(client, scope.job_file_id)
        assert first["status"] == "paused"
        assert read_current(client, scope.job_file_id) == first
    finally:
        del client.app.dependency_overrides[get_consultant_status_workflow]
        client.portal.call(engine.dispose)

    assert transact(client, lambda session: executions.read_execution(session, scope)) == before
    assert len(client.get(f"/api/job-files/{scope.job_file_id}/interviews").json()["messages"]) == 1
    assert (
        client.get(f"/api/job-files/{scope.job_file_id}/jd/profile").json()["profile"]["job_title"]
        is None
    )
