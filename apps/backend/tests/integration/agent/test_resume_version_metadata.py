"""新輪版本與原生 input Checkpoint 同存，範圍沿 Agent／Workspace／Turn。"""

import asyncio
from uuid import UUID, uuid4

import httpx2
import pytest
from langchain_core.runnables import RunnableConfig
from psycopg import AsyncConnection, sql
from sqlalchemy import Engine

from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.http_support import api_client
from tests.integration.agent.test_human_answers_http import settled
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    response_events,
    response_payload,
    sse_response,
)


def test_each_new_turn_saves_current_version_in_its_first_input_checkpoint(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        requests = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            return sse_response(EventStream(response_events(response_payload())))

        transport = httpx2.MockTransport(respond)
        async with api_client(pg_engine, checkpoint_conninfo, transport) as client:
            workspaces = [
                (
                    await client.post("/workspaces", json={"interviewee_name": name})
                ).json()["workspace_id"]
                for name in ("甲", "乙")
            ]
        first, second = str(uuid4()), str(uuid4())
        cases = [
            ("alpha", workspaces[0], first, "v1"),
            ("alpha", workspaces[0], second, "v2"),
            ("alpha", workspaces[1], first, "v3"),
            ("beta", workspaces[0], first, "v4"),
        ]
        for agent_id, workspace, turn_id, version in cases:
            async with api_client(
                pg_engine,
                checkpoint_conninfo,
                transport,
                agent_id=agent_id,
                resume_version=version,
            ) as client:
                response = await client.post(
                    f"/workspaces/{workspace}/agent/turns",
                    json={"turn_id": turn_id, "input": "版本範圍"},
                )
                assert response.status_code == 202, response.text
                assert (await settled(client, response.headers["Location"]))[
                    "status"
                ] == "completed"

        # 使用官方 Checkpointer 查讀，驗 metadata 契約，不另查產品私有表。
        async with open_postgres_checkpointer(checkpoint_conninfo) as saver:
            for agent_id, workspace, turn_id, version in cases:
                history = [
                    saved
                    async for saved in saver.alist(
                        {"configurable": {"thread_id": f"{agent_id}:{workspace}"}},
                        filter={"turn_id": turn_id},
                    )
                ]
                assert history[-1].metadata["source"] == "input"
                assert {saved.metadata.get("resume_version") for saved in history} == {
                    version
                }
                assert all("input_fingerprint" in saved.metadata for saved in history)
        assert requests == 4

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("rejected_source", ["input", "loop"])
def test_save_failure_never_acknowledges_a_turn_or_inherits_previous_turn_version(
    pg_engine: Engine, checkpoint_conninfo: str, rejected_source: str
) -> None:
    async def run() -> None:
        requests = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            return sse_response(EventStream(response_events(response_payload())))

        transport = httpx2.MockTransport(respond)
        async with api_client(pg_engine, checkpoint_conninfo, transport) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "首存故障"})
            ).json()["workspace_id"]
            turns_url = f"/workspaces/{workspace}/agent/turns"
            old_turn_id = str(uuid4())
            response = await client.post(
                turns_url, json={"turn_id": old_turn_id, "input": "前輪"}
            )
            assert response.status_code == 202
            assert (await settled(client, response.headers["Location"]))[
                "status"
            ] == "completed"

        turn_id = str(uuid4())
        body = {"turn_id": turn_id, "input": "新輪"}
        location = turns_url + "/" + turn_id
        async with (
            api_client(
                pg_engine, checkpoint_conninfo, transport, resume_version="v2"
            ) as client,
            await AsyncConnection.connect(
                checkpoint_conninfo, autocommit=True
            ) as controller,
        ):
            await controller.execute(
                "CREATE FUNCTION reject_version_save() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'synthetic version save failure'; END $$"
            )
            await controller.execute(
                sql.SQL(
                    "CREATE TRIGGER reject_version BEFORE INSERT ON checkpoints "
                    "FOR EACH ROW WHEN (NEW.metadata->>'source' = {}) "
                    "EXECUTE FUNCTION reject_version_save()"
                ).format(sql.Literal(rejected_source))
            )
            try:
                response = await client.post(turns_url, json=body)
                assert response.status_code == 503, response.text
                assert requests == 1
            finally:
                await controller.execute("DROP TRIGGER reject_version ON checkpoints")

        config: RunnableConfig = {
            "configurable": {"thread_id": f"http-test:{workspace}"}
        }
        async with open_postgres_checkpointer(checkpoint_conninfo) as saver:
            saved = await saver.aget_tuple(config)
            assert saved is not None
            if rejected_source == "input":
                assert saved.metadata.get("turn_id") == old_turn_id
                assert saved.metadata.get("resume_version") == "v1"
            else:
                assert saved.metadata["source"] == "input"
                assert saved.metadata.get("turn_id") == turn_id
                assert saved.metadata.get("resume_version") == "v2"
                assert saved.checkpoint["channel_values"]["turn_id"] == UUID(
                    old_turn_id
                )

        async with api_client(pg_engine, checkpoint_conninfo, transport) as client:
            current = await client.get(location)
            if rejected_source == "input":
                assert current.status_code == 404
            else:
                assert current.status_code == 200
                assert current.json()["status"] == "interrupted"
                assert current.json()["input"] is None
                assert (await client.post(location + "/resume")).status_code == 409
                assert (await client.post(turns_url, json=body)).status_code == 200
            assert requests == 1

        async with api_client(
            pg_engine, checkpoint_conninfo, transport, resume_version="v2"
        ) as client:
            response = (
                await client.post(turns_url, json=body)
                if rejected_source == "input"
                else await client.post(location + "/resume")
            )
            assert response.status_code == 202, response.text
            assert (await settled(client, location))["status"] == "completed"
            assert requests == 2
        async with open_postgres_checkpointer(checkpoint_conninfo) as saver:
            history = [
                saved
                async for saved in saver.alist(config, filter={"turn_id": turn_id})
            ]
            assert history[-1].metadata["source"] == "input"
            assert {saved.metadata.get("resume_version") for saved in history} == {"v2"}

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
