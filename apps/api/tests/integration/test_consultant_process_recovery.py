"""A real killed process must not repeat durable model outputs or committed JD effects."""

import json
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStatus, ExecutionWriter
from caliburn.features.interviews import queries as interviews
from caliburn.features.job_description.persistence import JdRevisionRecord
from caliburn.features.job_description.source_persistence import read_source_references
from caliburn.features.job_description.sources import InterviewSource
from caliburn.settings import DatabaseSettings
from tests.fixtures.consultant_crash_worker import ORIGINAL_REPLY
from tests.integration.test_jd_source_edits import start

pytestmark = pytest.mark.postgres


def invoke_worker(
    boundary: str, settings: DatabaseSettings, writer: ExecutionWriter
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "tests.fixtures.consultant_crash_worker",
            boundary,
            settings.schema,
            str(writer.scope.job_file_id),
            str(writer.scope.execution_id),
            str(writer.writer_id),
        ],
        # pytest's pythonpath applies only to this process. The isolated worker
        # must find the tests package even when pytest starts at the repo root.
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


@pytest.mark.parametrize(
    "boundary", ["count_saved", "response_saved", "tool_committed", "final_saved"]
)
def test_cold_reentry_completes_same_turn_without_repeating_saved_work(
    client: TestClient, database_settings: DatabaseSettings, boundary: str
) -> None:
    writer = start(client)
    crashed = invoke_worker(boundary, database_settings, writer)
    assert crashed.returncode == 19, crashed.stderr
    first_events = [json.loads(line) for line in crashed.stdout.splitlines()]
    assert first_events[-1] == {"event": "crash", "boundary": boundary}
    # Nothing provisional becomes a formal interview/JD just because the process died.
    base_url = f"/api/job-files/{writer.scope.job_file_id}"
    assert len(client.get(f"{base_url}/interviews").json()["messages"]) == 1
    assert not client.get(f"{base_url}/jd/profile").json()["profile"]["job_title"]

    async def revision_ids() -> set[UUID]:
        async with client.app.state.database.sessions() as session:
            return set(
                await session.scalars(
                    select(JdRevisionRecord.revision_id).where(
                        JdRevisionRecord.job_file_id == writer.scope.job_file_id
                    )
                )
            )

    before_resume = client.portal.call(revision_ids)
    if boundary in {"tool_committed", "final_saved"}:
        assert len(before_resume) > 1  # Candidate edits exist but are not yet formal.
    else:
        assert len(before_resume) == 1  # Only the initial JD exists.

    async def replace_writer() -> ExecutionWriter:
        async with client.app.state.database.sessions.begin() as session:
            return await executions.claim_writer(
                session, writer.scope, writer_id=uuid4(), replaces_writer_id=writer.writer_id
            )

    replacement = client.portal.call(replace_writer)
    resumed = invoke_worker("resume", database_settings, replacement)
    assert resumed.returncode == 0, resumed.stderr
    second_events = [json.loads(line) for line in resumed.stdout.splitlines()]
    assert second_events[-1] == {"event": "completed", "reply": ORIGINAL_REPLY}
    requests = [e for e in first_events + second_events if e["event"] == "request"]
    assert [(e["kind"], e["step"]) for e in requests] == [
        ("count", 1),
        ("model", 1),
        ("count", 2),
        ("model", 2),
    ]
    assert requests[0]["input_hash"] == requests[1]["input_hash"]
    assert requests[2]["input_hash"] == requests[3]["input_hash"]
    history = client.get(f"{base_url}/interviews").json()["messages"]
    assert [m["interview_sequence"] for m in history] == [1, 2, 3]
    profile = client.get(f"{base_url}/jd/profile").json()
    assert profile["profile"]["job_title"] == "前端工程師"

    async def verify_effects() -> None:
        async with client.app.state.database.sessions() as session:
            assert (
                await executions.read_execution(session, writer.scope)
            ).status == ExecutionStatus.COMPLETED
            references = await read_source_references(
                session, writer.scope.job_file_id, UUID(profile["revision_id"])
            )
            assert len(references) == 1
            original = await interviews.read_execution_input(
                session,
                job_file_id=writer.scope.job_file_id,
                execution_id=writer.scope.execution_id,
            )
            assert references[0].source == InterviewSource(original.source_id)

    client.portal.call(verify_effects)
    if boundary in {"tool_committed", "final_saved"}:
        # Reconcile the committed effect; do not create duplicate revisions on reentry.
        assert client.portal.call(revision_ids) == before_resume
