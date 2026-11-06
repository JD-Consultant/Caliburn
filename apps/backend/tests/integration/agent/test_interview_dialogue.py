"""正式 Host 的訪談讀取及 Agent 首尾原話保存。"""

import asyncio
from uuid import UUID, uuid4

import httpx2
from sqlalchemy import Engine

from caliburn.host.app import build_app
from caliburn.modules.agent.bootstrap import BundleConfig
from tests.integration.agent.http_support import api_client
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    message,
    response_events,
    response_payload,
    sse_response,
)


def test_interview_reads_do_not_require_an_agent(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    async def run() -> None:
        app = build_app(
            reference_configuration=HOST_REFERENCE_CONFIGURATION,
            database_url=pg_engine.url.render_as_string(hide_password=False),
        )
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app), base_url="http://testserver"
            ) as client,
        ):
            path = f"/workspaces/{jd_workspace_id}/interview/messages"
            response = await client.get(path)
            assert response.status_code == 200, response.text
            assert response.json() == []
            assert response.headers["Cache-Control"] == "no-store"
            assert (await client.get(path + f"/{uuid4()}")).status_code == 404
            assert (
                await client.get(f"/workspaces/{uuid4()}/interview/messages")
            ).status_code == 404

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_interview_bundle_records_input_and_final_message_only(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        calls = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            output = (
                [message("commentary", "正在整理，不是正式訪談。")]
                if calls == 1
                else [
                    message("commentary", "整理進度"),
                    message(text="您負責專案交付。"),
                ]
            )
            return sse_response(EventStream(response_events(response_payload(output))))

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(BundleConfig("caliburn.bundles.interview"),),
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "訪談接線"})
            ).json()["workspace_id"]
            opening = (
                await client.get(f"/workspaces/{workspace}/interview/messages")
            ).json()
            assert len(opening) == 1
            assert opening[0]["speaker"] == "app"
            turn_id = str(uuid4())
            created = await client.post(
                f"/workspaces/{workspace}/agent/turns",
                json={"turn_id": turn_id, "input": " 我負責專案交付。\n"},
            )
            assert created.status_code == 202, created.text
            async with asyncio.timeout(10):
                while True:
                    turn = (await client.get(created.headers["Location"])).json()
                    if turn["status"] != "running":
                        break
                    await asyncio.sleep(0.01)
            assert turn["status"] == "completed", turn
            response = await client.get(f"/workspaces/{workspace}/interview/messages")
            assert response.status_code == 200, response.text
            transcript = response.json()
            assert transcript[:1] == opening
            recorded = transcript[1:]
            assert [(m["speaker"], m["text"]) for m in recorded] == [
                ("employee", " 我負責專案交付。\n"),
                ("consultant", "您負責專案交付。"),
            ]
            assert all(m["turn_id"] == turn_id for m in recorded)
            assert all(m["reply_to_message_id"] is None for m in transcript)
            detail = await client.get(
                f"/workspaces/{workspace}/interview/messages/{recorded[0]['message_id']}"
            )
            assert detail.status_code == 200, detail.text
            assert detail.json()["content"]["text"] == " 我負責專案交付。\n"
            assert calls == 2

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
            saved = await reader.get(f"/workspaces/{workspace}/interview/messages")
            assert saved.status_code == 200, saved.text
            assert saved.json() == transcript
            assert calls == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
