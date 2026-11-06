"""HTTP 受理在真 PostgreSQL 的競爭、保存失敗與連線取消界線。"""

import asyncio
from uuid import uuid4

import httpx2
import pytest
from psycopg import AsyncConnection, sql
from psycopg.conninfo import make_conninfo
from sqlalchemy import Engine

from tests.integration.agent.http_support import api_client
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    response_events,
    response_payload,
    sse_response,
)


async def create_turns_url(client: httpx2.AsyncClient) -> str:
    response = await client.post(
        "/workspaces", json={"interviewee_name": "Synthetic admission"}
    )
    assert response.status_code == 201
    return f"/workspaces/{response.json()['workspace_id']}/agent/turns"


async def wait_for_completion(client: httpx2.AsyncClient, location: str) -> None:
    async with asyncio.timeout(5):
        events = await client.get(location + "/events")
    assert events.status_code == 200
    assert '"completed"' in events.text
    assert (await client.get(location)).json()["status"] == "completed"


def test_concurrent_duplicate_shares_execution_and_conflicting_turns_are_rejected(
    pg_engine: Engine,
    checkpoint_conninfo: str,
) -> None:
    async def run() -> None:
        model_started = asyncio.Event()
        finish_model = asyncio.Event()
        calls = 0

        async def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            model_started.set()
            await finish_model.wait()
            return sse_response(EventStream(response_events(response_payload())))

        async with api_client(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
        ) as client:
            url = await create_turns_url(client)
            body = {"turn_id": str(uuid4()), "input": " original input "}
            try:
                first, duplicate = await asyncio.gather(
                    client.post(url, json=body), client.post(url, json=body)
                )
                assert sorted([first.status_code, duplicate.status_code]) == [200, 202]
                await asyncio.wait_for(model_started.wait(), timeout=5)
                assert calls == 1
                assert first.json()["turn_id"] == duplicate.json()["turn_id"]
                assert first.json()["status"] == "running"
                changed = await client.post(
                    url, json={**body, "input": "original input"}
                )
                assert changed.status_code == 409
                another = await client.post(
                    url, json={"turn_id": str(uuid4()), "input": body["input"]}
                )
                assert another.status_code == 409
            finally:
                finish_model.set()
            await wait_for_completion(client, first.headers["Location"])
            assert calls == 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_old_turn_retry_precedes_busy_check_and_workspace_scope_is_isolated(
    pg_engine: Engine,
    checkpoint_conninfo: str,
) -> None:
    async def run() -> None:
        both_running = asyncio.Event()
        finish_models = asyncio.Event()
        calls = 0

        async def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            if calls > 1:
                if calls == 3:
                    both_running.set()
                await finish_models.wait()
            return sse_response(EventStream(response_events(response_payload())))

        async with api_client(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
        ) as client:
            url = await create_turns_url(client)
            old_body = {"turn_id": str(uuid4()), "input": "old turn"}
            old = await client.post(url, json=old_body)
            assert old.status_code == 202
            await wait_for_completion(client, old.headers["Location"])
            other_url = await create_turns_url(client)
            foreign = other_url + "/" + old_body["turn_id"]
            for suffix in ("", "/steps", "/events"):
                assert (await client.get(foreign + suffix)).status_code == 404
            assert (await client.get(other_url)).json() == []
            try:
                current = await client.post(
                    url, json={"turn_id": str(uuid4()), "input": "new turn"}
                )
                assert current.status_code == 202
                repeated_old = await client.post(url, json=old_body)
                assert repeated_old.status_code == 200
                assert repeated_old.json()["status"] == "completed"
                assert repeated_old.json()["input"] == "old turn"
                other = await client.post(
                    other_url,
                    json={"turn_id": old_body["turn_id"], "input": "other workspace"},
                )
                assert other.status_code == 202
                await asyncio.wait_for(both_running.wait(), timeout=5)
                turns = (await client.get(url)).json()
                assert [item["input"] for item in turns] == ["old turn", "new turn"]
                assert [item["status"] for item in turns] == ["completed", "running"]
                assert (await client.get(foreign)).json()["input"] == "other workspace"
                assert calls == 3
            finally:
                finish_models.set()
            await wait_for_completion(client, current.headers["Location"])
            await wait_for_completion(client, other.headers["Location"])
            assert calls == 3

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


async def wait_for_database_lock(conninfo: str, application_name: str) -> None:
    # 只用外部鎖等待作故障注入同步，不以 DB 內容斷言產品結果。
    async with await AsyncConnection.connect(conninfo, autocommit=True) as inspector:
        async with asyncio.timeout(5):
            while True:
                cursor = await inspector.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                    "WHERE application_name = %s AND wait_event_type = 'Lock')",
                    (application_name,),
                )
                row = await cursor.fetchone()
                if row and row[0]:
                    return
                await asyncio.sleep(0)


