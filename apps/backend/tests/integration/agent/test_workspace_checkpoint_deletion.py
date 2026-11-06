"""整份刪除沿正式 Host 清除所有角色的保存資料，不影響其他 Workspace。"""

import asyncio
from pathlib import Path
from uuid import uuid4

import httpx2
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import Engine

from caliburn.host.entrypoint import create_app
from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.http_support import api_app, api_client
from tests.integration.agent.test_agent_http_cancellation import wait_for_idle
from tests.reference_configuration import write_reference_configuration
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    message,
    response_events,
    response_payload,
    sse_response,
)


def test_delete_clears_all_agent_threads_and_preserves_other_workspace(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        def respond(request: httpx2.Request) -> httpx2.Response:
            return sse_response(EventStream(response_events(response_payload())))

        transport = httpx2.MockTransport(respond)
        async with api_client(pg_engine, checkpoint_conninfo, transport) as client:
            workspaces = [
                (
                    await client.post("/workspaces", json={"interviewee_name": name})
                ).json()["workspace_id"]
                for name in ("Remove synthetic", "Keep synthetic")
            ]
            for workspace in workspaces:
                submitted = await client.post(
                    f"/workspaces/{workspace}/agent/turns",
                    json={"turn_id": str(uuid4()), "input": "Synthetic input"},
                )
                assert submitted.status_code == 202, submitted.text
                assert (await wait_for_idle(client, submitted.headers["Location"]))[
                    "status"
                ] == "completed"

        # 另一個已停用 Agent 的 thread 也屬於同一份 Workspace。
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, agent_id="retired-agent"
        ) as client:
            submitted = await client.post(
                f"/workspaces/{workspaces[0]}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "Other role"},
            )
            await wait_for_idle(client, submitted.headers["Location"])

        async with api_client(pg_engine, checkpoint_conninfo, transport) as client:
            response = await client.delete(f"/workspaces/{workspaces[0]}")
            assert response.status_code == 204, response.text
            assert (await client.get(f"/workspaces/{workspaces[0]}")).status_code == 404
            assert (await client.get(f"/workspaces/{workspaces[1]}")).status_code == 200
            assert (
                await client.delete(f"/workspaces/{workspaces[0]}")
            ).status_code == 204

        async with open_postgres_checkpointer(checkpoint_conninfo) as saver:
            remaining = {
                entry.config["configurable"]["thread_id"]
                async for entry in saver.alist(None)
            }
            assert remaining == {f"http-test:{workspaces[1]}"}

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_delete_works_without_model_configuration_after_restart(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def run() -> None:
        def respond(request: httpx2.Request) -> httpx2.Response:
            return sse_response(EventStream(response_events(response_payload())))

        async with api_client(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            submitted = await client.post(
                f"/workspaces/{workspace}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "Synthetic input"},
            )
            await wait_for_idle(client, submitted.headers["Location"])

        monkeypatch.setenv(
            "CALIBURN_REBUILD_DATABASE_URL",
            pg_engine.url.render_as_string(hide_password=False),
        )
        monkeypatch.setenv(
            "CALIBURN_REBUILD_AGENT_CHECKPOINT_CONNINFO", checkpoint_conninfo
        )
        monkeypatch.delenv("CALIBURN_REBUILD_AGENT_CONFIG", raising=False)
        monkeypatch.setenv(
            "CALIBURN_REBUILD_REFERENCE_CONFIG",
            str(write_reference_configuration(tmp_path)),
        )
        app = create_app()
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://testserver"
            ) as client,
        ):
            assert (await client.delete(f"/workspaces/{workspace}")).status_code == 204
        async with open_postgres_checkpointer(checkpoint_conninfo) as saver:
            assert [entry async for entry in saver.alist(None)] == []

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("disconnect", [False, True])
def test_delete_blocks_admission_and_waits_for_active_writer(
    pg_engine: Engine, checkpoint_conninfo: str, disconnect: bool
) -> None:
    async def run() -> None:
        entered, release = asyncio.Event(), asyncio.Event()
        calls = 0

        async def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            entered.set()
            await release.wait()
            # 沒有安全停止則 commentary 會繼續呼叫模型。
            output = [message("commentary", "Still working")] if calls == 1 else None
            return sse_response(EventStream(response_events(response_payload(output))))

        async with api_client(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            url = f"/workspaces/{workspace}"
            body = {"turn_id": str(uuid4()), "input": "Running"}
            assert (
                await client.post(url + "/agent/turns", json=body)
            ).status_code == 202
            deletion = None
            try:
                async with asyncio.timeout(5):
                    await entered.wait()
                    deletion = asyncio.create_task(client.delete(url))
                    while True:
                        rejected = await client.post(url + "/agent/turns", json=body)
                        if rejected.status_code != 202:
                            break
                        await asyncio.sleep(0.01)
                    assert rejected.status_code == 409, rejected.text
                    assert not deletion.done()
                    assert (await client.get(url)).status_code == 200
                    if disconnect:
                        deletion.cancel()
                        with pytest.raises(asyncio.CancelledError):
                            await deletion
                        deletion = asyncio.create_task(client.delete(url))
                    release.set()
                    assert (await deletion).status_code == 204
                assert calls == 1
                assert (
                    await client.post(url + "/agent/turns", json=body)
                ).status_code == 404
            finally:
                release.set()
                if deletion is not None:
                    await deletion
        async with open_postgres_checkpointer(checkpoint_conninfo) as saver:
            assert [entry async for entry in saver.alist(None)] == []

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_checkpoint_cleanup_failure_is_not_success_and_delete_can_retry(
    pg_engine: Engine, checkpoint_conninfo: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run() -> None:
        def respond(request: httpx2.Request) -> httpx2.Response:
            return sse_response(EventStream(response_events(response_payload())))

        async with api_app(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
        ) as app:
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://testserver",
            ) as client:
                workspace = (
                    await client.post(
                        "/workspaces", json={"interviewee_name": "Synthetic"}
                    )
                ).json()["workspace_id"]
                url = f"/workspaces/{workspace}"
                submitted = await client.post(
                    url + "/agent/turns",
                    json={
                        "turn_id": str(uuid4()),
                        "input": "Synthetic input",
                    },
                )
                await wait_for_idle(client, submitted.headers["Location"])

                original = AsyncPostgresSaver.adelete_thread

                async def fail_once(self: AsyncPostgresSaver, thread_id: str) -> None:
                    raise OSError("Synthetic cleanup failure")

                monkeypatch.setattr(AsyncPostgresSaver, "adelete_thread", fail_once)
                failed = await client.delete(url)
                assert failed.status_code == 500
                assert (await client.get(url)).status_code == 404
                async with open_postgres_checkpointer(checkpoint_conninfo) as saver:
                    assert [entry async for entry in saver.alist(None)]
                monkeypatch.setattr(AsyncPostgresSaver, "adelete_thread", original)
                assert (await client.delete(url)).status_code == 204
        async with open_postgres_checkpointer(checkpoint_conninfo) as saver:
            assert [entry async for entry in saver.alist(None)] == []

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_delete_waits_for_memory_analysis_and_clears_its_threads(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        entered, release = asyncio.Event(), asyncio.Event()
        calls = 0

        async def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            if request.url.path.endswith("/input_tokens"):
                return httpx2.Response(
                    200, json={"object": "response.input_tokens", "input_tokens": 1}
                )
            calls += 1
            if calls == 1:
                output = [call("request_memory_consolidation", "request", "{}")]
            elif calls == 2:
                output = [message(text="Synthetic consultant completion")]
            else:
                entered.set()
                await release.wait()
                output = [message(text='{"status":"complete"}')]
            return sse_response(EventStream(response_events(response_payload(output))))

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(
                BundleConfig("caliburn.bundles.interview", plugins=("interview",)),
                BundleConfig("caliburn.bundles.memory"),
            ),
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            url = f"/workspaces/{workspace}"
            body = {"turn_id": str(uuid4()), "input": "Synthetic input"}
            accepted = await client.post(url + "/agent/turns", json=body)
            await wait_for_idle(client, accepted.headers["Location"])
            deletion = None
            try:
                async with asyncio.timeout(10):
                    await entered.wait()
                    deletion = asyncio.create_task(client.delete(url))
                    while True:
                        rejected = await client.post(
                            url + "/agent/turns",
                            json=body,
                        )
                        if rejected.status_code not in (200, 202):
                            break
                        await asyncio.sleep(0.01)
                    assert rejected.status_code == 409
                    assert not deletion.done()
                    release.set()
                    assert (await deletion).status_code == 204
            finally:
                release.set()
                if deletion is not None:
                    await deletion
        async with open_postgres_checkpointer(checkpoint_conninfo) as saver:
            assert [entry async for entry in saver.alist(None)] == []

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
