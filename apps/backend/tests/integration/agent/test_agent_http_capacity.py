"""跨 Workspace 的活動容量、去重與完成後釋放，沿真 HTTP 與 PG 驗證。"""

import asyncio
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from tests.integration.agent.http_support import api_client
from tests.integration.agent.test_agent_http_admission import (
    create_turns_url,
    wait_for_completion,
)
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    response_events,
    response_payload,
    sse_response,
)


@pytest.mark.parametrize("resume", [False, True])
def test_capacity_preserves_retries_and_releases_on_completion(
    pg_engine: Engine, checkpoint_conninfo: str, resume: bool
) -> None:
    async def run() -> None:
        hold_models = False
        fail_model = False
        releases: list[asyncio.Event] = []
        started: asyncio.Queue[asyncio.Event] = asyncio.Queue()

        async def respond(request: httpx2.Request) -> httpx2.Response:
            if hold_models:
                release = asyncio.Event()
                releases.append(release)
                started.put_nowait(release)
                await release.wait()
            payload = response_payload([]) if fail_model else response_payload()
            return sse_response(EventStream(response_events(payload)))

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            max_active_turns=2,
        ) as client:
            first_url = await create_turns_url(client)
            second_url = await create_turns_url(client)
            third_url = await create_turns_url(client)
            old_body = {"turn_id": str(uuid4()), "input": "old first workspace"}
            old = await client.post(first_url, json=old_body)
            assert old.status_code == 202
            await wait_for_completion(client, old.headers["Location"])
            third_body = {"turn_id": old_body["turn_id"], "input": "third workspace"}
            third_location = third_url + "/" + third_body["turn_id"]
            if resume:
                fail_model = True
                interrupted = await client.post(third_url, json=third_body)
                assert interrupted.status_code == 202
                async with asyncio.timeout(5):
                    events = await client.get(third_location + "/events")
                assert '"interrupted"' in events.text
                fail_model = False

            async def third_request() -> httpx2.Response:
                if resume:
                    return await client.post(third_location + "/resume")
                return await client.post(third_url, json=third_body)

            hold_models = True
            try:
                first_body = {
                    "turn_id": str(uuid4()),
                    "input": "active first workspace",
                }
                first = await client.post(first_url, json=first_body)
                assert first.status_code == 202
                first_release = await asyncio.wait_for(started.get(), timeout=5)
                second = await client.post(
                    second_url,
                    json={"turn_id": str(uuid4()), "input": "active second workspace"},
                )
                assert second.status_code == 202
                second_release = await asyncio.wait_for(started.get(), timeout=5)
                rejected = await third_request()
                assert rejected.status_code == 503, rejected.text
                assert rejected.json()["detail"]["code"] == "agent_unavailable"
                if resume:
                    assert (await client.get(third_location)).json()[
                        "status"
                    ] == "interrupted"
                else:
                    assert (await client.get(third_location)).status_code == 404
                    assert (await client.get(third_url)).json() == []
                assert (
                    await client.post(first_url, json=first_body)
                ).status_code == 200
                retried_old = await client.post(first_url, json=old_body)
                assert retried_old.status_code == 200
                assert retried_old.json()["status"] == "completed"
                assert retried_old.json()["input"] == old_body["input"]

                first_release.set()
                await wait_for_completion(client, first.headers["Location"])
                accepted = await third_request()
                assert accepted.status_code == 202, accepted.text
                third_release = await asyncio.wait_for(started.get(), timeout=5)
                assert accepted.json()["input"] == "third workspace"
                assert (await client.get(second.headers["Location"])).json()[
                    "status"
                ] == "running"
                assert [
                    item["input"] for item in (await client.get(first_url)).json()
                ] == ["old first workspace", "active first workspace"]
                assert [
                    item["input"] for item in (await client.get(third_url)).json()
                ] == ["third workspace"]
                second_release.set()
                third_release.set()
                await wait_for_completion(client, second.headers["Location"])
                await wait_for_completion(client, third_location)
                assert len(releases) == 3
            finally:
                hold_models = False
                for release in releases:
                    release.set()

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
