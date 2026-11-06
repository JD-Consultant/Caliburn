"""獨立壓縮 Bundle 沿原生 Core／PG Checkpoint 續作與取消。"""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any, cast
from uuid import uuid4

import httpx2
import pytest
from langchain_core.tools import StructuredTool
from langgraph.runtime import Runtime
from openai.types.responses import CompactedResponse
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.bundles.context.native_plugin import create_native_plugin
from caliburn.bundles.context.services import COMPACTION_CLIENT
from caliburn.modules.agent.agent import Agent, AgentExecutionError
from caliburn.modules.agent.application.turn_history import compaction_views
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginHook,
    PluginStep,
)
from caliburn.modules.agent.state import AgentLimitError, AgentState
from tests.integration.agent.stream_support import consume
from tests.unit.bundles.context.support import compacted_payload
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    call,
    message,
    offline_client,
    reasoning,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    async def read_alpha(item: str) -> str:
        return f"read {item}"

    tools = AgentPlugin(
        "reading",
        tools=(
            StructuredTool.from_function(coroutine=read_alpha, description="讀取項目"),
        ),
    )
    if "fail_after" not in config:
        return AgentBundle((tools,))

    def fail_after(inner: PluginHook[AgentState]) -> PluginHook[AgentState]:
        async def invoke(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            result = await inner(state, runtime=runtime)
            if config["fail_after"]:
                raise RuntimeError("failure after compact result before adoption")
            return result

        return invoke

    plugin = create_native_plugin(threshold_tokens=100)
    step, *remaining = plugin.before_model_step

    async def restore_window(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        return {
            "model_request": {
                **state["model_request"],
                "input": cast(ResponseInputParam, compacted_payload()["output"]),
            }
        }

    return AgentBundle(
        (
            replace(
                plugin,
                before_model_step=(replace(step, wrappers=(fail_after,)), *remaining),
            ),
            tools,
            *(
                (
                    AgentPlugin(
                        "unchanged_window",
                        after_model_step=(PluginStep("restore", restore_window),),
                    ),
                )
                if config.get("unchanged_window")
                else ()
            ),
        )
    )


@asynccontextmanager
async def open_compaction_agent(
    conninfo: str,
    transport: httpx2.MockTransport,
    *,
    initialize: bool,
    fail_after: bool | None = None,
    unchanged_window: bool = False,
) -> AsyncIterator[Agent]:
    bundles = (
        (
            BundleConfig(
                "caliburn.bundles.context",
                {"threshold_tokens": 100},
                plugins=("native_compaction",),
            ),
            BundleConfig(__name__),
        )
        if fail_after is None
        else (
            BundleConfig(
                __name__,
                {"fail_after": fail_after, "unchanged_window": unchanged_window},
            ),
        )
    )
    async with (
        open_postgres_checkpointer(conninfo, initialize=initialize) as saver,
        offline_client(transport) as client,
        open_agent(
            agent_id="compaction-test",
            resume_version="v1",
            client=client,
            model_settings={**MODEL_REQUEST, "instructions": "保留工作事實與引用。"},
            bundles=bundles,
            checkpointer=saver,
            external_services=(COMPACTION_CLIENT.bind(client),),
        ) as agent,
    ):
        yield agent


def test_each_model_send_counts_the_current_window_after_tool_calls(
    checkpoint_conninfo: str,
) -> None:
    paths: list[str] = []
    counts: list[dict[str, Any]] = []
    compacts: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    workspace, turn = uuid4(), uuid4()
    payload = compacted_payload()

    def respond(request: httpx2.Request) -> httpx2.Response:
        paths.append(request.url.path)
        body = request_body(request)
        if request.url.path.endswith("input_tokens"):
            counts.append(body)
            return httpx2.Response(
                200,
                json={
                    "object": "response.input_tokens",
                    "input_tokens": 100 if len(counts) == 2 else 20,
                },
            )
        if request.url.path.endswith("compact"):
            compacts.append(body)
            return httpx2.Response(200, json=payload)
        models.append(body)
        output = (
            [reasoning(), call(call_id=f"read_{len(models)}")]
            if len(models) <= 2
            else None
        )
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with open_compaction_agent(
            checkpoint_conninfo, httpx2.MockTransport(respond), initialize=True
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=workspace, turn_id=turn, input="原始本輪輸入"
                )
            )
            saved = await agent.aget_state(workspace_id=workspace)
            assert saved.values["turn_input"] == "原始本輪輸入"
            assert saved.values["model_response"].output_text == "Synthetic reply"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert paths == [
        "/v1/responses/input_tokens",
        "/v1/responses",
        "/v1/responses/input_tokens",
        "/v1/responses/compact",
        "/v1/responses/input_tokens",
        "/v1/responses",
        "/v1/responses/input_tokens",
        "/v1/responses",
    ]
    for counted, sent in zip((counts[0], counts[2], counts[3]), models, strict=True):
        for field in ("input", "tools", "instructions"):
            assert counted[field] == sent[field]
    assert counts[1]["input"] == compacts[0]["input"]
    assert [item.get("type") for item in compacts[0]["input"][-3:]] == [
        "reasoning",
        "function_call",
        "function_call_output",
    ]
    assert models[1]["input"] == payload["output"]
    assert models[2]["input"][:2] == payload["output"]
    assert models[2]["input"][-1]["output"] == "read alpha"
    for counted, call_id in ((counts[1], "read_1"), (counts[3], "read_2")):
        call_item, output_item = counted["input"][-2:]
        assert call_item["call_id"] == output_item["call_id"] == call_id
        assert output_item["output"] == "read alpha"
    assert all(model["tools"] == models[0]["tools"] for model in models)
    assert all(model["instructions"] == "保留工作事實與引用。" for model in models)


def test_saved_compaction_result_survives_failure_before_adoption_and_cold_resume(
    checkpoint_conninfo: str,
) -> None:
    paths: list[str] = []
    models: list[dict[str, Any]] = []
    workspace, turn = uuid4(), uuid4()
    payload = compacted_payload()

    def respond(request: httpx2.Request) -> httpx2.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("input_tokens"):
            return httpx2.Response(
                200,
                json={
                    "object": "response.input_tokens",
                    "input_tokens": 20
                    if request_body(request)["input"] == payload["output"]
                    else 100,
                },
            )
        if request.url.path.endswith("compact"):
            return httpx2.Response(200, json=payload)
        models.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with open_compaction_agent(
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            initialize=True,
            fail_after=True,
        ) as agent:
            with pytest.raises(RuntimeError, match="before adoption"):
                await consume(
                    agent.astream(
                        workspace_id=workspace, turn_id=turn, input="original"
                    )
                )
            saved = await agent.aget_state(workspace_id=workspace)
            assert saved.values["model_request"]["input"] == [
                {"role": "user", "content": "original"}
            ]
        async with open_compaction_agent(
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            initialize=False,
            fail_after=False,
        ) as agent:
            await consume(agent.aresume(workspace_id=workspace, turn_id=turn))
            saved = await agent.aget_state(workspace_id=workspace)
            response = saved.values["compaction_response"]
            assert isinstance(response, CompactedResponse)
            assert (
                response.model_dump(mode="json", exclude_unset=True, warnings=False)
                == payload
            )
            history = [
                snapshot
                async for snapshot in agent.aget_state_history(workspace_id=workspace)
            ]
            (observed,) = compaction_views(history, turn)
            assert observed.response_id == response.id
            assert observed.model_step == 1
            assert observed.usage is not None
            assert observed.usage.total_tokens == response.usage.total_tokens

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert paths == [
        "/v1/responses/input_tokens",
        "/v1/responses/compact",
        "/v1/responses/input_tokens",
        "/v1/responses",
    ]
    assert models[0]["input"] == payload["output"]


def test_compaction_failure_preserves_input_and_can_resume(
    checkpoint_conninfo: str,
) -> None:
    attempts = 0
    models: list[dict[str, Any]] = []
    workspace, turn = uuid4(), uuid4()

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        if request.url.path.endswith("input_tokens"):
            return httpx2.Response(
                200,
                json={
                    "object": "response.input_tokens",
                    "input_tokens": 20
                    if request_body(request)["input"] == compacted_payload()["output"]
                    else 100,
                },
            )
        if request.url.path.endswith("compact"):
            attempts += 1
            if attempts == 1:
                return httpx2.Response(
                    400,
                    json={
                        "error": {
                            "message": "synthetic outage",
                            "type": "invalid_request_error",
                        }
                    },
                )
            return httpx2.Response(200, json=compacted_payload())
        models.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with open_compaction_agent(
            checkpoint_conninfo, httpx2.MockTransport(respond), initialize=True
        ) as agent:
            with pytest.raises(RuntimeError, match="Model provider compaction failed"):
                await consume(
                    agent.astream(
                        workspace_id=workspace, turn_id=turn, input="original"
                    )
                )
            saved = await agent.aget_state(workspace_id=workspace)
            assert saved.values["model_request"]["input"] == [
                {"role": "user", "content": "original"}
            ]
            assert any(task.error for task in saved.tasks)
            assert "synthetic outage" not in repr([task.error for task in saved.tasks])
            assert models == []
        async with open_compaction_agent(
            checkpoint_conninfo, httpx2.MockTransport(respond), initialize=False
        ) as agent:
            await consume(agent.aresume(workspace_id=workspace, turn_id=turn))

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert attempts == 2 and len(models) == 1
    assert models[0]["input"] == compacted_payload()["output"]


def test_cancel_inflight_compaction_does_not_adopt_a_window(
    checkpoint_conninfo: str,
) -> None:
    workspace, turn = uuid4(), uuid4()
    paths: list[str] = []

    async def run() -> None:
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def respond(request: httpx2.Request) -> httpx2.Response:
            paths.append(request.url.path)
            if request.url.path.endswith("input_tokens"):
                return httpx2.Response(
                    200, json={"object": "response.input_tokens", "input_tokens": 100}
                )
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
            raise AssertionError("Unreachable compaction result")

        async with open_compaction_agent(
            checkpoint_conninfo, httpx2.MockTransport(respond), initialize=True
        ) as agent:
            invocation = asyncio.create_task(
                consume(
                    agent.astream(
                        workspace_id=workspace, turn_id=turn, input="original"
                    )
                )
            )
            await asyncio.wait_for(started.wait(), timeout=5)
            invocation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await invocation
            assert cancelled.is_set()
            await agent.acancel_turn(workspace_id=workspace, turn_id=turn)
            saved = await agent.aget_state(workspace_id=workspace)
            assert saved.values["model_request"]["input"] == [
                {"role": "user", "content": "original"}
            ]
            assert saved.values["cancel_status"] == "completed"
            with pytest.raises(AgentExecutionError):
                await consume(agent.aresume(workspace_id=workspace, turn_id=turn))

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert paths == ["/v1/responses/input_tokens", "/v1/responses/compact"]


def test_compacted_window_over_limit_stops_without_recompacting_on_resume(
    checkpoint_conninfo: str,
) -> None:
    workspace, turn = uuid4(), uuid4()
    paths: list[str] = []
    payload = compacted_payload()

    def respond(request: httpx2.Request) -> httpx2.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 100}
            )
        if request.url.path.endswith("compact"):
            return httpx2.Response(200, json=payload)
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with open_compaction_agent(
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            initialize=True,
            fail_after=False,
        ) as agent:
            with pytest.raises(AgentLimitError, match="Compacted window"):
                await consume(
                    agent.astream(
                        workspace_id=workspace, turn_id=turn, input="original"
                    )
                )
            saved = await agent.aget_state(workspace_id=workspace)
            assert saved.values["model_request"]["input"] == payload["output"]
            response = saved.values["compaction_response"]
            assert isinstance(response, CompactedResponse)
            assert (
                response.model_dump(mode="json", exclude_unset=True, warnings=False)
                == payload
            )
        async with open_compaction_agent(
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            initialize=False,
            fail_after=False,
        ) as agent:
            with pytest.raises(AgentLimitError, match="Compacted window"):
                await consume(agent.aresume(workspace_id=workspace, turn_id=turn))

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert paths == [
        "/v1/responses/input_tokens",
        "/v1/responses/compact",
        "/v1/responses/input_tokens",
    ]


