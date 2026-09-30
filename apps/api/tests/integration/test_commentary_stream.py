"""Real scoped execution admission plus an in-process ASGI SSE connection."""

import asyncio
import json
from contextlib import ExitStack
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.types import Message, Scope

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStatus
from caliburn.features.interviews.models import SubmitInterviewInput
from caliburn.workflows.consultant_commentary import ConsultantCommentaryHub

pytestmark = pytest.mark.postgres


def create_file(client: TestClient) -> UUID:
    return UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "SSE合成",
                "employee_name": "合成人",
            },
        ).json()["job_file_id"]
    )


def test_stream_sends_only_scoped_public_text_and_disconnect_does_not_stop_execution(
    client: TestClient,
) -> None:
    file_id = create_file(client)

    async def scenario() -> None:
        # Use the real bootstrap-owned instance, not a replacement hiding a missing wire.
        hub = client.app.state.consultant_commentary_hub
        assert isinstance(hub, ConsultantCommentaryHub)
        accepted = await client.app.state.interview_input_workflow.accept(
            SubmitInterviewInput(file_id, uuid4(), "SSE input"),
        )
        execution_id = accepted.accepted.execution_id
        path = f"/api/job-files/{file_id}/consultant-turns/{execution_id}/commentary-stream"
        disconnected = asyncio.Event()
        messages: list[Message] = []
        first_request = True

        async def receive() -> Message:
            nonlocal first_request
            if first_request:
                first_request = False
                return {"type": "http.request", "body": b"", "more_body": False}
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(message: Message) -> None:
            messages.append(message)
            if message["type"] == "http.response.start":
                hub.publish(uuid4(), execution_id, "secret", "secret", "wrong file")
                hub.publish(file_id, execution_id, "r-public", "m-public", "累積\n公開全文")
            if message["type"] == "http.response.body" and message.get("body"):
                disconnected.set()

        scope: Scope = {
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
        headers = dict(messages[0]["headers"])
        assert headers[b"content-type"].startswith(b"text/event-stream")
        assert headers[b"x-accel-buffering"] == b"no"
        assert b"no-store" in b", ".join(
            value for key, value in messages[0]["headers"] if key == b"cache-control"
        )
        body = b"".join(message.get("body", b"") for message in messages).decode()
        expected = {
            "job_file_id": str(file_id),
            "execution_id": str(execution_id),
            "response_id": "r-public",
            "message_id": "m-public",
            "text": "累積\n公開全文",
        }
        assert (
            body
            == "event: commentary\ndata: "
            + json.dumps(
                expected,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n\n"
        )
        # All 64 default slots fit after disconnect; no subscription leaks or replay.
        with ExitStack() as subscriptions:
            for _ in range(64):
                queue = subscriptions.enter_context(hub.subscribe(file_id, execution_id))
                assert queue.empty()
            async with AsyncClient(
                transport=ASGITransport(app=client.app), base_url="http://127.0.0.1:8100"
            ) as http:
                full = await http.get(path)
                assert full.status_code == 503
                assert full.json() == {"detail": {"code": "commentary_stream_capacity"}}
        status = await client.app.state.consultant_status_workflow.read(file_id, execution_id)
        assert status.status == ExecutionStatus.ACTIVE

    client.portal.call(scenario)


def test_stream_checks_original_file_and_operation_family_before_subscribing(
    client: TestClient,
) -> None:
    # Exercise the missing-dependency branch even after main wires the normal hub.
    if hasattr(client.app.state, "consultant_commentary_hub"):
        del client.app.state.consultant_commentary_hub
    file_id, other_file = create_file(client), create_file(client)

    async def accept() -> tuple[UUID, UUID]:
        result = await client.app.state.interview_input_workflow.accept(
            SubmitInterviewInput(file_id, uuid4(), "Scope input"),
        )
        memory_scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
        async with client.app.state.database.sessions.begin() as session:
            await executions.admit_execution(session, memory_scope)
        return result.accepted.execution_id, memory_scope.execution_id

    execution_id, memory_id = client.portal.call(accept)
    for job_file, execution in ((other_file, execution_id), (file_id, memory_id)):
        response = client.get(
            f"/api/job-files/{job_file}/consultant-turns/{execution}/commentary-stream",
        )
        assert response.status_code == 404
        assert response.json() == {"detail": {"code": "consultant_turn_not_found"}}
    response = client.get(
        f"/api/job-files/{file_id}/consultant-turns/{execution_id}/commentary-stream",
    )
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "commentary_stream_not_configured"}}

    async def cancel() -> None:
        scope = ExecutionScope(file_id, execution_id, ExecutionKind.CONSULTANT_TURN)
        async with client.app.state.database.sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            await executions.finish_execution(session, writer, ExecutionStatus.CANCELLED)

    client.portal.call(cancel)
    terminal = client.get(
        f"/api/job-files/{file_id}/consultant-turns/{execution_id}/commentary-stream",
    )
    assert terminal.status_code == 204
    assert terminal.content == b""
    assert "no-store" in terminal.headers["cache-control"]
