"""A uses real scoped tools and PostgreSQL completion, with a synthetic SDK transport."""

import json
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStatus
from caliburn.features.job_description.source_persistence import read_source_references
from caliburn.settings import DatabaseSettings, ModelSettings
from tests.unit.test_response_loop import response_at

pytestmark = pytest.mark.postgres


def test_native_model_tools_then_atomic_completion(
    client: TestClient,
    database_settings: DatabaseSettings,
) -> None:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "顧問旅程",
                "employee_name": "合成人員",
            },
        ).json()["job_file_id"]
    )
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={
            "command_id": str(uuid4()),
            "text": "我是前端工程師，負責依設計稿製作網站頁面。",
        },
    ).json()
    scope = ExecutionScope(file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN)
    sent: list[dict] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        assert request.url.path.endswith("/responses")
        sent.append(payload)
        raw = response_at(
            len(sent), final=len(sent) == 2, tools=1 if len(sent) == 1 else 0
        ).model_dump(mode="json")
        raw["service_tier"] = "default"
        if len(sent) == 1:
            raw["output"][-1].update(
                name="revise_jd_profile",
                arguments=json.dumps(
                    {
                        "changes": [
                            {"action": "set_field", "field": "job_title", "value": "前端工程師"},
                            {
                                "action": "add_source",
                                "field": "job_title",
                                "source": {"kind": "current_input"},
                            },
                        ],
                    }
                ),
            )
        else:
            raw["output"][1]["content"][0]["text"] = "已記下職務名稱。最近一個頁面你親自做到哪裡？"
        return httpx2.Response(200, json=raw)

    async def scenario():
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
                api_key="synthetic-not-a-real-key",
                timeout_seconds=5,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
            )
            try:
                runner = ConsultantRunner(sessions, saver, sdk, ModelSettings(api_key="synthetic"))
                exchange = await runner.run(writer)
            finally:
                await sdk.close()
        async with sessions() as session:
            assert (
                await executions.read_execution(session, scope)
            ).status == ExecutionStatus.COMPLETED
        return exchange

    result = client.portal.call(scenario)
    assert result.employee_input.interview_sequence == 2
    assert result.consultant_reply.interview_sequence == 3
    profile = client.get(f"/api/job-files/{file_id}/jd/profile").json()
    assert profile["profile"]["job_title"] == "前端工程師"
    assert len(sent) == 2
    assert sent[0]["input"][-1]["content"] == "我是前端工程師，負責依設計稿製作網站頁面。"
    assert sent[1]["input"][: len(sent[0]["input"])] == sent[0]["input"]
    assert sent[1]["input"][-1]["type"] == "function_call_output"

    async def sources():
        async with client.app.state.database.sessions() as session:
            return await read_source_references(session, file_id, UUID(profile["revision_id"]))

    references = client.portal.call(sources)
    assert len(references) == 1
    assert references[0].source.source_id == result.employee_input.source_id