def test_saved_window_survives_recount_failure_without_repeating_compaction(
    checkpoint_conninfo: str,
) -> None:
    workspace, turn = uuid4(), uuid4()
    paths: list[str] = []
    recounts = 0
    payload = compacted_payload()

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal recounts
        paths.append(request.url.path)
        body = request_body(request)
        if request.url.path.endswith("input_tokens"):
            if body["input"] == payload["output"]:
                recounts += 1
                if recounts == 1:
                    return httpx2.Response(
                        400,
                        json={
                            "error": {
                                "message": "synthetic recount failure",
                                "type": "invalid_request_error",
                            }
                        },
                    )
                tokens = 20
            else:
                tokens = 100
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": tokens}
            )
        if request.url.path.endswith("compact"):
            return httpx2.Response(200, json=payload)
        assert body["input"] == payload["output"]
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with open_compaction_agent(
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            initialize=True,
            fail_after=False,
        ) as agent:
            with pytest.raises(
                RuntimeError, match="Model provider input token count failed"
            ):
                await consume(
                    agent.astream(
                        workspace_id=workspace, turn_id=turn, input="original"
                    )
                )
            saved = await agent.aget_state(workspace_id=workspace)
            assert saved.values["model_request"]["input"] == payload["output"]
            assert any(task.error for task in saved.tasks)
            assert "synthetic recount failure" not in repr(
                [task.error for task in saved.tasks]
            )
        async with open_compaction_agent(
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            initialize=False,
            fail_after=False,
        ) as agent:
            await consume(agent.aresume(workspace_id=workspace, turn_id=turn))

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert paths == [
        "/v1/responses/input_tokens",
        "/v1/responses/compact",
        "/v1/responses/input_tokens",
        "/v1/responses/input_tokens",
        "/v1/responses",
    ]


