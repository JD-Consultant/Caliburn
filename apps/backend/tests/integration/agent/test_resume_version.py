"""恢復版本沿正式 HTTP 與真 PG 保存；不相容配置不能開始新工作。"""

import asyncio
import json
from uuid import uuid4

import httpx2
from langgraph.checkpoint.base import CheckpointTuple
from sqlalchemy import Engine

from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.http_support import api_client
from tests.integration.agent.test_human_answers_http import (
    BUNDLES,
    QUESTIONS,
    read_answers,
    settled,
    start_question,
)
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    response_events,
    response_payload,
    sse_response,
)


async def saved_turn_checkpoints(
    checkpoint_conninfo: str, location: str
) -> list[CheckpointTuple]:
    workspace_id = httpx2.URL(location).path.split("/")[2]
    turn_id = location.rsplit("/", 1)[1]
    async with open_postgres_checkpointer(checkpoint_conninfo) as saver:
        history = [
            saved
            async for saved in saver.alist(
                {"configurable": {"thread_id": f"http-test:{workspace_id}"}},
                filter={"turn_id": turn_id},
            )
        ]
        assert history
        return history


def test_incompatible_answer_is_rejected_before_execution_and_original_can_resume(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        requests = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            output = (
                [call("ask_user_question", "call_ask", json.dumps(QUESTIONS))]
                if requests == 1
                else None
            )
            return sse_response(EventStream(response_events(response_payload(output))))

        transport = httpx2.MockTransport(respond)
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=BUNDLES
        ) as client:
            location = await start_question(client)
            answers = await read_answers(client, location)
            original = (await client.get(location)).json()
            steps = (await client.get(location + "/steps")).json()
            questions = (await client.get(location + "/questions")).json()
        checkpoints = await saved_turn_checkpoints(checkpoint_conninfo, location)

        async with api_client(
            pg_engine, checkpoint_conninfo, transport, resume_version="v2"
        ) as client:
            response = await client.post(location + "/answers", json=answers)
            assert response.status_code == 409, response.text
            assert response.json()["detail"]["code"] == "agent_turn_conflict"
            assert (await client.post(location + "/resume")).status_code == 409
            assert (await client.get(location)).json() == original
            assert (await client.get(location + "/steps")).json() == steps
            assert (await client.get(location + "/questions")).json() == questions
            turns_url, turn_id = location.rsplit("/", 1)
            duplicate = await client.post(
                turns_url, json={"turn_id": turn_id, "input": original["input"]}
            )
            assert duplicate.status_code == 200
            assert (
                await client.post(
                    turns_url, json={"turn_id": str(uuid4()), "input": "不得跳過"}
                )
            ).status_code == 409
            assert requests == 1
        assert (
            await saved_turn_checkpoints(checkpoint_conninfo, location) == checkpoints
        )

        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=BUNDLES
        ) as client:
            response = await client.post(location + "/answers", json=answers)
            assert response.status_code == 202, response.text
            assert (await settled(client, location))["status"] == "completed"
            assert requests == 2
        assert {
            saved.metadata.get("resume_version")
            for saved in await saved_turn_checkpoints(checkpoint_conninfo, location)
        } == {"v1"}

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_saved_answer_remains_readable_and_idempotent_with_bundle_disabled(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        requests: list[dict[str, object]] = []

        def respond(request: httpx2.Request) -> httpx2.Response:
            requests.append(json.loads(request.content))
            output = (
                [call("ask_user_question", "call_ask", json.dumps(QUESTIONS))]
                if len(requests) == 1
                else None
            )
            return sse_response(EventStream(response_events(response_payload(output))))

        transport = httpx2.MockTransport(respond)
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=BUNDLES
        ) as client:
            location = await start_question(client)
            answers = await read_answers(client, location)
            assert (
                await client.post(location + "/answers", json=answers)
            ).status_code == 202
            completed = await settled(client, location)
            steps = (await client.get(location + "/steps")).json()
            questions = (await client.get(location + "/questions")).json()

        async with api_client(
            pg_engine, checkpoint_conninfo, transport, resume_version="v2"
        ) as client:
            assert (await client.get(location)).json() == completed
            assert (await client.get(location + "/steps")).json() == steps
            assert (await client.get(location + "/questions")).json() == questions
            duplicate = await client.post(location + "/answers", json=answers)
            assert duplicate.status_code == 200, duplicate.text
            different = {
                **answers,
                "answers": [
                    {**answers["answers"][0], "selected": ["品質"]},
                    answers["answers"][1],
                ],
            }
            assert (
                await client.post(location + "/answers", json=different)
            ).status_code == 409
            assert len(requests) == 2
            response = await client.post(
                location.rsplit("/", 1)[0],
                json={"turn_id": str(uuid4()), "input": "新輪沒有提問工具"},
            )
            assert response.status_code == 202, response.text
            assert (await settled(client, response.headers["Location"]))[
                "status"
            ] == "completed"
            assert len(requests) == 3
            assert not requests[-1].get("tools")

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_incompatible_recovery_preserves_failed_turn_until_original_version_returns(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        requests = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            if requests == 1:
                raise httpx2.ConnectError("合成模型故障")
            return sse_response(EventStream(response_events(response_payload())))

        transport = httpx2.MockTransport(respond)
        async with api_client(pg_engine, checkpoint_conninfo, transport) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "故障恢復"})
            ).json()["workspace_id"]
            response = await client.post(
                f"/workspaces/{workspace}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "合成故障"},
            )
            assert response.status_code == 202
            location = response.headers["Location"]
            original = await settled(client, location)
            assert original["status"] == "interrupted"
        checkpoints = await saved_turn_checkpoints(checkpoint_conninfo, location)

        async with api_client(
            pg_engine, checkpoint_conninfo, transport, resume_version="v2"
        ) as client:
            response = await client.post(location + "/resume")
            assert response.status_code == 409, response.text
            assert response.json()["detail"]["code"] == "agent_turn_conflict"
            assert (await client.get(location)).json() == original
            assert requests == 1
        assert (
            await saved_turn_checkpoints(checkpoint_conninfo, location) == checkpoints
        )

        async with api_client(pg_engine, checkpoint_conninfo, transport) as client:
            response = await client.post(location + "/resume")
            assert response.status_code == 202, response.text
            assert (await settled(client, location))["status"] == "completed"
            assert requests == 2
        assert {
            saved.metadata.get("resume_version")
            for saved in await saved_turn_checkpoints(checkpoint_conninfo, location)
        } == {"v1"}

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
