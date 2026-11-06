"""HTTP admission and reads use offline OpenAI and real PostgreSQL."""

import asyncio
from pathlib import Path
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.http_support import api_client
from tests.reference_configuration import write_reference_configuration
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    response_events,
    response_payload,
    sse_response,
)


def test_missing_workspace_is_translated_at_host_boundary(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    def no_model(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("Missing Workspace must not call the model")

    async def run() -> None:
        async with api_client(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(no_model)
        ) as client:
            base = f"/workspaces/{uuid4()}/agent/turns"
            turn_id = str(uuid4())
            responses = (
                await client.post(base, json={"turn_id": turn_id, "input": "hello"}),
                await client.get(base),
                await client.get(f"{base}/{turn_id}/questions"),
            )
            for response in responses:
                assert response.status_code == 404, response.text
                assert response.json()["detail"]["code"] == "agent_turn_not_found"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_accepted_turn_is_durable_and_completed_resubmission_does_not_run_again(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        calls = 0

        async def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            return sse_response(EventStream(response_events(response_payload())))

        async with api_client(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            url = f"/workspaces/{workspace}/agent/turns"
            body = {"turn_id": str(uuid4()), "input": " synthetic input "}
            accepted = await client.post(url, json=body)
            assert accepted.status_code == 202, accepted.text
            saved = await client.get(accepted.headers["Location"])
            assert saved.status_code == 200
            assert saved.json()["input"] == body["input"]
            async with asyncio.timeout(5):
                while saved.json()["status"] == "running":
                    await asyncio.sleep(0.01)
                    saved = await client.get(accepted.headers["Location"])
            assert saved.json()["status"] == "completed"
            assert saved.json()["output"] == "Synthetic reply"
            duplicate = await client.post(url, json=body)
            assert duplicate.status_code == 200
            assert duplicate.json() == saved.json()
            assert calls == 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_history_keeps_each_saved_step_and_totals_usage_once(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    from tests.unit.modules.agent.offline_openai import message, reasoning

    async def run() -> None:
        replies = iter(
            [
                response_payload([message("commentary", "Working"), reasoning()]),
                response_payload(
                    [message("commentary", "More work"), message(text="Final only")]
                ),
            ]
        )

        def respond(request: httpx2.Request) -> httpx2.Response:
            return sse_response(EventStream(response_events(next(replies))))

        async with api_client(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            url = f"/workspaces/{workspace}/agent/turns"
            body = {"turn_id": str(uuid4()), "input": "one"}
            result = await client.post(url, json=body)
            assert result.status_code == 202
            location = result.headers["Location"]
            async with asyncio.timeout(5):
                while (await client.get(location)).json()["status"] == "running":
                    await asyncio.sleep(0.01)
            turns = await client.get(url)
            assert turns.status_code == 200
            assert len(turns.json()) == 1
            assert turns.json()[0]["output"] == "Final only"
            assert turns.json()[0]["usage"] == {
                "input_tokens": 26,
                "output_tokens": 16,
                "total_tokens": 42,
            }
            steps = await client.get(location + "/steps")
            assert steps.status_code == 200
            assert [step["model_step"] for step in steps.json()] == [1, 2]
            assert steps.json()[0]["messages"] == ["Working"]
            assert steps.json()[1]["messages"] == ["More work", "Final only"]
            assert "encrypted_content" not in steps.text
            assert "Synthetic instructions" not in steps.text

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_cold_interrupted_turn_resumes_without_appending_input(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        calls = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            return sse_response(
                EventStream(
                    response_events(response_payload([] if calls == 1 else None))
                )
            )

        transport = httpx2.MockTransport(respond)
        async with api_client(pg_engine, checkpoint_conninfo, transport) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            url = f"/workspaces/{workspace}/agent/turns"
            body = {"turn_id": str(uuid4()), "input": "original"}
            accepted = await client.post(url, json=body)
            assert accepted.status_code == 202
            location = accepted.headers["Location"]
            async with asyncio.timeout(5):
                while (await client.get(location)).json()["status"] == "running":
                    await asyncio.sleep(0.01)
        async with api_client(pg_engine, checkpoint_conninfo, transport) as client:
            cold = await client.get(location)
            assert cold.json()["status"] == "interrupted"
            assert (
                await client.post(url, json={"turn_id": str(uuid4()), "input": "skip"})
            ).status_code == 409
            assert (await client.post(url, json=body)).status_code == 200
            assert calls == 1
            resumed = await client.post(location + "/resume")
            assert resumed.status_code == 202, resumed.text
            async with asyncio.timeout(5):
                while (await client.get(location)).json()["status"] == "running":
                    await asyncio.sleep(0.01)
            completed = (await client.get(location)).json()
            assert completed["status"] == "completed"
            assert completed["input"] == "original"
            assert calls == 2
            assert (await client.post(location + "/resume")).status_code == 409

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_completed_sse_returns_terminal_status_and_missing_turn_is_404(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        calls = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            return sse_response(EventStream(response_events(response_payload())))

        async with api_client(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            url = f"/workspaces/{workspace}/agent/turns"
            accepted = await client.post(
                url, json={"turn_id": str(uuid4()), "input": "hello"}
            )
            location = accepted.headers["Location"]
            async with asyncio.timeout(5):
                while (await client.get(location)).json()["status"] == "running":
                    await asyncio.sleep(0.01)
                events = await client.get(location + "/events")
            assert events.status_code == 200
            assert events.headers["content-type"].startswith("text/event-stream")
            assert "event: status" in events.text
            assert '"completed"' in events.text
            assert "Synthetic instructions" not in events.text
            assert calls == 1
            missing = await client.get(url + f"/{uuid4()}/events")
            assert missing.status_code == 404

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_main_configuration_enables_the_same_http_lifespan(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import caliburn.host.agent_settings as agent_host
    from caliburn.host.entrypoint import create_app
    from tests.unit.modules.agent.offline_openai import offline_client

    async def run() -> None:
        calls = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            return sse_response(EventStream(response_events(response_payload())))

        config = tmp_path / "agent.json"
        config.write_text(
            '{"agent_id":"http-test","resume_version":"v1",'
            '"model":"offline-model","max_output_tokens":100}',
            encoding="utf-8",
        )
        monkeypatch.setenv(
            "CALIBURN_REBUILD_DATABASE_URL",
            pg_engine.url.render_as_string(hide_password=False),
        )
        monkeypatch.setenv("CALIBURN_REBUILD_AGENT_CONFIG", str(config))
        monkeypatch.setenv(
            "CALIBURN_REBUILD_REFERENCE_CONFIG",
            str(write_reference_configuration(tmp_path)),
        )
        monkeypatch.setenv(
            "CALIBURN_REBUILD_AGENT_CHECKPOINT_CONNINFO", checkpoint_conninfo
        )
        monkeypatch.setattr(
            agent_host,
            "AsyncOpenAI",
            lambda **kwargs: offline_client(httpx2.MockTransport(respond)),
        )
        async with open_postgres_checkpointer(checkpoint_conninfo, initialize=True):
            pass
        app = create_app()
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://testserver"
            ) as client,
        ):
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            result = await client.post(
                f"/workspaces/{workspace}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "hello"},
            )
            assert result.status_code == 202
            async with asyncio.timeout(5):
                while (await client.get(result.headers["Location"])).json()[
                    "status"
                ] == "running":
                    await asyncio.sleep(0.01)
            assert calls == 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_http_rejects_noncanonical_ids_and_unencodable_input(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        def no_model(request: httpx2.Request) -> httpx2.Response:
            raise AssertionError("Invalid input must not call the model")

        async with api_client(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(no_model)
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            url = f"/workspaces/{workspace}/agent/turns"
            response = await client.post(
                url, json={"turn_id": uuid4().hex, "input": "hello"}
            )
            assert response.status_code == 422
            response = await client.post(
                url,
                content='{"turn_id":"00000000-0000-0000-0000-000000000001","input":"\\ud800"}',
                headers={"content-type": "application/json"},
            )
            assert response.status_code == 422
            assert (
                await client.get(
                    f"/workspaces/{workspace.replace('-', '')}/agent/turns"
                )
            ).status_code == 422
            assert (await client.get(url)).json() == []

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
