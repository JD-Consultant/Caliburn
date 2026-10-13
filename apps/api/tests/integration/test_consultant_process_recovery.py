"""A real killed process must not repeat durable model outputs or committed JD effects."""

import json
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo
from sqlalchemy import select

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.features.executions import budgets
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStatus, ExecutionWriter
from caliburn.features.interviews import queries as interviews
from caliburn.features.job_description.persistence import JdRevisionRecord
from caliburn.features.job_description.source_persistence import read_source_references
from caliburn.features.job_description.sources import InterviewSource
from caliburn.settings import DatabaseSettings
from caliburn.transport.model_tools.memory_write_checkpoint import MEMORY_CHECKPOINT_TYPES
from tests.fixtures.consultant_crash_worker import ORIGINAL_REPLY
from tests.fixtures.consultant_turn import MANUAL_PURPOSE
from tests.fixtures.consultant_turn import start_consultant_turn as start

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
    "boundary", ["count_unsaved", "count_saved", "response_saved", "tool_committed", "final_saved"]
)
def test_cold_reentry_completes_same_turn_without_repeating_saved_work(
    client: TestClient, database_settings: DatabaseSettings, boundary: str
) -> None:
    writer = start(client, initial_purpose=MANUAL_PURPOSE)
    crashed = invoke_worker(boundary, database_settings, writer)
    assert crashed.returncode == 19, crashed.stderr
    first_events = [json.loads(line) for line in crashed.stdout.splitlines()]
    assert first_events[-1] == {"event": "crash", "boundary": boundary}

    async def read_unknown_count():
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        serializer = create_graph_serializer(allowed_types=MEMORY_CHECKPOINT_TYPES)
        async with AsyncPostgresSaver.from_conn_string(dsn, serde=serializer) as saver:
            request_ids = set()
            async for checkpoint in saver.alist(None):
                values = checkpoint.checkpoint["channel_values"]
                if values.get("request_id") is not None:
                    request_ids.add(values["request_id"])
                assert values.get("input_count") is None
                assert all(
                    channel != "input_count" for _, channel, _ in checkpoint.pending_writes or []
                )
            assert request_ids
        async with client.app.state.database.sessions() as session:
            attempts = []
            for request_id in request_ids:
                attempts.extend(
                    await budgets.read_request_attempts(
                        session, writer.scope, uuid5(request_id, "input_tokens")
                    )
                )
            assert len(attempts) == 1
            original = attempts[0]
            assert original.failure is None
            assert original.reported_cost_usd is None
            assert original.reserved_cost_usd > 0
            return original

    unknown_count = client.portal.call(read_unknown_count) if boundary == "count_unsaved" else None
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
        assert len(before_resume) == 2  # 初稿及輪前人工稿，候選尚未產生新修訂。

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
    assert all(event["manual_net"] for event in requests)
    expected_requests = [
        ("count", 1),
        ("model", 1),
        ("count", 2),
        ("model", 2),
    ]
    if unknown_count is not None:
        expected_requests.insert(0, ("count", 1))
        assert requests[0]["payload_hash"] == requests[1]["payload_hash"]
    assert [(e["kind"], e["step"]) for e in requests] == expected_requests
    requests = requests[int(unknown_count is not None) :]
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
            if unknown_count is not None:
                attempts = await budgets.read_request_attempts(
                    session, writer.scope, unknown_count.request.request_id
                )
                assert len(attempts) == 2
                assert unknown_count in attempts
                assert len({attempt.request for attempt in attempts}) == 1
                assert all(attempt.failure is None for attempt in attempts)
                assert all(attempt.reported_cost_usd is None for attempt in attempts)
                usage = await budgets.read_budget_usage(session, writer.scope)
                assert usage.outbound_attempts == 5

    client.portal.call(verify_effects)
    if boundary in {"tool_committed", "final_saved"}:
        # Reconcile the committed effect; do not create duplicate revisions on reentry.
        assert client.portal.call(revision_ids) == before_resume
