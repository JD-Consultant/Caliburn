"""正式 Host 載入 Plan Bundle，停用 Agent 後仍可查模組保存內容。"""

import asyncio
import json
from uuid import uuid4

import httpx2
from sqlalchemy import Engine

from caliburn.host.app import build_app
from caliburn.modules.agent.bootstrap import BundleConfig
from tests.integration.agent.http_support import api_client
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def test_host_provides_plan_storage_and_keeps_http_readable_without_agent(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = (
            [
                call("read_interview_plan", "read", "{}"),
                call(
                    "edit_interview_plan",
                    "edit",
                    json.dumps(
                        {"diff": "@@\n+釐清交付範圍\n*** End of File"},
                        ensure_ascii=False,
                    ),
                ),
            ]
            if len(sent) == 1
            else None
        )
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(BundleConfig("caliburn.bundles.plan"),),
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "計畫接線"})
            ).json()["workspace_id"]
            path = f"/workspaces/{workspace}/plan"
            before = (await client.get(path)).json()
            assert before["version"] is None
            created = await client.post(
                f"/workspaces/{workspace}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "建立交付計畫"},
            )
            assert created.status_code == 202, created.text
            async with asyncio.timeout(10):
                while True:
                    turn = (await client.get(created.headers["Location"])).json()
                    if turn["status"] != "running":
                        break
                    await asyncio.sleep(0.01)
            assert turn["status"] == "completed", turn
            saved = await client.get(path)
            assert saved.status_code == 200, saved.text
            assert saved.json() == {
                "workspace_id": workspace,
                "version": 2,
                "body": "釐清交付範圍",
            }
            assert saved.headers["Cache-Control"] == "no-store"

        app = build_app(
            reference_configuration=HOST_REFERENCE_CONFIGURATION,
            database_url=pg_engine.url.render_as_string(hide_password=False),
        )
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app), base_url="http://testserver"
            ) as reader,
        ):
            assert (await reader.get(path)).json() == saved.json()
            assert (await reader.post(path, json={})).status_code == 405

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert sent[0]["input"] == [{"role": "user", "content": "建立交付計畫"}]
    replies = [
        json.loads(item["output"])
        for item in sent[1]["input"]
        if item.get("type") == "function_call_output"
    ]
    assert replies[0] == {"plan": None}
    assert replies[1]["status"] == "updated"
    assert "+釐清交付範圍" in replies[1]["diff"]
