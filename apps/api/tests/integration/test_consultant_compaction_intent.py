"""A's tool intent survives completed work, but adopted preparation is not repeated."""

import json
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import AgentRole, HistoryConflictError
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.settings import DatabaseSettings, ModelSettings
from caliburn.transport.model_tools.context_compaction import ContextCompactionTools
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.context_history import RoleContextHistory
from tests.integration.test_context_histories import admit_writer, prepare, transact
from tests.unit.test_response_loop import response_at

pytestmark = pytest.mark.postgres


def test_requested_compaction_runs_next_turn_once_and_excludes_new_input(
    client: TestClient,
    database_settings: DatabaseSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": "壓縮要求", "employee_name": "合成"},
        ).json()["job_file_id"]
    )
    sent, compactions = [], []
    compacted_items = [
        {"type": "compaction", "id": "cmp_item_synthetic", "encrypted_content": "opaque"},
        {"role": "user", "content": "retained synthetic history"},
    ]

    def accept(text):
        accepted = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={"command_id": str(uuid4()), "text": text},
        )
        assert accepted.status_code == 202
        return ExecutionScope(
            file_id, UUID(accepted.json()["execution_id"]), ExecutionKind.CONSULTANT_TURN
        )

    def respond(request: httpx2.Request) -> httpx2.Response:
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        if request.url.path.endswith("/compact"):
            compactions.append(payload)
            return httpx2.Response(
                200,
                json={
                    "id": "cmp_synthetic",
                    "object": "response.compaction",
                    "created_at": 1,
                    "output": compacted_items,
                    "usage": {
                        "input_tokens": 500,
                        "output_tokens": 30,
                        "total_tokens": 530,
                        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                    },
                },
            )
        assert request.url.path.endswith("/responses")
        sent.append(payload)
        first = len(sent) == 1
        raw = response_at(len(sent), final=not first, tools=2 if first else 0).model_dump(
            mode="json"
        )
        raw["service_tier"] = "default"
        if first:
            # Repeated calls are one idempotent intention, not two future compactions.
            for item in raw["output"][-2:]:
                item.update(name="request_context_compaction", arguments="{}")
        return httpx2.Response(200, json=raw)

    async def run(scope, *, fail_after_preparation=False):
        sessions = client.app.state.database.sessions
        async with sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        async with AsyncPostgresSaver.from_conn_string(
            dsn, serde=create_graph_serializer()
        ) as saver:
            await saver.setup()
            sdk = create_responses_client(
                api_key="synthetic",
                timeout_seconds=5,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
            )
            try:
                runner = ConsultantRunner(sessions, saver, sdk, ModelSettings(api_key="synthetic"))
                if fail_after_preparation:

                    async def interrupt_capture(*args, **kwargs):
                        raise RuntimeError("synthetic interruption after preparation")

                    with monkeypatch.context() as patch:
                        patch.setattr(
                            "caliburn.agents.job_consultant.runner.capture_turn_context",
                            interrupt_capture,
                        )
                        with pytest.raises(RuntimeError, match="synthetic interruption"):
                            await runner.run(writer)
                    await ConsultantCompletionWorkflow(sessions).stop(
                        writer, ExecutionStatus.CANCELLED
                    )
                else:
                    await runner.run(writer)
            finally:
                await sdk.close()

    client.portal.call(run, accept("COMPLETED_INPUT"))
    assert compactions == []  # The request never compresses the currently active Turn.
    results = [item for item in sent[1]["input"] if item.get("type") == "function_call_output"]
    assert [json.loads(item["output"]) for item in results] == [
        {"status": "requested"},
        {"status": "requested"},
    ]

    async def cancel_after_preparation(scope):
        await run(scope, fail_after_preparation=True)

    client.portal.call(cancel_after_preparation, accept("CANCELLED_INPUT"))
    assert len(compactions) == 1
    assert "COMPLETED_INPUT" in json.dumps(compactions[0]["input"])
    assert "CANCELLED_INPUT" not in json.dumps(compactions[0]["input"])
    # Reopen saver/client, replace the input: the adopted C survives cancellation.
    client.portal.call(run, accept("REPLACEMENT_INPUT"))
    assert len(compactions) == 1
    replacement = sent[-1]["input"]
    assert len(replacement) == len(compacted_items) + 2
    assert replacement[:-2] == compacted_items
    assert replacement[-2]["role"] == "user"  # Fresh App data follows all retained items.
    assert replacement[-1] == {"role": "user", "content": "REPLACEMENT_INPUT"}
    assert "CANCELLED_INPUT" not in json.dumps(sent[-1]["input"])
    # The previous request is consumed by preparation, not inherited forever.
    client.portal.call(run, accept("NEXT_INPUT"))
    assert len(compactions) == 1


@pytest.mark.parametrize("status", [ExecutionStatus.CANCELLED, ExecutionStatus.FAILED])
def test_abandoned_compaction_request_does_not_escape_into_replacement_work(
    client: TestClient,
    status: ExecutionStatus,
) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    tools = ContextCompactionTools(
        RoleContextHistory(client.app.state.database.sessions, writer, role, InMemorySaver())
    )
    command = tools.prepare("{}")
    assert isinstance(command, dict)
    prepared = prepare(client, writer)
    assert json.loads(client.portal.call(tools.execute, command)) == {"status": "requested"}
    transact(client, lambda s: executions.finish_execution(s, writer, status))
    with pytest.raises(ExecutionStateError):
        client.portal.call(tools.execute, command)

    replacement = admit_writer(client, job_file_id=writer.scope.job_file_id)
    binding = transact(client, lambda s: history.bind_context_history(s, replacement, role))
    assert binding.base == prepared
    assert not transact(
        client,
        lambda s: history.read_completed_compaction_request(
            s,
            writer.scope.job_file_id,
            role,
            binding.base,
        ),
    )


def test_compaction_tool_rejects_model_scope_and_foreign_saved_intent(client: TestClient) -> None:
    writer = admit_writer(client)
    tools = ContextCompactionTools(
        RoleContextHistory(
            client.app.state.database.sessions,
            writer,
            AgentRole.JOB_CONSULTANT,
            InMemorySaver(),
        )
    )
    rejected = tools.prepare('{"execution_id":"model-must-not-select-scope"}')
    assert isinstance(rejected, str)
    assert json.loads(rejected)["code"] == "invalid_arguments"
    command = tools.prepare("{}")
    assert isinstance(command, dict)
    with pytest.raises(HistoryConflictError, match="Prepare"):
        client.portal.call(tools.execute, command)
    prepare(client, writer)
    with pytest.raises(ValueError, match="another role or execution"):
        client.portal.call(tools.execute, {**command, "execution_id": str(uuid4())})
    assert json.loads(client.portal.call(tools.execute, command)) == {"status": "requested"}
