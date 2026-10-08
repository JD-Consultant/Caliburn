"""A uses real scoped tools and PostgreSQL completion, with a synthetic SDK transport."""

import json
from decimal import Decimal
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.features.executions import budgets
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStatus
from caliburn.features.job_description.source_persistence import read_source_references
from caliburn.settings import DatabaseSettings, ModelSettings
from tests.unit.test_response_loop import response_at
from tests.unit.test_response_streaming import WireStream

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("max_cost_usd", [None, Decimal("0.02")])
@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-6.1-sol"])
@pytest.mark.parametrize("public_summaries", [False, True])
def test_native_model_tools_then_atomic_completion(
    client: TestClient,
    database_settings: DatabaseSettings,
    max_cost_usd: Decimal | None,
    model: str,
    public_summaries: bool,
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
    summaries = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        payload = json.loads(request.content)
        assert payload["model"] == model
        assert payload["reasoning"]["summary"] == "auto"
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
        raw["model"] = model
        raw["output"][0]["summary"] = [{"type": "summary_text", "text": "合成核對摘要"}]
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
        if public_summaries:
            assert payload["stream"] is True
            item = raw["output"][0]
            return httpx2.Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=WireStream(
                    [
                        {
                            "type": "response.created",
                            "response": {**raw, "status": "in_progress", "output": []},
                        },
                        {
                            "type": "response.output_item.added",
                            "output_index": 0,
                            "item": {**item, "summary": []},
                        },
                        {
                            "type": "response.reasoning_summary_text.delta",
                            "item_id": item["id"],
                            "output_index": 0,
                            "summary_index": 0,
                            "delta": "合成核對摘要",
                        },
                        {"type": "response.completed", "response": raw},
                    ]
                ),
            )
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
                runner = ConsultantRunner(
                    sessions,
                    saver,
                    sdk,
                    ModelSettings(
                        api_key="synthetic",
                        model=model,
                        max_cost_usd=max_cost_usd,
                        max_output_tokens=1024,
                    ),
                    on_reasoning_summary=(lambda scope, summary: summaries.append((scope, summary)))
                    if public_summaries
                    else None,
                )
                exchange = await runner.run(writer)
            finally:
                await sdk.close()

        # A different process has neither the original Runner nor its saver/client.
        # Recovery must read the original complete checkpoints and exchange without IO
        # to the provider, even if today's rollout no longer advertises plan tools.
        def reject_remote(request):
            pytest.fail("Completed recovery cannot send a provider request")

        async with AsyncPostgresSaver.from_conn_string(
            dsn, serde=create_graph_serializer()
        ) as restored_saver:
            restored_sdk = create_responses_client(
                api_key="synthetic-never-used",
                timeout_seconds=5,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(reject_remote)),
            )
            try:
                fresh = ConsultantRunner(
                    sessions,
                    restored_saver,
                    restored_sdk,
                    ModelSettings(api_key="synthetic"),
                    interview_plans_enabled=False,
                )
                assert await fresh.run(writer) == exchange
            finally:
                await restored_sdk.close()
        async with sessions() as session:
            assert (
                await executions.read_execution(session, scope)
            ).status == ExecutionStatus.COMPLETED
            if model == "gpt-6.1-sol":
                policy = await budgets.read_execution_budget(session, scope)
                assert policy.cost_basis.startswith("openai-standard-2026-10-01:")
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
    assert next(item for item in sent[1]["input"] if item.get("type") == "reasoning")[
        "summary"
    ] == [{"type": "summary_text", "text": "合成核對摘要"}]
    if public_summaries:
        assert len(summaries) == 2
        assert all(saved_scope == scope for saved_scope, _ in summaries)
    history = client.get(
        f"/api/job-files/{file_id}/consultant-turns/{scope.execution_id}/reasoning-summaries"
    ).json()
    assert [item["text"] for item in history] == ["合成核對摘要", "合成核對摘要"]

    async def sources():
        async with client.app.state.database.sessions() as session:
            return await read_source_references(session, file_id, UUID(profile["revision_id"]))

    references = client.portal.call(sources)
    assert len(references) == 1
    assert references[0].source.source_id == result.employee_input.source_id