@pytest.mark.parametrize("disconnect", [False, True])
def test_http_acceptance_waits_for_save_without_cancelling_on_disconnect(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    disconnect: bool,
) -> None:
    async def run() -> None:
        application_name = "agent_admission_" + uuid4().hex
        gated_conninfo = make_conninfo(
            checkpoint_conninfo, application_name=application_name
        )
        calls = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            return sse_response(EventStream(response_events(response_payload())))

        async with (
            api_client(
                pg_engine, gated_conninfo, httpx2.MockTransport(respond)
            ) as client,
            await AsyncConnection.connect(
                checkpoint_conninfo, autocommit=True
            ) as controller,
        ):
            url = await create_turns_url(client)
            lock_key = uuid4().int % (2**63)
            await controller.execute(
                "CREATE FUNCTION pause_loop_checkpoint() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "PERFORM pg_advisory_xact_lock(TG_ARGV[0]::bigint); "
                "RETURN NEW; END $$"
            )
            await controller.execute(
                sql.SQL(
                    "CREATE TRIGGER pause_loop_checkpoint BEFORE INSERT ON checkpoints "
                    "FOR EACH ROW WHEN (NEW.metadata->>'source' = 'loop') "
                    "EXECUTE FUNCTION pause_loop_checkpoint({})"
                ).format(sql.Literal(str(lock_key)))
            )
            await controller.execute("SELECT pg_advisory_lock(%s)", (lock_key,))
            body = {"turn_id": str(uuid4()), "input": "pending durable state"}
            submission = asyncio.create_task(client.post(url, json=body))
            try:
                await wait_for_database_lock(checkpoint_conninfo, application_name)
                assert not submission.done()
                assert calls == 0
                if disconnect:
                    submission.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await submission
            finally:
                await controller.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
            accepted = await asyncio.wait_for(
                client.post(url, json=body) if disconnect else submission, timeout=5
            )
            assert accepted.status_code == (200 if disconnect else 202), accepted.text
            saved = await client.get(accepted.headers["Location"])
            assert saved.json()["input"] == body["input"]
            await wait_for_completion(client, accepted.headers["Location"])
            assert calls == 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_failed_first_state_save_returns_503_and_cold_input_only_turn_is_preserved(
    pg_engine: Engine,
    checkpoint_conninfo: str,
) -> None:
    async def run() -> None:
        calls = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            return sse_response(EventStream(response_events(response_payload())))

        transport = httpx2.MockTransport(respond)
        async with (
            api_client(pg_engine, checkpoint_conninfo, transport) as client,
            await AsyncConnection.connect(
                checkpoint_conninfo, autocommit=True
            ) as controller,
        ):
            url = await create_turns_url(client)
            old = await client.post(
                url, json={"turn_id": str(uuid4()), "input": "private old input"}
            )
            assert old.status_code == 202
            await wait_for_completion(client, old.headers["Location"])
            await controller.execute(
                "CREATE FUNCTION reject_loop_checkpoint() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'synthetic state checkpoint failure'; END $$"
            )
            await controller.execute(
                "CREATE TRIGGER reject_loop_checkpoint BEFORE INSERT ON checkpoints "
                "FOR EACH ROW WHEN (NEW.metadata->>'source' = 'loop') "
                "EXECUTE FUNCTION reject_loop_checkpoint()"
            )
            body = {"turn_id": str(uuid4()), "input": "new original input"}
            location = url + "/" + body["turn_id"]
            try:
                failed = await asyncio.wait_for(client.post(url, json=body), timeout=5)
                assert failed.status_code == 503, failed.text
                assert failed.json()["detail"]["code"] == "agent_unavailable"
                assert calls == 1
            finally:
                await controller.execute(
                    "DROP TRIGGER reject_loop_checkpoint ON checkpoints"
                )

        async with api_client(pg_engine, checkpoint_conninfo, transport) as client:
            cold = await client.get(location)
            assert cold.status_code == 200
            assert cold.json()["status"] == "interrupted"
            assert cold.json()["input"] is None
            assert cold.json()["output"] is None
            assert cold.json()["usage"] is None
            assert (await client.get(location + "/steps")).json() == []
            assert (await client.post(url, json=body)).status_code == 200
            assert (
                await client.post(
                    url, json={"turn_id": str(uuid4()), "input": "skip pending"}
                )
            ).status_code == 409
            assert calls == 1
            resumed = await client.post(location + "/resume")
            assert resumed.status_code == 202, resumed.text
            await wait_for_completion(client, location)
            assert (await client.get(location)).json()["input"] == body["input"]
            assert calls == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
