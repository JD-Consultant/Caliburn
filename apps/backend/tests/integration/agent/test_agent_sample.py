"""公開範例設定沿正式 Host 將顧問角色送進第一個模型請求。"""

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx2
from sqlalchemy import Engine

from caliburn.host.agent_settings import load_agent_configuration
from caliburn.host.app import build_app
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.jd_bundle_support import wait_for_idle
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def test_sample_sends_consultant_role_and_breadth_before_depth_instructions(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    configuration = load_agent_configuration(
        Path(__file__).parents[3] / "agent.example.json",
        checkpoint_conninfo=checkpoint_conninfo,
    )
    requests: list[dict[str, Any]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 1}
            )
        assert request.url.path == "/v1/responses"
        requests.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with open_postgres_checkpointer(checkpoint_conninfo, initialize=True):
            pass
        app = build_app(
            reference_configuration=HOST_REFERENCE_CONFIGURATION,
            database_url=pg_engine.url.render_as_string(hide_password=False),
            agent_configuration=replace(
                configuration,
                client_factory=lambda: offline_client(httpx2.MockTransport(respond)),
            ),
        )
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://testserver"
            ) as client,
        ):
            workspace = await client.post(
                "/workspaces", json={"interviewee_name": "合成範例顧問接線"}
            )
            assert workspace.status_code == 201, workspace.text
            submitted = await client.post(
                f"/workspaces/{workspace.json()['workspace_id']}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "目前負責報價整理與交付核對"},
            )
            assert submitted.status_code == 202, submitted.text
            turn = await wait_for_idle(client, submitted.headers["Location"])
            assert turn["status"] == "completed", turn

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    (request,) = requests
    assert request["model"] == configuration.model_settings["model"]
    instructions = request["instructions"]
    assert "你是 Caliburn 的職務顧問。" in instructions
    assert "初期先建立工作廣度" in instructions
    assert "再選重要或最需釐清的主題深入" in instructions
