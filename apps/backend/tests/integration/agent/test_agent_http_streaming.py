"""SSE 斷線、終局及關閉順序經正式 HTTP 與真 PG 驗證。"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx2
import pytest
from fastapi import FastAPI
from sqlalchemy import Engine
from starlette.types import Message, Scope

from tests.integration.agent.http_support import api_app
from tests.unit.modules.agent.offline_openai import (
    message,
    reasoning,
    response_events,
    response_payload,
    sse_response,
)


class GatedModelStream(httpx2.AsyncByteStream):
    """只在 OpenAI 傳輸邊界控制進度，不替換 Agent 或保存規則。"""

    def __init__(self, *, chunks: int = 1) -> None:
        self.release = asyncio.Event()
        self.entered = asyncio.Event()
        self.closed = asyncio.Event()
        self.chunks = chunks

    async def __aiter__(self) -> AsyncIterator[bytes]:
        text = "Synthetic reply" if self.chunks == 1 else "x" * self.chunks
        payload = response_payload([reasoning(), message(text=text)])
        first, last = response_events(payload)
        yield self.encode(first)
        self.entered.set()
        await self.release.wait()
        sequence = 1
        for index, item in enumerate([reasoning(), message(text="")]):
            yield self.encode(
                {
                    "type": "response.output_item.added",
                    "sequence_number": sequence,
                    "output_index": index,
                    "item": item,
                }
            )
            sequence += 1
        yield self.encode(
            {
                "type": "response.content_part.added",
                "sequence_number": sequence,
                "output_index": 1,
                "item_id": "msg_final_answer",
                "content_index": 0,
                "part": {"type": "output_text", "text": "", "annotations": []},
            }
        )
        sequence += 1
        for _ in range(self.chunks):
            yield self.encode(
                {
                    "type": "response.output_text.delta",
                    "sequence_number": sequence,
                    "output_index": 1,
                    "item_id": "msg_final_answer",
                    "content_index": 0,
                    "delta": "Synthetic reply" if self.chunks == 1 else "x",
                    "logprobs": [],
                }
            )
            sequence += 1
        yield self.encode({**last, "sequence_number": sequence})

    @staticmethod
    def encode(event: dict[str, object]) -> bytes:
        return ("data: " + json.dumps(event) + "\n\n").encode()

    async def aclose(self) -> None:
        self.closed.set()


@asynccontextmanager
async def release_model_on_exit(model: GatedModelStream) -> AsyncIterator[None]:
    """測例失敗仍先放行外部替身，避免正式 drain 等不到測試 gate。"""
    try:
        yield
    finally:
        model.release.set()


class SseConnection:
    """ASGI HTTP 接收端可明確斷線及暫停讀取，保留真正串流時序。"""

    def __init__(self, app: FastAPI, location: str) -> None:
        self.app = app
        self.path = urlsplit(location).path
        self.disconnected = asyncio.Event()
        self.first_status = asyncio.Event()
        self.allow_body = asyncio.Event()
        self.allow_body.set()
        self.received: list[bytes] = []
        self.status: int | None = None
        self._request_received = False

    async def receive(self) -> Message:
        if not self._request_received:
            self._request_received = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await self.disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(self, event: Message) -> None:
        if event["type"] == "http.response.start":
            self.status = event["status"]
        elif event["type"] == "http.response.body":
            await self.allow_body.wait()
            body = event.get("body", b"")
            self.received.append(body)
            if b"event: status" in body:
                self.first_status.set()

    async def run(self) -> None:
        scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "scheme": "http",
            "method": "GET",
            "path": self.path,
            "raw_path": self.path.encode(),
            "root_path": "",
            "query_string": b"",
            "headers": [(b"host", b"testserver"), (b"accept", b"text/event-stream")],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
        await self.app(scope, self.receive, self.send)

    def events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for frame in (
            b"".join(self.received).decode().replace("\r\n", "\n").split("\n\n")
        ):
            kind = None
            data = None
            for line in frame.splitlines():
                if line.startswith("event: "):
                    kind = line[7:]
                if line.startswith("data: "):
                    data = json.loads(line[6:])
            if kind is not None:
                events.append({"event": kind, "data": data})
        return events


@asynccontextmanager
async def stream_connection(
    app: FastAPI, location: str
) -> AsyncIterator[tuple[SseConnection, asyncio.Task[None]]]:
    connection = SseConnection(app, location)
    task = asyncio.create_task(connection.run())
    try:
        async with asyncio.timeout(10):
            await connection.first_status.wait()
        yield connection, task
    finally:
        connection.allow_body.set()
        connection.disconnected.set()
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def submit(client: httpx2.AsyncClient) -> str:
    workspace = await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
    assert workspace.status_code == 201, workspace.text
    response = await client.post(
        f"/workspaces/{workspace.json()['workspace_id']}/agent/turns",
        json={"turn_id": str(uuid4()), "input": "Synthetic input"},
    )
    assert response.status_code == 202, response.text
    return response.headers["Location"]


def test_live_sse_keeps_terminal_status_and_exposes_only_public_fields(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        model = GatedModelStream()
        calls = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            return sse_response(model)

        async with (
            api_app(
                pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
            ) as app,
            release_model_on_exit(model),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://testserver"
            ) as client,
        ):
            location = await submit(client)
            async with stream_connection(app, location + "/events") as (
                connection,
                task,
            ):
                assert connection.status == 200
                assert connection.events()[0]["data"]["status"] == "running"
                model.release.set()
                async with asyncio.timeout(10):
                    await task
                events = connection.events()
                assert events[-1]["event"] == "status"
                assert events[-1]["data"]["status"] == "completed"
                assert events[-1]["data"]["output"] == "Synthetic reply"
                assert {
                    "event": "text_delta",
                    "data": {"model_step": 1, "delta": "Synthetic reply"},
                } in events
                raw = b"".join(connection.received).decode()
                for secret in (
                    "encrypted_content",
                    "synthetic-opaque-content",
                    "Synthetic instructions",
                    "future_response_field",
                    "model_request",
                ):
                    assert secret not in raw
                assert calls == 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_sse_disconnect_releases_subscription_without_stopping_turn(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        model = GatedModelStream()
        calls = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            return sse_response(model)

        async with (
            api_app(
                pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
            ) as app,
            release_model_on_exit(model),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://testserver"
            ) as client,
        ):
            location = await submit(client)
            for _ in range(3):
                async with stream_connection(app, location + "/events") as (
                    connection,
                    task,
                ):
                    assert connection.events()[0]["data"]["status"] == "running"
                    connection.disconnected.set()
                    async with asyncio.timeout(5):
                        await task
                assert not model.closed.is_set()
                assert (await client.get(location)).json()["status"] == "running"
            async with stream_connection(app, location + "/events") as (
                connection,
                task,
            ):
                model.release.set()
                async with asyncio.timeout(10):
                    await task
                assert connection.events()[-1]["data"]["status"] == "completed"
            assert calls == 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_slow_sse_reader_is_told_to_resync_without_blocking_completion(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        model = GatedModelStream(chunks=300)
        transport = httpx2.MockTransport(lambda _: sse_response(model))
        async with (
            api_app(pg_engine, checkpoint_conninfo, transport) as app,
            release_model_on_exit(model),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://testserver"
            ) as client,
        ):
            location = await submit(client)
            async with stream_connection(app, location + "/events") as (
                connection,
                task,
            ):
                connection.allow_body.clear()
                model.release.set()
                async with asyncio.timeout(10):
                    await model.closed.wait()
                    while (await client.get(location)).json()["status"] == "running":
                        await asyncio.sleep(0.01)
                saved = (await client.get(location)).json()
                assert saved["status"] == "completed"
                assert saved["output"] == "x" * 300
                connection.allow_body.set()
                async with asyncio.timeout(10):
                    await task
                assert any(
                    event["event"] == "resync_required" for event in connection.events()
                )
                assert (
                    len(
                        [
                            event
                            for event in connection.events()
                            if event["event"] == "text_delta"
                        ]
                    )
                    < 300
                )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_lifespan_waits_for_owned_turn_before_closing_dependencies(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        baseline = asyncio.all_tasks()
        closed: list[str] = []

        class ObservedStream(GatedModelStream):
            async def aclose(self) -> None:
                closed.append("stream")
                await super().aclose()

        model = ObservedStream()

        class ObservedTransport(httpx2.MockTransport):
            async def aclose(self) -> None:
                closed.append("client")
                await super().aclose()

        transport = ObservedTransport(lambda _: sse_response(model))
        async with AsyncExitStack() as resources:
            app = await resources.enter_async_context(
                api_app(pg_engine, checkpoint_conninfo, transport)
            )
            try:
                async with httpx2.AsyncClient(
                    transport=httpx2.ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    location = await submit(client)
                    async with asyncio.timeout(5):
                        await model.entered.wait()
                    assert (await client.get(location)).json()["status"] == "running"
                    shutdown = asyncio.create_task(resources.aclose())
                    try:
                        # 只等待關閉結果，不取消關閉工作；模型 gate 仍阻擋自然完成。
                        with pytest.raises(TimeoutError):
                            async with asyncio.timeout(0.1):
                                await asyncio.shield(shutdown)
                        assert not model.closed.is_set()
                        assert closed == []
                    finally:
                        model.release.set()
                        async with asyncio.timeout(10):
                            await shutdown
            finally:
                model.release.set()
        assert closed == ["stream", "client"]
        assert not [
            task
            for task in asyncio.all_tasks()
            if task not in baseline and not task.done()
        ]

        def unexpected_model_call(request: httpx2.Request) -> httpx2.Response:
            raise AssertionError("Cold read must not start the model")

        async with (
            api_app(
                pg_engine,
                checkpoint_conninfo,
                httpx2.MockTransport(unexpected_model_call),
            ) as app,
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://testserver"
            ) as client,
        ):
            saved = await client.get(location)
            assert saved.status_code == 200
            assert saved.json()["status"] == "completed"
            assert saved.json()["input"] == "Synthetic input"
            assert saved.json()["output"] == "Synthetic reply"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
