"""Completed-Turn comparisons use retained endpoints, never today's formal JD."""

from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.interviews import queries
from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.sources import (
    AddJdSource,
    InterviewSource,
    JdSourceTarget,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from tests.integration.test_consultant_completion import complete, start_turn, transact

pytestmark = pytest.mark.postgres


def changes_url(turn):
    scope = turn.writer.scope
    return f"/api/job-files/{scope.job_file_id}/consultant-turns/{scope.execution_id}/jd-changes"


def test_changes_keep_original_endpoints_after_undo_and_later_manual_edit(client: TestClient):
    turn = start_turn(client)
    complete(client, turn)
    url = changes_url(turn)
    original = client.get(url)
    assert original.status_code == 200, original.text
    assert original.headers["Cache-Control"] == "no-store"
    assert original.json()["execution_id"] == str(turn.writer.scope.execution_id)
    assert "+前端工程師" in original.json()["markdown"]
    # Reversing the effect does not rewrite what this completed Turn originally did.
    undo = client.post(url.removesuffix("jd-changes") + "undo-jd")
    assert undo.status_code == 200
    edit = client.post(
        f"/api/job-files/{turn.writer.scope.job_file_id}/jd/profile",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": undo.json()["revision_id"],
            "changes": [{"action": "set_field", "field": "job_title", "value": "後來人工修改"}],
        },
    )
    assert edit.status_code == 200
    assert client.get(url).json() == original.json()


@pytest.mark.parametrize("status", [None, ExecutionStatus.CANCELLED, ExecutionStatus.FAILED])
def test_uncompleted_turn_does_not_expose_candidate_as_formal_change(client: TestClient, status):
    turn = start_turn(client)
    if status is not None:
        completion = ConsultantCompletionWorkflow(client.app.state.database.sessions)
        client.portal.call(completion.stop, turn.writer, status)
    response = client.get(changes_url(turn))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "jd_changes_unavailable"


def test_foreign_file_and_client_selected_revision_are_rejected(client: TestClient):
    turn = start_turn(client)
    complete(client, turn)
    other = start_turn(client)
    wrong = changes_url(turn).replace(
        str(turn.writer.scope.job_file_id), str(other.writer.scope.job_file_id)
    )
    assert client.get(wrong).status_code == 404
    assert client.get(changes_url(turn) + f"?revision_id={uuid4()}").status_code == 422


def test_source_only_change_is_not_reported_as_no_change(client: TestClient):
    initial = start_turn(client)
    complete(client, initial)
    turn = start_turn(client, file_id=initial.writer.scope.job_file_id)
    assert turn.candidate is not None
    pending = transact(
        client,
        lambda session: queries.read_execution_input(
            session,
            job_file_id=turn.writer.scope.job_file_id,
            execution_id=turn.writer.scope.execution_id,
        ),
    )
    candidates = JdCandidateWorkflow(client.app.state.database.sessions)
    revised = client.portal.call(
        candidates.edit,
        turn.writer,
        turn.candidate.scope,
        ReviseJdSources(
            uuid4(),
            turn.candidate.revision_id,
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.JOB_TITLE),
            (AddJdSource(InterviewSource(pending.source_id)),),
        ),
    )
    complete(client, replace(turn, candidate=revised))
    response = client.get(changes_url(turn))
    assert response.status_code == 200, response.text
    markdown = response.json()["markdown"]
    assert "正文淨差異：無" in markdown
    assert "新增 1 筆" in markdown


def test_completed_turn_without_net_changes_is_explicit(client: TestClient):
    first = start_turn(client)
    complete(client, first)
    second = start_turn(client, file_id=first.writer.scope.job_file_id)
    complete(client, second)
    response = client.get(changes_url(second))
    assert response.status_code == 200
    assert "正文淨差異：無" in response.json()["markdown"]
    assert "來源依據淨差異：無" in response.json()["markdown"]
