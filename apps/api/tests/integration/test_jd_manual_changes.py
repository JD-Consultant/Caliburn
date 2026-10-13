"""人工 net 使用固定正式兩端；中途原件留給 Debug。"""

import json
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.postgres import PostgresSaver

from caliburn.diagnostics.inspection import read_diagnostics
from caliburn.features.executions import history
from caliburn.features.executions.history_models import AgentRole, HistoryConflictError
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.job_description.change_comparison import compare_jd_snapshots
from caliburn.features.job_description.change_queries import (
    JdChangeHistoryUnavailableError,
    read_manual_change_endpoints,
)
from caliburn.features.job_description.models import ProfileField, ReviseJdProfile, SetProfileField
from caliburn.features.job_description.sources import (
    AddJdSource,
    InterviewSource,
    JdSourceTarget,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.workflows.consultant_turns.completion import ConsultantCompletionWorkflow
from caliburn.workflows.consultant_turns.context import ConsultantContextWorkflow
from caliburn.workflows.job_description.candidates import JdCandidateWorkflow
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


def endpoints(client, turn):
    async def read(session):
        previous = await history.read_previous_completed_execution(
            session, turn.writer.scope, AgentRole.JOB_CONSULTANT
        )
        return await read_manual_change_endpoints(
            session,
            turn.writer.scope.job_file_id,
            turn.writer.scope.execution_id,
            start_revision_id=turn.candidate.base_revision_id,
            previous_completed_execution_id=previous.execution_id if previous else None,
        )

    return transact(client, read)


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
    before, after = endpoints(client, current)
    net = compare_jd_snapshots(before, after)
    assert before.profile.job_title == "前端工程師"
    assert after.profile.job_title == "人工職稱"
    assert after.profile.purpose == "人工使命"
    assert net.profile_fields == (ProfileField.JOB_TITLE, ProfileField.PURPOSE)
    client.portal.call(
        JdCandidateWorkflow(client.app.state.database.sessions).edit,
        current.writer,
        current.candidate.scope,
        ReviseJdProfile(
            uuid4(),
            current.candidate.revision_id,
            (SetProfileField(ProfileField.PURPOSE, "候選改動不得混入"),),
        ),
    )
    assert endpoints(client, current) == (before, after)


def test_first_turn_compares_initial_jd_and_rejects_forged_start(client: TestClient):
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": "先改稿", "employee_name": "合成"},
        ).json()["job_file_id"]
    )
    manual_profile(client, file_id, "purpose", "首輪前人工使命")
    current = start_turn(client, file_id=file_id)
    before, after = endpoints(client, current)
    assert before.profile.purpose is None and after.profile.purpose == "首輪前人工使命"
    with pytest.raises(JdChangeHistoryUnavailableError):
        transact(
            client,
            lambda session: read_manual_change_endpoints(
                session,
                file_id,
                current.writer.scope.execution_id,
                start_revision_id=uuid4(),
                previous_completed_execution_id=None,
            ),
        )


def test_text_restored_but_review_changed_still_has_net(client: TestClient):
    from caliburn.features.interviews import queries as interviews

    first = start_turn(client)
    file_id = first.writer.scope.job_file_id
    original = transact(
        client,
        lambda session: interviews.read_execution_input(
            session, job_file_id=file_id, execution_id=first.writer.scope.execution_id
        ),
    )
    position = client.portal.call(
        JdCandidateWorkflow(client.app.state.database.sessions).edit,
        first.writer,
        first.candidate.scope,
        ReviseJdSources(
            uuid4(),
            first.candidate.revision_id,
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.JOB_TITLE),
            (AddJdSource(InterviewSource(original.source_id)),),
        ),
    )
    complete(client, replace(first, candidate=position))
    manual_profile(client, file_id, "job_title", "臨時職稱")
    manual_profile(client, file_id, "job_title", "前端工程師")
    current = start_turn(client, file_id=file_id)
    before, after = endpoints(client, current)
    net = compare_jd_snapshots(before, after)
    assert net.profile_fields == ()
    assert net.citation_ids == (before.sources[0].citation_id,)
    assert before.sources[0].needs_review is False and after.sources[0].needs_review is True
    captured = client.portal.call(
        lambda: ConsultantContextWorkflow(client.app.state.database.sessions).capture(
            current.writer, plan_enabled=False
        )
    )
    assert captured.manual_changes == net
    assert {item.reference for item in captured.manual_sources} == {
        *before.sources,
        *after.sources,
    }
    assert all(item.interview_sequence == 2 for item in captured.manual_sources)


def test_restored_text_has_no_net_but_debug_keeps_manual_receipts_and_fixed_interval(
    client, database_settings, database_connection
):
    PostgresSaver(database_connection).setup()
    first = start_turn(client)
    complete(client, first)
    file_id = first.writer.scope.job_file_id
    changed = manual_profile(client, file_id, "job_title", "臨時職稱")
    restored = manual_profile(client, file_id, "job_title", "前端工程師")
    manual_profile(client, file_id, "job_title", "前端工程師")
    current = start_turn(client, file_id=file_id)
    net = compare_jd_snapshots(*endpoints(client, current))
    assert (net.profile_fields, net.item_refs, net.citation_ids) == ((), (), ())
    complete(client, current)

    def debug():
        return client.portal.call(
            lambda: read_diagnostics(
                database_settings, execution_id=current.writer.scope.execution_id, full=True
            )
        )[0]

    original = debug()
    manual = [
        item for item in original["operations"]["jd"] if item["candidate_execution_id"] is None
    ]
    assert len(manual) == 3
    assert "臨時職稱" in json.dumps(manual, ensure_ascii=False)
    revisions = {
        item["revision_id"]: item["snapshot"] for item in original["versions"]["jd"]["revisions"]
    }
    assert revisions[changed["revision_id"]]["profile"]["job_title"] == "臨時職稱"
    assert revisions[restored["revision_id"]]["profile"]["job_title"] == "前端工程師"
    manual_profile(client, file_id, "purpose", "後續人工不可混入")
    assert debug()["operations"] == original["operations"]
    assert debug()["versions"]["jd"] == original["versions"]["jd"]


def test_missing_history_endpoint_cannot_fall_back_to_initial(
    client, monkeypatch, database_settings, database_connection
):
    from caliburn.features.executions import history_persistence

    PostgresSaver(database_connection).setup()
    first = start_turn(client)
    complete(client, first)
    current = start_turn(client, file_id=first.writer.scope.job_file_id)

    async def unavailable(*args, **kwargs):
        return None

    monkeypatch.setattr(history_persistence, "read_position_origin", unavailable)
    with pytest.raises(HistoryConflictError):
        endpoints(client, current)
    with pytest.raises(HistoryConflictError):
        client.portal.call(
            lambda: read_diagnostics(
                database_settings, execution_id=current.writer.scope.execution_id, full=True
            )
        )