def test_unchanged_window_after_a_step_does_not_compact_again(
    checkpoint_conninfo: str,
) -> None:
    workspace, turn = uuid4(), uuid4()
    counts = 0
    compacts = 0
    models = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal counts, compacts, models
        if request.url.path.endswith("input_tokens"):
            counts += 1
            return httpx2.Response(
                200,
                json={
                    "object": "response.input_tokens",
                    "input_tokens": 20 if counts == 2 else 100,
                },
            )
        if request.url.path.endswith("compact"):
            compacts += 1
            return httpx2.Response(200, json=compacted_payload())
        models += 1
        output = response_payload([message("commentary")])
        return sse_response(EventStream(response_events(output)))

    async def run() -> None:
        async with open_compaction_agent(
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            initialize=True,
            fail_after=False,
            unchanged_window=True,
        ) as agent:
            with pytest.raises(AgentLimitError, match="Compacted window"):
                await consume(
                    agent.astream(
                        workspace_id=workspace, turn_id=turn, input="original"
                    )
                )
            saved = await agent.aget_state(workspace_id=workspace)
            assert (
                saved.values["model_request"]["input"] == compacted_payload()["output"]
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert (counts, compacts, models) == (3, 1, 1)


def test_new_tool_items_allow_compaction_again_and_new_turn_resets_the_boundary(
    checkpoint_conninfo: str,
) -> None:
    workspace = uuid4()
    counts: list[dict[str, Any]] = []
    compacts: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    payload = compacted_payload()

    def respond(request: httpx2.Request) -> httpx2.Response:
        body = request_body(request)
        if request.url.path.endswith("input_tokens"):
            counts.append(body)
            return httpx2.Response(
                200,
                json={
                    "object": "response.input_tokens",
                    "input_tokens": 20 if body["input"] == payload["output"] else 100,
                },
            )
        if request.url.path.endswith("compact"):
            compacts.append(body)
            return httpx2.Response(200, json=payload)
        models.append(body)
        output = [reasoning(), call()] if len(models) == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with open_compaction_agent(
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            initialize=True,
            fail_after=False,
        ) as agent:
            for text in ("first turn", "new turn"):
                await consume(
                    agent.astream(workspace_id=workspace, turn_id=uuid4(), input=text)
                )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(compacts) == 3 and len(models) == 3 and len(counts) == 6
    assert compacts[1]["input"][:2] == payload["output"]
    assert [item["type"] for item in compacts[1]["input"][-3:]] == [
        "reasoning",
        "function_call",
        "function_call_output",
    ]
    assert compacts[2]["input"] == [{"role": "user", "content": "new turn"}]
    assert all(model["input"] == payload["output"] for model in models)
