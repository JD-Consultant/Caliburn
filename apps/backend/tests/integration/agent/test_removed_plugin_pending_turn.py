"""移除待續插件後仍須辨識未完成輪，不能靠新 Graph 的空排程宣告完成。"""

import asyncio
from collections.abc import Mapping
from uuid import uuid4

import httpx2
import pytest
from langgraph.runtime import Runtime
from sqlalchemy import Engine

from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState
from tests.integration.agent.http_support import api_client
from tests.integration.agent.test_agent_http_cancellation import wait_for_idle
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    response_events,
    response_payload,
    sse_response,
)


async def unfinished_step(
    state: AgentState, *, runtime: Runtime[AgentContext]
) -> Mapping[str, object]:
    raise RuntimeError("Synthetic unfinished plugin")


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    step = (PluginStep("unfinished", unfinished_step),)
    return AgentBundle(
        plugins=(
            AgentPlugin(
                name="removed_plugin",
                on_turn_start=step if config["phase"] == "start" else (),
                on_turn_end=step if config["phase"] == "end" else (),
            ),
        )
    )


@pytest.mark.parametrize("phase", ["start", "end"])
def test_removing_pending_plugin_keeps_turn_interrupted_until_cancelled(
    pg_engine: Engine, checkpoint_conninfo: str, phase: str
) -> None:
    calls = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        transport = httpx2.MockTransport(respond)
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=(BundleConfig(__name__, {"phase": phase}),),
        ) as client:
            created = await client.post(
                "/workspaces", json={"interviewee_name": "Synthetic interrupted turn"}
            )
            assert created.status_code == 201, created.text
            workspace = created.json()["workspace_id"]
            turns = f"/workspaces/{workspace}/agent/turns"
            submitted = await client.post(
                turns, json={"turn_id": str(uuid4()), "input": "Unfinished work"}
            )
            assert submitted.status_code == 202, submitted.text
            location = submitted.headers["Location"]
            assert (await wait_for_idle(client, location))["status"] == "interrupted"
        calls_before_restart = calls
        assert calls_before_restart == (1 if phase == "end" else 0)

        async with api_client(
            pg_engine, checkpoint_conninfo, transport, resume_version="v2"
        ) as client:
            reopened = await client.get(location)
            assert reopened.status_code == 200, reopened.text
            assert reopened.json()["status"] == "interrupted"
            assert (await client.get(turns)).json()[0]["status"] == "interrupted"
            next_input = {"turn_id": str(uuid4()), "input": "New work"}
            assert (await client.post(turns, json=next_input)).status_code == 409
            assert (await client.post(location + "/resume")).status_code == 409
            assert calls == calls_before_restart

            cancelled = await client.post(location + "/cancel")
            assert cancelled.status_code == 204, cancelled.text
            assert (await client.get(location)).status_code == 404
            assert calls == calls_before_restart
            assert (await client.post(location + "/cancel")).status_code == 204
            resumed = await client.post(turns, json=next_input)
            assert resumed.status_code == 202, resumed.text
            complete = await wait_for_idle(client, resumed.headers["Location"])
            assert complete["status"] == "completed"
            assert complete["output"] == "Synthetic reply"
            assert calls == calls_before_restart + 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
