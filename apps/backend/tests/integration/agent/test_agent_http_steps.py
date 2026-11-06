"""逐工具保存及同 call_id 跨模型步的 HTTP 觀察。"""

import asyncio
from collections.abc import Mapping
from typing import cast
from uuid import uuid4

import httpx2
from langchain_core.tools import StructuredTool
from sqlalchemy import Engine

from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from tests.integration.agent.http_support import api_client
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    response_events,
    response_payload,
    sse_response,
)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle((cast(AgentPlugin, config["plugin"]),))


def test_steps_keep_partial_tool_results_and_reused_call_ids_separate(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        effects: list[str] = []
        fail = True

        async def read_item(item: str) -> str:
            nonlocal fail
            effects.append(item)
            if item == "beta" and fail:
                fail = False
                raise RuntimeError("Synthetic effect before missing result")
            return "read " + item

        plugin = AgentPlugin(
            "tools",
            tools=(
                StructuredTool.from_function(
                    coroutine=read_item,
                    name="read_item",
                    description="Read synthetic item",
                ),
            ),
        )
        replies = iter(
            [
                response_payload([call("read_item", "same", '{"item":"alpha"}')]),
                response_payload([call("read_item", "same", '{"item":"beta"}')]),
                response_payload(),
            ]
        )

        def respond(request: httpx2.Request) -> httpx2.Response:
            return sse_response(EventStream(response_events(next(replies))))

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(BundleConfig(__name__, {"plugin": plugin}),),
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            accepted = await client.post(
                f"/workspaces/{workspace}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "tools"},
            )
            location = accepted.headers["Location"]
            async with asyncio.timeout(5):
                while (await client.get(location)).json()["status"] == "running":
                    await asyncio.sleep(0.01)
            steps = (await client.get(location + "/steps")).json()
            assert len(steps) == 2
            assert steps[0]["tool_calls"][0]["output"] == "read alpha"
            assert steps[1]["tool_calls"][0]["output"] is None
            assert steps[1]["tool_calls"][0]["status"] == "not_recorded"
            assert effects == ["alpha", "beta"]
            assert (await client.get(location)).json()["usage"]["total_tokens"] == 42
            assert (await client.post(location + "/resume")).status_code == 202
            async with asyncio.timeout(5):
                while (await client.get(location)).json()["status"] == "running":
                    await asyncio.sleep(0.01)
            steps = (await client.get(location + "/steps")).json()
            assert [step["model_step"] for step in steps] == [1, 2, 3]
            assert steps[0]["tool_calls"][0]["output"] == "read alpha"
            assert steps[1]["tool_calls"][0]["output"] == "read beta"
            assert effects == ["alpha", "beta", "beta"]
            assert (await client.get(location)).json()["usage"]["total_tokens"] == 63

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
