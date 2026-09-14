from __future__ import annotations

from collections.abc import AsyncIterable
from importlib.metadata import version
from typing import Annotated, Any

import pytest
from deepagents.backends import StateBackend
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.skills import SkillsMiddleware
from fastapi import FastAPI, Header
from fastapi.sse import EventSourceResponse, ServerSentEvent
from httpx import ASGITransport, AsyncClient
from langchain_openrouter import ChatOpenRouter
from pydantic import BaseModel

import app.app_factory as app_factory
from app.api.problems import INVALID_REQUEST, problem_response


class _SnapshotEvent(BaseModel):
    revision: int
    status: str


def _build_sse_app() -> FastAPI:
    app = FastAPI()

    @app.get("/events", response_class=EventSourceResponse)
    async def events(
        last_event_id: Annotated[int | None, Header()] = None,
    ) -> AsyncIterable[ServerSentEvent]:
        next_event_id = (last_event_id or 0) + 1
        yield ServerSentEvent(comment="keepalive")
        yield ServerSentEvent(
            data=_SnapshotEvent(revision=next_event_id, status="completed"),
            event="snapshot",
            id=str(next_event_id),
            retry=1_500,
        )

    @app.get("/problem")
    async def problem():
        return problem_response(
            type_uri=INVALID_REQUEST,
            title="Invalid request",
            status=422,
        )

    return app


@pytest.mark.asyncio
async def test_native_sse_serializes_typed_event_fields_and_resume_header() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_build_sse_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/events", headers={"Last-Event-ID": "7"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.text.splitlines() == [
        ": keepalive",
        "",
        "event: snapshot",
        'data: {"revision":8,"status":"completed"}',
        "id: 8",
        "retry: 1500",
        "",
    ]


@pytest.mark.asyncio
async def test_native_sse_disconnect_listener_completes_cleanly() -> None:
    response = EventSourceResponse(content=iter(()))
    received: list[dict[str, Any]] = []

    async def receive() -> dict[str, str]:
        message = {"type": "http.disconnect"}
        received.append(message)
        return message

    await response.listen_for_disconnect(receive)

    assert received == [{"type": "http.disconnect"}]


@pytest.mark.asyncio
async def test_fastapi_upgrade_preserves_health_and_problem_details(monkeypatch) -> None:
    class _UnavailableDatabase:
        async def __aenter__(self):
            raise OSError("database unavailable")

        async def __aexit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(
        app_factory,
        "AsyncSessionLocal",
        lambda: _UnavailableDatabase(),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app_factory.configure(FastAPI())),
        base_url="http://test",
    ) as client:
        health = await client.get("/healthz")
    async with AsyncClient(
        transport=ASGITransport(app=_build_sse_app()),
        base_url="http://test",
    ) as client:
        problem = await client.get("/problem")

    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert problem.status_code == 422
    assert problem.headers["content-type"] == "application/problem+json"
    assert problem.json()["type"] == INVALID_REQUEST


def test_runtime_framework_versions_are_exactly_pinned() -> None:
    assert {
        package: version(package)
        for package in (
            "fastapi",
            "httpx",
            "langchain",
            "langgraph",
            "langgraph-checkpoint-postgres",
            "langchain-openrouter",
            "deepagents",
        )
    } == {
        "fastapi": "0.141.1",
        "httpx": "0.28.1",
        "langchain": "1.4.0",
        "langgraph": "1.2.11",
        "langgraph-checkpoint-postgres": "3.1.2",
        "langchain-openrouter": "0.2.8",
        "deepagents": "0.7.13",
    }


def test_beta_integrations_have_a_narrow_non_executing_surface() -> None:
    backend = StateBackend()
    skill_reader = FilesystemMiddleware(
        backend=backend,
        tools=["read_file"],
        system_prompt=None,
    )
    skills = SkillsMiddleware(
        backend=backend,
        sources=[("/skills", "Caliburn")],
        system_prompt=(
            "{skills_locations}\n{skills_load_warnings}\n{skills_list}\n"
            "Load a selected skill only with the read_file tool."
        ),
    )
    model = ChatOpenRouter(
        model="openai/test-model",
        api_key="test-only",
        temperature=0,
        max_retries=0,
    )

    exposed_tools = {tool.name for tool in skill_reader.tools}
    exposed_tools.update(tool.name for tool in getattr(skills, "tools", ()))

    assert exposed_tools == {"read_file"}
    assert exposed_tools.isdisjoint(
        {"execute", "write_file", "edit_file", "delete", "task", "write_todos"}
    )
    assert model.model == "openai/test-model"
    assert model.temperature == 0
    assert callable(model.with_structured_output)
