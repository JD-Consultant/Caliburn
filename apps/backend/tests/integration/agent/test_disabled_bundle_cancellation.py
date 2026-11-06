"""正式 Host 停用模型能力後，仍履行舊輪的撤回義務。"""

import asyncio
import json
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.modules.agent.bootstrap import BundleConfig
from tests.integration.agent.http_support import api_client
from tests.integration.agent.test_agent_http_cancellation import wait_for_idle
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


@pytest.mark.parametrize("keep_interview_bundle", [False, True])
def test_disabled_bundles_still_cancel_prior_turn_after_host_restart(
    pg_engine: Engine, checkpoint_conninfo: str, keep_interview_bundle: bool
) -> None:
    requests: list[dict[str, Any]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request_body(request))
        output = (
            [
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
                    json.dumps({"questions": [{"question": "Cancelled question?"}]}),
                ),
            ]
            if len(requests) == 1
            else None
        )
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        transport = httpx2.MockTransport(respond)
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
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
            original_messages = (
                await client.get(prefix + "/interview/messages")
            ).json()
            turns = prefix + "/agent/turns"
            accepted = await client.post(
                turns,
                json={"turn_id": str(uuid4()), "input": "Cancelled employee input"},
            )
            assert accepted.status_code == 202, accepted.text
            location = accepted.headers["Location"]
            assert (await wait_for_idle(client, location))[
                "status"
            ] == "waiting_for_input"
            assert (await client.get(prefix + "/plan")).json() == {
                "workspace_id": workspace,
                "version": 3,
                "body": "Second change",
            }
            assert len((await client.get(prefix + "/interview/messages")).json()) == (
                len(original_messages) + 2
            )

        disabled = (
            (
                BundleConfig(
                    "caliburn.bundles.interview",
                    plugins=(),
                ),
                BundleConfig("caliburn.bundles.plan", plugins=()),
            )
            if keep_interview_bundle
            else ()
        )
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=disabled,
            resume_version="v2",
        ) as client:
            assert (await client.post(location + "/resume")).status_code == 409
            cancelled = await client.post(location + "/cancel")
            assert cancelled.status_code == 204, cancelled.text
            restored = {"workspace_id": workspace, "version": 4, "body": None}
            assert (await client.get(prefix + "/plan")).json() == restored
            assert (
                await client.get(prefix + "/interview/messages")
            ).json() == original_messages
            assert len(requests) == 1
            assert (await client.post(location + "/cancel")).status_code == 204
            assert (await client.get(prefix + "/plan")).json() == restored
            assert (await client.get(location)).status_code == 404

            new = await client.post(
                turns, json={"turn_id": str(uuid4()), "input": "Fresh input"}
            )
            assert new.status_code == 202, new.text
            assert (await wait_for_idle(client, new.headers["Location"]))[
                "status"
            ] == "completed"
            assert (await client.get(prefix + "/plan")).json() == restored
            assert (
                await client.get(prefix + "/interview/messages")
            ).json() == original_messages

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert requests[-1]["tools"] == []
    assert requests[-1]["input"] == [{"role": "user", "content": "Fresh input"}]


def test_disabled_bundles_cancel_without_initializing_business_state(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    def respond(request: httpx2.Request) -> httpx2.Response:
        assert request_body(request)["tools"] == []
        return sse_response(EventStream(response_events(response_payload([]))))

    async def run() -> None:
        async with api_client(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            prefix = f"/workspaces/{workspace}"
            original_messages = (
                await client.get(prefix + "/interview/messages")
            ).json()
            empty_plan = {"workspace_id": workspace, "version": None, "body": None}
            assert (await client.get(prefix + "/plan")).json() == empty_plan
            accepted = await client.post(
                prefix + "/agent/turns",
                json={"turn_id": str(uuid4()), "input": "No business write"},
            )
            assert accepted.status_code == 202, accepted.text
            location = accepted.headers["Location"]
            assert (await wait_for_idle(client, location))["status"] == "interrupted"
            cancelled = await client.post(location + "/cancel")
            assert cancelled.status_code == 204, cancelled.text
            assert (await client.get(prefix + "/plan")).json() == empty_plan
            assert (
                await client.get(prefix + "/interview/messages")
            ).json() == original_messages
            assert (await client.post(location + "/cancel")).status_code == 204

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
