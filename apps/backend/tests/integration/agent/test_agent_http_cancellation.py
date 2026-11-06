"""整輪取消經正式 HTTP、離線模型與真 PostgreSQL 驗證。"""

import asyncio
import json
from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.runtime import Runtime
from langgraph.types import interrupt
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
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    message,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle((cast(AgentPlugin, config["plugin"]),))


async def wait_for_idle(client: httpx2.AsyncClient, location: str) -> dict[str, Any]:
    async with asyncio.timeout(5):
        while True:
            response = await client.get(location)
            assert response.status_code == 200, response.text
            if response.json()["status"] != "running":
                return cast(dict[str, Any], response.json())
            await asyncio.sleep(0.01)


def test_waiting_turn_cancel_is_hidden_and_new_turn_initializes(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        async def ask(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            if state["turn_input"] == "cancel this":
                interrupt("Synthetic question")
            return {}

        plugin = AgentPlugin("ask", on_turn_start=(PluginStep("ask", ask),))
        bundles = (BundleConfig(__name__, {"plugin": plugin}),)

        def respond(request: httpx2.Request) -> httpx2.Response:
            return sse_response(EventStream(response_events(response_payload())))

        transport = httpx2.MockTransport(respond)
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=bundles
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            url = f"/workspaces/{workspace}/agent/turns"
            body = {"turn_id": str(uuid4()), "input": "cancel this"}
            accepted = await client.post(url, json=body)
            assert accepted.status_code == 202, accepted.text
            location = accepted.headers["Location"]
            assert (await wait_for_idle(client, location))[
                "status"
            ] == "waiting_for_input"

            cancelled = await client.post(location + "/cancel")
            assert cancelled.status_code == 204, cancelled.text
            assert cancelled.content == b""
            assert (await client.post(location + "/cancel")).status_code == 204
            for suffix in ("", "/steps", "/events", "/questions"):
                assert (await client.get(location + suffix)).status_code == 404
            assert (await client.get(url)).json() == []
            assert (await client.post(url, json=body)).status_code == 409
            assert (await client.post(location + "/resume")).status_code == 409

        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=bundles
        ) as client:
            assert (await client.post(location + "/cancel")).status_code == 204
            new = await client.post(
                url, json={"turn_id": str(uuid4()), "input": "start fresh"}
            )
            assert new.status_code == 202, new.text
            completed = await wait_for_idle(client, new.headers["Location"])
            assert completed["status"] == "completed"
            assert completed["input"] == "start fresh"
            assert completed["output"] == "Synthetic reply"
            assert (await client.post(location + "/cancel")).status_code == 204
            assert (await client.post(location + "/resume")).status_code == 409
            assert (
                await client.post(new.headers["Location"] + "/cancel")
            ).status_code == 409
            assert len((await client.get(url)).json()) == 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_cancel_restores_plan_and_withdraws_answered_interview_before_new_turn(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        requests: list[dict[str, Any]] = []

        def respond(request: httpx2.Request) -> httpx2.Response:
            requests.append(request_body(request))
            output: list[dict[str, object]] | None
            if len(requests) == 1:
                output = [
                    call("read_interview_plan", "read", "{}"),
                    call(
                        "edit_interview_plan",
                        "edit_one",
                        json.dumps({"diff": "@@\n+First change\n*** End of File"}),
                    ),
                    call(
                        "edit_interview_plan",
                        "edit_two",
                        json.dumps({"diff": "@@\n-First change\n+Second change"}),
                    ),
                    call(
                        "ask_user_question",
                        "ask",
                        json.dumps(
                            {
                                "questions": [
                                    {"question": "Synthetic cancelled question?"}
                                ]
                            }
                        ),
                    ),
                ]
            else:
                output = [] if len(requests) == 2 else None
            return sse_response(EventStream(response_events(response_payload(output))))

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(
                BundleConfig("caliburn.bundles.plan"),
                BundleConfig("caliburn.bundles.interview"),
                BundleConfig("caliburn.bundles.human_questions"),
            ),
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            prefix = f"/workspaces/{workspace}"
            url = prefix + "/agent/turns"
            initial_messages = (await client.get(prefix + "/interview/messages")).json()
            first_turn = str(uuid4())
            accepted = await client.post(
                url, json={"turn_id": first_turn, "input": "Cancelled employee input"}
            )
            location = accepted.headers["Location"]
            assert (await wait_for_idle(client, location))[
                "status"
            ] == "waiting_for_input"
            assert (await client.get(prefix + "/plan")).json()[
                "body"
            ] == "Second change"
            exchange = (await client.get(location + "/questions")).json()[0]
            answer = {
                "model_step": exchange["model_step"],
                "call_id": exchange["call_id"],
                "answers": [
                    {
                        "question_message_id": exchange["questions"][0]["message_id"],
                        "selected": [],
                        "custom": "Cancelled employee answer",
                    }
                ],
            }
            answered = await client.post(location + "/answers", json=answer)
            assert answered.status_code == 202, answered.text
            assert (await wait_for_idle(client, location))["status"] == "interrupted"
            originals = (await client.get(prefix + "/interview/messages")).json()
            assert originals[: len(initial_messages)] == initial_messages
            assert (
                len([item for item in originals if item["turn_id"] == first_turn]) == 3
            )
            assert (await client.post(location + "/cancel")).status_code == 204
            restored = (await client.get(prefix + "/plan")).json()
            assert restored == {"workspace_id": workspace, "body": None, "version": 4}
            assert (
                await client.get(prefix + "/interview/messages")
            ).json() == initial_messages
            assert (await client.get(location + "/questions")).status_code == 404
            assert (
                await client.post(location + "/answers", json=answer)
            ).status_code == 409
            assert (await client.post(location + "/cancel")).status_code == 204
            assert (await client.get(prefix + "/plan")).json() == restored
            new_turn = str(uuid4())
            new = await client.post(
                url, json={"turn_id": new_turn, "input": "Fresh input"}
            )
            assert (await wait_for_idle(client, new.headers["Location"]))[
                "status"
            ] == "completed"
            transcript = (await client.get(prefix + "/interview/messages")).json()
            assert transcript[: len(initial_messages)] == initial_messages
            assert len(transcript) == len(initial_messages) + 2
            assert all(
                item["turn_id"] == new_turn
                for item in transcript[len(initial_messages) :]
            )
            assert "Cancelled employee" not in json.dumps(requests[-1]["input"])

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_failed_cleanup_blocks_resume_and_new_turn_until_cold_retry(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        fail = True

        async def ask(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            interrupt("Synthetic question")
            return {}

        async def cleanup(
            state: AgentState | None,
            *,
            workspace_id: UUID,
            turn_id: UUID,
            context: AgentContext,
        ) -> None:
            if fail:
                raise RuntimeError("Synthetic unavailable business storage")

        plugin = AgentPlugin(
            "ask", on_turn_start=(PluginStep("ask", ask),), on_turn_cancel=cleanup
        )
        bundles = (BundleConfig(__name__, {"plugin": plugin}),)

        def respond(request: httpx2.Request) -> httpx2.Response:
            raise AssertionError("Waiting or cancelled turns must not call the model")

        transport = httpx2.MockTransport(respond)
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=bundles
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            url = f"/workspaces/{workspace}/agent/turns"
            body = {"turn_id": str(uuid4()), "input": "cancel this"}
            accepted = await client.post(url, json=body)
            location = accepted.headers["Location"]
            await wait_for_idle(client, location)
            assert (await client.post(location + "/cancel")).status_code == 503
            assert (await client.get(location)).status_code == 404
            assert (await client.post(location + "/resume")).status_code == 409

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=bundles,
            resume_version="v2",
        ) as client:
            assert (await client.post(url, json=body)).status_code == 409
            new_body = {"turn_id": str(uuid4()), "input": "start fresh"}
            assert (await client.post(url, json=new_body)).status_code == 409
            assert (await client.post(location + "/cancel")).status_code == 503
            fail = False
            assert (await client.post(location + "/cancel")).status_code == 204
            assert (await client.post(url, json=new_body)).status_code == 202

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("finishes_naturally", [False, True])
def test_running_cancel_waits_for_writer_and_resolves_natural_completion(
    pg_engine: Engine, checkpoint_conninfo: str, finishes_naturally: bool
) -> None:
    async def run() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            entered.set()
            await release.wait()
            output = None if finishes_naturally else [message("commentary", "Partial")]
            return sse_response(EventStream(response_events(response_payload(output))))

        async with api_client(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            url = f"/workspaces/{workspace}/agent/turns"
            body = {"turn_id": str(uuid4()), "input": "running"}
            accepted = await client.post(url, json=body)
            location = accepted.headers["Location"]
            cancellation = None
            try:
                async with asyncio.timeout(5):
                    await entered.wait()
                    cancellation = asyncio.create_task(
                        client.post(location + "/cancel")
                    )
                    while (await client.post(url, json=body)).status_code != 409:
                        await asyncio.sleep(0.01)
                    assert not cancellation.done()
                    release.set()
                    result = await cancellation
                assert result.status_code == (409 if finishes_naturally else 204), (
                    result.text
                )
                assert calls == 1
                saved = await client.get(location)
                if finishes_naturally:
                    assert saved.json()["status"] == "completed"
                else:
                    assert saved.status_code == 404
            finally:
                release.set()
                if cancellation is not None:
                    await cancellation

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
