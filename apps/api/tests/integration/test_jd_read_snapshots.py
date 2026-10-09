"""Multi-query JD readers survive a committed whole-file deletion at their first seam."""

from dataclasses import replace
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from caliburn.adapters.database import consistent_read_session
from caliburn.features.executions import service as executions
from caliburn.features.job_description import persistence as jd
from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.sources import (
    AddJdSource,
    InterviewSource,
    JdSourceTarget,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_editing import JdEditingWorkflow
from caliburn.workflows.jd_evidence import JdEvidenceWorkflow
from caliburn.workflows.jd_export import JdExportWorkflow
from caliburn.workflows.jd_reads import JdReadWorkflow
from caliburn.workflows.memory_reads import PublishedMemoryRead
from tests.integration.test_consultant_completion import complete, start_turn

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("reader", ["human", "export", "evidence"])
def test_aggregate_keeps_snapshot_when_file_is_deleted_after_head(
    client: TestClient,
    database_connection: psycopg.Connection,
    monkeypatch: pytest.MonkeyPatch,
    reader: str,
) -> None:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "合成", "employee_name": "合成"},
    ).json()
    file_id = UUID(created["job_file_id"])
    url = f"/api/job-files/{file_id}/jd"
    empty = client.get(f"{url}/profile").json()
    added = client.post(
        f"{url}/areas",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": empty["revision_id"],
            "change": {"action": "create_area", "title": "完整保留職責", "scope_text": None},
        },
    ).json()
    sessions = client.app.state.database.sessions
    if reader == "evidence":
        opening_id = UUID(
            client.get(f"/api/job-files/{file_id}/interviews").json()["messages"][0]["source_id"]
        )
        turn = start_turn(client, file_id=file_id)
        position = client.portal.call(
            JdCandidateWorkflow(sessions).edit,
            turn.writer,
            turn.candidate.scope,
            ReviseJdSources(
                uuid4(),
                turn.candidate.revision_id,
                JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
                (AddJdSource(InterviewSource(opening_id)),),
            ),
        )
        complete(client, replace(turn, candidate=position))
        added["revision_id"] = str(position.revision_id)
    original = jd.read_document
    deleted = False

    async def delete_after_head(session, requested):
        nonlocal deleted
        head = await original(session, requested)
        if not deleted:
            deleted = True
            database_connection.execute("DELETE FROM job_files WHERE job_file_id=%s", (file_id,))
        return head

    monkeypatch.setattr(jd, "read_document", delete_after_head)
    if reader == "human":
        result = client.portal.call(JdEditingWorkflow(sessions).read_work, file_id)
        assert result.revision_id == UUID(added["revision_id"])
        assert [area.title for area in result.areas] == ["完整保留職責"]
    elif reader == "export":

        class Renderer:
            async def render_html(self, body: str) -> bytes:
                assert "完整保留職責" in body
                assert client.app.state.database.engine.pool.checkedout() == 0
                return b"complete"

        assert (
            client.portal.call(JdExportWorkflow(sessions, Renderer()).export_current, file_id)
            == b"complete"
        )
    else:
        result = client.portal.call(JdEvidenceWorkflow(sessions).read_overview, file_id)
        assert result.revision_id == UUID(added["revision_id"])
        assert len(result.references) == 1
        assert result.references[0].source_label == "訪談序號 1 · 系統開場"
    assert deleted
    assert database_connection.execute("SELECT count(*) FROM job_files").fetchone() == (0,)


def test_model_preview_survives_turn_end_and_file_delete_after_admission(
    client: TestClient, database_connection: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    turn = start_turn(client)
    scope = turn.writer.scope
    original = executions.read_execution

    async def delete_after_admission(session, requested):
        state = await original(session, requested)
        database_connection.execute(
            "UPDATE executions SET status='cancelled' WHERE execution_id=%s", (scope.execution_id,)
        )
        database_connection.execute(
            "DELETE FROM job_files WHERE job_file_id=%s", (scope.job_file_id,)
        )
        return state

    monkeypatch.setattr(executions, "read_execution", delete_after_admission)
    preview = client.portal.call(
        JdReadWorkflow(client.app.state.database.sessions).read_candidate,
        PublishedMemoryRead(scope, None, 1),
    )
    assert preview.position.revision_id == turn.candidate.revision_id
    assert preview.profile.job_title == "前端工程師"


def test_consistent_session_is_readonly_and_returns_clean_connection_to_pool(
    client: TestClient,
) -> None:
    async def exercise():
        sessions = client.app.state.database.sessions
        async with consistent_read_session(sessions) as session:
            connection_id = await session.scalar(text("SELECT pg_backend_pid()"))
            assert await session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
            assert await session.scalar(text("SHOW transaction_read_only")) == "on"
        with pytest.raises(DBAPIError, match="read-only"):
            async with consistent_read_session(sessions) as session:
                await session.execute(text("UPDATE job_files SET display_name=display_name"))
        async with sessions.begin() as session:
            assert await session.scalar(text("SELECT pg_backend_pid()")) == connection_id
            assert await session.scalar(text("SHOW transaction_isolation")) == "read committed"
            assert await session.scalar(text("SHOW transaction_read_only")) == "off"
            await session.execute(text("UPDATE job_files SET display_name=display_name"))

    client.portal.call(exercise)
