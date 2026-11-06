"""公開 Agent 的共享資源、每輪選版及取消清理。"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import cast
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import StateSnapshot
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.agent import Agent
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.openai.call_model import ModelResponseError
from caliburn.modules.agent.state import request_items
from tests.unit.modules.agent.bundle_fixtures.host_services import EVENTS
from tests.unit.modules.agent.bundle_fixtures.snapshots import (
    SNAPSHOT_SOURCE,
    SnapshotSource,
)
from tests.unit.modules.agent.offline_openai import (
    INITIAL,
    MODEL_REQUEST,
    TEST_WORKSPACE_ID,
    EventStream,
    call,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)

SNAPSHOTS = "tests.unit.modules.agent.bundle_fixtures.snapshots"


async def complete_turn(
    agent: Agent, workspace_id: UUID = TEST_WORKSPACE_ID
) -> StateSnapshot:
    async for _ in agent.astream(
        turn_id=uuid4(),
        workspace_id=workspace_id,
        input=cast(ResponseInputParam, INITIAL),
    ):
        pass
    return await agent.aget_state(workspace_id=workspace_id)


def test_bundle_resources_survive_multiple_turns_then_close_without_client() -> None:
    events: list[str] = []
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        assert events == ["enter"]
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="lifecycle",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                external_services=(EVENTS.bind(events),),
                checkpointer=InMemorySaver(),
                bundles=[
                    BundleConfig("tests.unit.modules.agent.bundle_fixtures.lifecycle")
                ],
            ) as agent:
                await complete_turn(agent)
                await complete_turn(agent)
                assert events == ["enter"]
            assert events == ["enter", "exit"]
            assert not client.is_closed()

    asyncio.run(run())
    assert len(sent) == 2
    assert all(
        body["instructions"] == f"workspace={TEST_WORKSPACE_ID.int}" for body in sent
    )


def test_fixed_snapshot_is_reused_for_all_steps_and_next_turn_reads_new_version() -> (
    None
):
    source = SnapshotSource({TEST_WORKSPACE_ID: "v1"})
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        if len(sent) == 1:
            source.published[TEST_WORKSPACE_ID] = "v2"
            output = [call()]
        else:
            output = None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="snapshots",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                external_services=(SNAPSHOT_SOURCE.bind(source),),
                checkpointer=InMemorySaver(),
                bundles=[BundleConfig(SNAPSHOTS, {"tools": True})],
            ) as agent:
                assert source.reads == []
                for expected_steps, expected_version in ((2, "v1"), (1, "v2")):
                    result = (await complete_turn(agent)).values
                    assert result["model_step"] == expected_steps
                    assert result["snapshot_version"] == expected_version
                    memory = [
                        item
                        for item in request_items(result["model_request"])
                        if isinstance(item, dict) and item.get("role") == "developer"
                    ]
                    assert len(memory) == 1
                    assert str(memory[0].get("content")).startswith("snapshot:")
                assert source.events == ["snapshot:enter"]

    asyncio.run(run())
    assert source.reads == [TEST_WORKSPACE_ID, TEST_WORKSPACE_ID]
    assert source.events == ["snapshot:enter", "snapshot:exit"]
    assert [body["instructions"] for body in sent] == [
        "snapshot:static\n\nsnapshot:v1:items=1",
        "snapshot:static\n\nsnapshot:v1:items=3",
        "snapshot:static\n\nsnapshot:v2:items=1",
    ]
    assert [len(body["input"]) for body in sent] == [2, 4, 2]
    assert sent[1]["input"][-1]["output"] == "snapshot:v1:items=1/alpha"
    assert [item["type"] for item in sent[1]["input"][2:]] == [
        "function_call",
        "function_call_output",
    ]


def test_setup_failure_closes_partial_then_previous_bundles_in_reverse() -> None:
    source = SnapshotSource({TEST_WORKSPACE_ID: "v1"})

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("no model request"))
        ) as client:
            with pytest.raises(RuntimeError, match="setup failed"):
                async with open_agent(
                    agent_id="snapshots",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    external_services=(SNAPSHOT_SOURCE.bind(source),),
                    checkpointer=InMemorySaver(),
                    bundles=[
                        BundleConfig(
                            SNAPSHOTS, {"label": label, "fail_setup": label == "third"}
                        )
                        for label in ("first", "second", "third")
                    ],
                ):
                    pytest.fail("setup should fail before yielding")
            assert not client.is_closed()

    asyncio.run(run())
    assert source.reads == []
    assert source.events == [
        "first:enter",
        "second:enter",
        "third:enter",
        "third:exit",
        "second:exit",
        "first:exit",
    ]


def test_interleaved_turns_pin_separate_workspace_snapshots() -> None:
    async def run() -> None:
        source = SnapshotSource({UUID(int=1): "left-v1", UUID(int=2): "right-v1"})
        both_requested = asyncio.Event()
        requests = []

        async def respond(request: httpx2.Request) -> httpx2.Response:
            body = request_body(request)
            requests.append(body)
            if len(body["input"]) == 2:
                if len(requests) == 2:
                    both_requested.set()
                await both_requested.wait()
                source.published.update(
                    {UUID(int=1): "left-v2", UUID(int=2): "right-v2"}
                )
                output = [call()]
            else:
                output = None
            return sse_response(EventStream(response_events(response_payload(output))))

        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="snapshots",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                external_services=(SNAPSHOT_SOURCE.bind(source),),
                checkpointer=InMemorySaver(),
                bundles=[BundleConfig(SNAPSHOTS, {"tools": True})],
            ) as agent:
                results = await asyncio.wait_for(
                    asyncio.gather(
                        complete_turn(agent, UUID(int=1)),
                        complete_turn(agent, UUID(int=2)),
                    ),
                    timeout=5,
                )
                assert [result.values["model_step"] for result in results] == [2, 2]
                assert source.events == ["snapshot:enter"]
        assert source.reads == [UUID(int=1), UUID(int=2)]
        subsequent = [body for body in requests if len(body["input"]) == 4]
        assert {
            (body["input"][0]["content"], body["input"][-1]["output"])
            for body in subsequent
        } == {
            ("snapshot:left-v1:items=3", "snapshot:left-v1:items=1/alpha"),
            ("snapshot:right-v1:items=3", "snapshot:right-v1:items=1/alpha"),
        }
        assert source.events == ["snapshot:enter", "snapshot:exit"]

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["model", "tool"])
def test_graph_failure_preserves_shared_resources_until_agent_closes(
    failure: str,
) -> None:
    source = SnapshotSource({TEST_WORKSPACE_ID: "v1"})

    def respond(request: httpx2.Request) -> httpx2.Response:
        payload = (
            response_payload(status="failed")
            if failure == "model"
            else response_payload([call()])
        )
        return sse_response(EventStream(response_events(payload)))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="snapshots",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                external_services=(SNAPSHOT_SOURCE.bind(source),),
                checkpointer=InMemorySaver(),
                bundles=[BundleConfig(SNAPSHOTS, {"tools": True, "fail_tool": True})],
            ) as agent:
                expected_error = (
                    ModelResponseError if failure == "model" else RuntimeError
                )
                expected_message = (
                    "did not complete" if failure == "model" else "tool failed"
                )
                with pytest.raises(expected_error, match=expected_message):
                    await complete_turn(agent)
                assert source.events == ["snapshot:enter"]
            assert not client.is_closed()

    asyncio.run(run())
    assert source.events == ["snapshot:enter", "snapshot:exit"]


def test_cancellation_closes_stream_and_preserves_agent_resources_for_resume() -> None:
    async def run() -> None:
        entered = asyncio.Event()
        blocked = asyncio.Event()
        source = SnapshotSource({TEST_WORKSPACE_ID: "v1"})

        class BlockedStream(EventStream):
            async def __aiter__(self) -> AsyncIterator[bytes]:
                async for chunk in super().__aiter__():
                    yield chunk
                    entered.set()
                    await blocked.wait()

            async def aclose(self) -> None:
                await super().aclose()
                source.events.append("stream:close")

        stream = BlockedStream(response_events(response_payload()))
        streams = iter([stream, EventStream(response_events(response_payload()))])
        async with offline_client(
            httpx2.MockTransport(lambda _: sse_response(next(streams)))
        ) as client:
            async with open_agent(
                agent_id="snapshots",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                external_services=(SNAPSHOT_SOURCE.bind(source),),
                checkpointer=InMemorySaver(),
                bundles=[BundleConfig(SNAPSHOTS)],
            ) as agent:
                task = asyncio.create_task(complete_turn(agent))
                await asyncio.wait_for(entered.wait(), timeout=5)
                assert source.events == ["snapshot:enter"]
                task.cancel()
                async with asyncio.timeout(5):
                    with pytest.raises(asyncio.CancelledError):
                        await task
                assert stream.closed
                assert source.events == ["snapshot:enter", "stream:close"]
                source.published[TEST_WORKSPACE_ID] = "v2"
                interrupted = await agent.aget_state(workspace_id=TEST_WORKSPACE_ID)
                async for _ in agent.aresume(
                    workspace_id=TEST_WORKSPACE_ID,
                    turn_id=interrupted.values["turn_id"],
                ):
                    pass
                saved = await agent.aget_state(workspace_id=TEST_WORKSPACE_ID)
                assert saved.values["snapshot_version"] == "v1"
                assert source.reads == [TEST_WORKSPACE_ID]
            assert source.events == ["snapshot:enter", "stream:close", "snapshot:exit"]
            assert not client.is_closed()

    asyncio.run(run())


def test_stream_early_exit_closes_invocation_without_closing_agent_resources() -> None:
    async def run() -> None:
        blocked = asyncio.Event()
        source = SnapshotSource({TEST_WORKSPACE_ID: "v1"})

        class BlockedStream(EventStream):
            async def __aiter__(self) -> AsyncIterator[bytes]:
                async for chunk in super().__aiter__():
                    yield chunk
                    await blocked.wait()

        stream = BlockedStream(response_events(response_payload()))
        async with offline_client(
            httpx2.MockTransport(lambda _: sse_response(stream))
        ) as client:
            async with open_agent(
                agent_id="snapshots",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                external_services=(SNAPSHOT_SOURCE.bind(source),),
                checkpointer=InMemorySaver(),
                bundles=[BundleConfig(SNAPSHOTS)],
            ) as agent:
                async with asyncio.timeout(5):
                    async with aclosing(
                        agent.astream(
                            turn_id=uuid4(),
                            workspace_id=TEST_WORKSPACE_ID,
                            input=cast(ResponseInputParam, INITIAL),
                        )
                    ) as events:
                        async for event in events:
                            if event["type"] == "custom":
                                assert source.events == ["snapshot:enter"]
                                break
                assert stream.closed
                assert source.events == ["snapshot:enter"]
            assert source.events == ["snapshot:enter", "snapshot:exit"]
            assert not client.is_closed()

    asyncio.run(run())


def test_bundle_cleanup_exception_propagates_without_wrapping() -> None:
    cleanup_error = RuntimeError("cleanup failed")
    source = SnapshotSource({TEST_WORKSPACE_ID: "v1"}, cleanup_error=cleanup_error)

    def respond(request: httpx2.Request) -> httpx2.Response:
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            with pytest.raises(RuntimeError) as caught:
                async with open_agent(
                    agent_id="snapshots",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    external_services=(SNAPSHOT_SOURCE.bind(source),),
                    checkpointer=InMemorySaver(),
                    bundles=[BundleConfig(SNAPSHOTS)],
                ) as agent:
                    await complete_turn(agent)
            assert caught.value is cleanup_error
            assert not client.is_closed()

    asyncio.run(run())
    assert source.events == ["snapshot:enter", "snapshot:exit"]
