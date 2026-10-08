"""File-level adopted text and scoped candidate previews use real PostgreSQL owners."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.interview_plans import service as interview_plans
from caliburn.features.interview_plans.models import PlanEdit
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.interview_plans import InterviewPlanWorkflow
from tests.integration.test_consultant_completion import start_turn, transact

pytestmark = pytest.mark.postgres


def create_file(client: TestClient) -> UUID:
    response = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "規劃讀取", "employee_name": "合成人"},
    )
    assert response.status_code == 201
    return UUID(response.json()["job_file_id"])


def test_existing_file_reads_explicit_uncreated_plan(client: TestClient) -> None:
    file_id = create_file(client)
    response = client.get(f"/api/job-files/{file_id}/interview-plan")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"job_file_id": str(file_id), "plan": None}


def test_missing_file_cannot_masquerade_as_an_uncreated_plan(client: TestClient) -> None:
    response = client.get(f"/api/job-files/{uuid4()}/interview-plan")
    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "job_file_not_found"}}


@pytest.mark.parametrize("body", [None, "", "## 未釐清子任務\n- 盤點差異確認。\n"])
def test_saved_preview_is_same_nullable_body_and_is_adopted_only_after_completion(
    client: TestClient, body: str | None
) -> None:
    turn = start_turn(client)
    scope = turn.writer.scope
    snapshot = transact(
        client,
        lambda session: interview_plans.start_candidate(
            session, scope.job_file_id, scope.execution_id, body
        ),
    )
    plan_path = f"/api/job-files/{scope.job_file_id}/interview-plan"
    turn_path = f"/api/job-files/{scope.job_file_id}/consultant-turns/{scope.execution_id}"
    current_path = f"/api/job-files/{scope.job_file_id}/consultant-turns/current"
    assert client.get(plan_path).json() == {"job_file_id": str(scope.job_file_id), "plan": None}
    assert client.get(turn_path).json()["plan_preview"] == {"plan": body}
    assert client.get(current_path).json()["turn"]["plan_preview"] == {"plan": body}

    transact(client, lambda session: executions.request_pause(session, scope))
    transact(client, lambda session: executions.pause_execution(session, turn.writer))
    paused = client.get(turn_path).json()
    assert paused["status"] == "paused"
    assert paused["plan_preview"] == {"plan": body}
    transact(client, lambda session: executions.resume_execution(session, turn.writer))
    assert turn.candidate is not None
    client.portal.call(
        ConsultantCompletionWorkflow(client.app.state.database.sessions).complete,
        turn.writer,
        turn.candidate,
        "合成正式答覆",
        turn.completed,
        snapshot.position,
    )
    adopted = client.get(plan_path)
    assert adopted.status_code == 200
    assert adopted.json() == {"job_file_id": str(scope.job_file_id), "plan": body}
    assert client.get(turn_path).json()["plan_preview"] is None
    assert client.get(current_path).json() == {"turn": None}

    other = create_file(client)
    assert client.get(f"/api/job-files/{other}/interview-plan").json()["plan"] is None
    assert (
        client.get(f"/api/job-files/{other}/consultant-turns/{scope.execution_id}").status_code
        == 404
    )


@pytest.mark.parametrize("outcome", [ExecutionStatus.CANCELLED, ExecutionStatus.FAILED])
def test_terminal_candidate_does_not_replace_the_previous_adopted_plan(
    client: TestClient, outcome: ExecutionStatus
) -> None:
    original = start_turn(client)
    file_id = original.writer.scope.job_file_id
    original_plan = transact(
        client,
        lambda session: interview_plans.start_candidate(
            session, file_id, original.writer.scope.execution_id, "上一採用版"
        ),
    )
    assert original.candidate is not None
    completion = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    client.portal.call(
        completion.complete,
        original.writer,
        original.candidate,
        "合成正式答覆",
        original.completed,
        original_plan.position,
    )
    abandoned = start_turn(client, file_id=file_id)
    base = transact(
        client,
        lambda session: interview_plans.start_candidate(
            session, file_id, abandoned.writer.scope.execution_id, "上一採用版"
        ),
    )
    client.portal.call(
        InterviewPlanWorkflow(client.app.state.database.sessions).apply,
        abandoned.writer,
        PlanEdit(
            uuid4(),
            base.position,
            "@@\n-上一採用版\n+未完成候選",
            "未完成候選",
            '{"status":"updated","diff":"觀察"}',
        ),
    )
    client.portal.call(completion.stop, abandoned.writer, outcome)
    terminal = client.get(
        f"/api/job-files/{file_id}/consultant-turns/{abandoned.writer.scope.execution_id}"
    )
    assert terminal.status_code == 200
    assert terminal.json()["plan_preview"] is None
    assert client.get(f"/api/job-files/{file_id}/interview-plan").json() == {
        "job_file_id": str(file_id),
        "plan": "上一採用版",
    }
