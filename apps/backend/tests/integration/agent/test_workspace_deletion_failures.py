"""Workspace 刪除已回滾時，既有待答資格及訪談仍可正常接續。"""

import asyncio
import json
from uuid import UUID, uuid4

import httpx2
from sqlalchemy import Engine, text

from caliburn.modules.agent.bootstrap import BundleConfig
from tests.integration.agent.http_support import api_client
from tests.integration.agent.test_human_answers_http import (
    BUNDLES,
    QUESTIONS,
    read_answers,
    settled,
)
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    response_events,
    response_payload,
    sse_response,
)


def test_failed_delete_preserves_recovered_question_waiting_and_answer_admission(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
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

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(
                *BUNDLES,
                BundleConfig(
                    "tests.integration.agent.human_question_fixture", {"when": "before"}
                ),
            ),
        ) as client:
            workspace = (
                await client.post(
                    "/workspaces",
                    json={"interviewee_name": "Synthetic delete rollback"},
                )
            ).json()["workspace_id"]
            path = f"/workspaces/{workspace}"
            accepted = await client.post(
                path + "/agent/turns",
                json={"turn_id": str(uuid4()), "input": "Synthetic question"},
            )
            assert accepted.status_code == 202, accepted.text
            location = accepted.headers["Location"]
            assert (await settled(client, location))["status"] == "interrupted"
            assert (await client.post(location + "/resume")).status_code == 202
            assert (await settled(client, location))["status"] == "waiting_for_input"
            answers = await read_answers(client, location)

            with pg_engine.connect() as blocker, blocker.begin():
                blocker.execute(
                    text("SELECT id FROM workspaces WHERE id = :id FOR UPDATE"),
                    {"id": UUID(workspace)},
                )
                async with asyncio.timeout(10):
                    deleted = await client.delete(path)
                assert deleted.status_code == 409, deleted.text
                assert deleted.json()["detail"]["reason"] == "lock_timeout"
                assert (await client.get(path)).status_code == 200
                assert (await client.get(location)).json()["status"] == (
                    "waiting_for_input"
                )

            assert requests == 1
            answered = await client.post(location + "/answers", json=answers)
            assert answered.status_code == 202, answered.text
            assert (await settled(client, location))["status"] == "completed"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert requests == 2
