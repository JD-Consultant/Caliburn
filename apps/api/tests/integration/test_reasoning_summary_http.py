"""Summary history and live delivery remain scoped to an actual consultant Turn."""

import asyncio
import json
from uuid import uuid4

import pytest
from langgraph.checkpoint.base import empty_checkpoint

from caliburn.adapters.reasoning_summaries import PublicReasoningSummary
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import (
    AgentRole,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStatus
from caliburn.features.interviews.models import SubmitInterviewInput
from caliburn.workflows.consultant_activity import PublicCommentaryUpdate
from tests.integration.test_activity_stream import create_file
from tests.unit.test_reasoning_summaries import summary_response

pytestmark = pytest.mark.postgres


def test_saved_history_is_scoped_readable_without_model_and_not_part_of_turn_contract(client):
    file_id, other_file = create_file(client), create_file(client)

    async def save():
        accepted = await client.app.state.interview_input_workflow.accept(
            SubmitInterviewInput(file_id, uuid4(), "summary input")
        )
        execution_id = accepted.accepted.execution_id
        scope = ExecutionScope(file_id, execution_id, ExecutionKind.CONSULTANT_TURN)
        thread_id = context_thread_id(
            scope, AgentRole.JOB_CONSULTANT, HistoryWindowKind.COMPLETED_WORK
        )
        checkpoint = empty_checkpoint()
        checkpoint["channel_values"] = {"response_snapshot": summary_response()}
        checkpoint["channel_versions"] = {"response_snapshot": 1}
        await client.app.state.consultant_status_workflow.checkpointer.aput(
            {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}},
            checkpoint,
            {"source": "loop", "step": 0, "parents": {}},
            checkpoint["channel_versions"],
        )
        memory_scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
        async with client.app.state.database.sessions.begin() as session:
            await executions.admit_execution(session, memory_scope)
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            await executions.finish_execution(session, writer, ExecutionStatus.CANCELLED)
        return execution_id, memory_scope.execution_id

    execution_id, memory_id = client.portal.call(save)
    base = f"/api/job-files/{file_id}/consultant-turns/{execution_id}"
    result = client.get(base + "/reasoning-summaries")
    assert result.status_code == 200
    assert "no-store" in result.headers["cache-control"]
    assert [s["text"] for s in result.json()] == ["先核對工作範圍。", "再確認責任分界。"]
    assert set(result.json()[0]) == {
        "response_id",
        "item_id",
        "output_index",
        "summary_index",
        "text",
    }
    assert "PRIVATE" not in result.text
    assert "reasoning_summaries" not in client.get(base).json()
    assert client.get(base + "/activity-stream").status_code == 204
    for wrong_file, wrong_id in ((other_file, execution_id), (file_id, memory_id)):
        for suffix in ("reasoning-summaries", "activity-stream"):
            assert (
                client.get(
                    f"/api/job-files/{wrong_file}/consultant-turns/{wrong_id}/{suffix}"
                ).status_code
                == 404
            )


def test_live_summary_is_separate_scoped_and_disconnect_does_not_cancel(client):
    file_id = create_file(client)

    async def scenario():
        accepted = await client.app.state.interview_input_workflow.accept(
            SubmitInterviewInput(file_id, uuid4(), "stream input")
        )
        execution_id = accepted.accepted.execution_id
        hub = client.app.state.consultant_activity_hub
        path = f"/api/job-files/{file_id}/consultant-turns/{execution_id}/activity-stream"
        disconnected = asyncio.Event()
        messages = []
        first = True

        async def receive():
            nonlocal first
            if first:
                first = False
                return {"type": "http.request", "body": b"", "more_body": False}
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            messages.append(message)
            if message["type"] == "http.response.start":
                hub.publish(
                    uuid4(), execution_id, PublicReasoningSummary("wrong", "wrong", 0, 0, "wrong")
                )
                hub.publish(
                    file_id, execution_id, PublicReasoningSummary("resp", "rs", 0, 1, "核對範圍")
                )
                hub.publish(
                    file_id,
                    execution_id,
                    PublicCommentaryUpdate(file_id, execution_id, "resp", "msg", "接著確認"),
                )
            if message["type"] == "http.response.body" and message.get("body"):
                if sum(bool(m.get("body")) for m in messages) == 2:
                    disconnected.set()

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "root_path": "",
            "query_string": b"",
            "headers": [(b"host", b"127.0.0.1:8100")],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8100),
        }
        async with asyncio.timeout(3):
            await client.app(scope, receive, send)
        assert messages[0]["status"] == 200
        body = b"".join(m.get("body", b"") for m in messages).decode()
        assert body.startswith("event: reasoning_summary\ndata: ")
        events = body.strip().split("\n\n")
        assert len(events) == 2
        assert json.loads(events[0].split("data: ", 1)[1]) == {
            "response_id": "resp",
            "item_id": "rs",
            "output_index": 0,
            "summary_index": 1,
            "text": "核對範圍",
        }
        assert events[1].startswith("event: commentary\n")
        assert json.loads(events[1].split("data: ", 1)[1])["text"] == "接著確認"
        assert (
            await client.app.state.consultant_status_workflow.read(file_id, execution_id)
        ).status == ExecutionStatus.ACTIVE

    client.portal.call(scenario)
