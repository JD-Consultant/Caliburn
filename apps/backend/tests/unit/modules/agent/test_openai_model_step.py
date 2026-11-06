"""真 SDK 串流的失敗、terminal、取消及最終訊息判讀。"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import cast
from uuid import UUID

import httpx2
import pytest
from langchain_core.tools import StructuredTool
from openai import InternalServerError, RateLimitError
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.infrastructure.openai.call_model import ModelResponseError
from tests.unit.modules.agent.offline_openai import (
    INITIAL,
    EventStream,
    call,
    message,
    offline_client,
    open_test_agent,
    reasoning,
    response_events,
    response_payload,
    run_test_agent,
    run_turn,
    sse_response,
    stream_test_agent,
)


@pytest.mark.parametrize("status", ["failed", "incomplete"])
def test_unsuccessful_terminal_preserves_native_response_and_closes_stream(
    status: str,
) -> None:
    effects: list[str] = []
    payload = response_payload([reasoning(), call()], status=status)
    stream = EventStream(response_events(payload))

    async def read_alpha(item: str) -> str:
        effects.append(item)
        return item

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read.")

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: sse_response(stream))
        ) as client:
            async with open_test_agent(client=client, tools=(tool,)) as graph:
                with pytest.raises(ModelResponseError) as caught:
                    await run_turn(graph, input=cast(ResponseInputParam, INITIAL))
                assert caught.value.response.status == status
                opaque = caught.value.response.output[0]
                assert opaque.type == "reasoning"
                assert opaque.encrypted_content == "synthetic-opaque-content"

    asyncio.run(run())
    assert stream.closed and effects == []


@pytest.mark.parametrize(
    "ending, error_type", [("error", ValueError), ("eof", RuntimeError)]
)
def test_stream_error_or_eof_cannot_execute_argument_deltas(
    ending: str, error_type: type[Exception]
) -> None:
    events = response_events(response_payload())[:1]
    events.extend(
        [
            {
                "type": "response.output_item.added",
                "sequence_number": 1,
                "output_index": 0,
                "item": {**call(), "arguments": "", "status": "in_progress"},
            },
            {
                "type": "response.function_call_arguments.delta",
                "sequence_number": 2,
                "output_index": 0,
                "item_id": "fc_call_alpha",
                "delta": '{"item":"alpha"}',
            },
        ]
    )
    if ending == "error":
        events.append(
            {
                "type": "error",
                "sequence_number": 3,
                "code": "server_error",
                "param": None,
                "message": "Synthetic stream error",
            }
        )
    stream = EventStream(events)
    effects: list[str] = []

    async def read_alpha(item: str) -> str:
        effects.append(item)
        return item

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read.")

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: sse_response(stream))
        ) as client:
            async with open_test_agent(client=client, tools=(tool,)) as graph:
                with pytest.raises(error_type):
                    await run_turn(graph, input=cast(ResponseInputParam, INITIAL))

    asyncio.run(run())
    assert stream.closed and effects == []


@pytest.mark.parametrize(
    "output",
    [
        [],
        [reasoning()],
        [message(text="")],
        [{**message(), "status": "in_progress"}],
        pytest.param(
            [{**message(), "role": "user"}],
            id="non_assistant",
            marks=pytest.mark.filterwarnings(
                "ignore:Pydantic serializer warnings:UserWarning"
            ),
        ),
        pytest.param(
            [message("future_phase")],
            marks=pytest.mark.filterwarnings(
                "ignore:Pydantic serializer warnings:UserWarning"
            ),
        ),
    ],
)
def test_completed_generation_without_complete_answer_is_not_agent_success(
    output: list[dict[str, object]],
) -> None:
    stream = EventStream(response_events(response_payload(output)))

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: sse_response(stream))
        ) as client:
            async with open_test_agent(client=client, tools=()) as graph:
                with pytest.raises(ValueError):
                    await run_turn(graph, input=cast(ResponseInputParam, INITIAL))

    asyncio.run(run())
    assert stream.closed


@pytest.mark.parametrize(
    "unsupported",
    [
        {"id": "search_1", "type": "web_search_call", "status": "completed"},
        message("future_phase"),
    ],
)
@pytest.mark.filterwarnings("ignore:Pydantic serializer warnings:UserWarning")
def test_unsupported_output_rejects_whole_response_before_tools(
    unsupported: dict[str, object],
) -> None:
    effects: list[str] = []

    async def read_alpha(item: str) -> str:
        effects.append(item)
        return item

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read.")
    responses = iter([response_payload([call(), unsupported]), response_payload()])

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(next(responses))))
            )
        ) as client:
            async with open_test_agent(client=client, tools=(tool,)) as agent:
                with pytest.raises(ValueError, match="Unsupported"):
                    await run_turn(agent)
                saved = await agent.aget_state(workspace_id=UUID(int=2))
                assert saved.values["model_response"] is None
                assert saved.next == ("call_model",)

    asyncio.run(run())
    assert effects == []


@pytest.mark.parametrize(
    "output, expected_steps",
    [
        ([message()], 1),
        ([message(None)], 1),
        (
            [
                {
                    **message(),
                    "content": [{"type": "refusal", "refusal": "Cannot help."}],
                }
            ],
            1,
        ),
        ([message("commentary")], 2),
        ([message(), message("commentary")], 2),
    ],
)
def test_last_complete_assistant_message_controls_finish(
    output: list[dict[str, object]], expected_steps: int
) -> None:
    requests = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal requests
        requests += 1
        return sse_response(
            EventStream(
                response_events(response_payload(output if requests == 1 else None))
            )
        )

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            result = (
                await run_test_agent(
                    client=client, tools=(), input=cast(ResponseInputParam, INITIAL)
                )
            )["model_response"]
            assert result is not None
            assert result.output

    asyncio.run(run())
    assert requests == expected_steps


@pytest.mark.parametrize(
    "status_code, error_type", [(429, RateLimitError), (503, InternalServerError)]
)
def test_sdk_errors_report_safe_failure_and_log_original_type_without_retry(
    status_code: int,
    error_type: type[Exception],
    caplog: pytest.LogCaptureFixture,
) -> None:
    attempts = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        return httpx2.Response(
            status_code,
            headers={"x-request-id": "req_offline"},
            json={"error": {"message": "Synthetic failure", "type": "offline_error"}},
        )

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            with pytest.raises(RuntimeError, match="Model provider request failed"):
                await run_test_agent(
                    client=client, tools=(), input=cast(ResponseInputParam, INITIAL)
                )

    asyncio.run(run())
    assert attempts == 1
    assert any(
        getattr(record, "error_type", None) == error_type.__name__
        for record in caplog.records
    )


def test_transport_failure_after_delta_reports_safe_error_and_closes_stream() -> None:

    class BrokenStream(EventStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            async for event in super().__aiter__():
                yield event
            raise httpx2.ReadError("Synthetic disconnection")

    stream = BrokenStream(response_events(response_payload())[:1])

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: sse_response(stream))
        ) as client:
            with pytest.raises(RuntimeError, match="Model provider request failed"):
                await run_test_agent(
                    client=client, tools=(), input=cast(ResponseInputParam, INITIAL)
                )

    asyncio.run(run())
    assert stream.closed


def test_cancellation_closes_active_stream_and_never_produces_a_result() -> None:

    async def run() -> None:
        started = asyncio.Event()
        never = asyncio.Event()

        class WaitingStream(EventStream):
            async def __aiter__(self) -> AsyncIterator[bytes]:
                async for event in super().__aiter__():
                    yield event
                started.set()
                await never.wait()

        stream = WaitingStream(response_events(response_payload())[:1])
        async with offline_client(
            httpx2.MockTransport(lambda _: sse_response(stream))
        ) as client:
            async with open_test_agent(client=client, tools=()) as graph:
                task = asyncio.create_task(
                    run_turn(graph, input=cast(ResponseInputParam, INITIAL))
                )
                try:
                    await asyncio.wait_for(started.wait(), timeout=5)
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                    assert stream.closed
                    assert not client.is_closed()
                finally:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())


def test_custom_events_redact_opaque_without_changing_native_result() -> None:
    stream = EventStream(response_events(response_payload([reasoning(), message()])))

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: sse_response(stream))
        ) as client:
            events = [
                event
                async for event in stream_test_agent(
                    client=client, tools=(), input=cast(ResponseInputParam, INITIAL)
                )
            ]
        custom = [event["data"] for event in events if event["type"] == "custom"]
        assert "synthetic-opaque-content" not in json.dumps(custom)
        assert UUID(custom[-1]["execution"]["turn_id"])
        assert custom[-1]["execution"]["model_step"] == 1
        assert custom[-1]["redacted_fields"] == [
            "$.response.output[0].encrypted_content"
        ]
        final = [
            event["data"]["model_response"]
            for event in events
            if event["type"] == "values" and "model_response" in event["data"]
        ][-1]
        opaque = final.output[0]
        assert opaque.type == "reasoning"
        assert opaque.encrypted_content == "synthetic-opaque-content"

    asyncio.run(run())
