"""Execute one native Step with explicit persistence boundaries and ordered tool effects."""

import json
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from openai.types.responses import Response, ResponseFunctionToolCall

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import NativeItems, snapshot_response
from caliburn.agent_execution.response_steps import UnsupportedModelResponseError
from caliburn.agent_execution.tool_steps import (
    ReceivedModelResponse,
    _build_response_step,
    run_response_step,
)
from tests.fixtures.response_capacity import synthetic_capacity_limits, synthetic_response_runtime


async def ensure_active() -> None:
    """This isolated graph fixture has no product execution owner."""


async def account_response(received: ReceivedModelResponse) -> None:
    """This isolated graph fixture does not persist execution costs."""


def make_request(input_items: NativeItems) -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic",
        input_items=input_items,
        tools=[],
        reasoning_effort="low",
        max_output_tokens=512,
    )


def model_response() -> Response:
    raw = json.loads(
        (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(encoding="utf-8")
    )
    first = raw["output"][2]
    second = {**deepcopy(first), "id": "fc_second", "call_id": "second"}
    raw["output"].append(second)
    return Response.model_validate(raw)


@pytest.mark.asyncio
async def test_model_and_each_prepared_operation_are_saved_before_effects() -> None:
    response = model_response()
    events = []
    saver = InMemorySaver(
        serde=JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)
    )
    graph = _build_response_step(saver, max_tool_calls=16)
    config = {"configurable": {"thread_id": "ordered-step"}}
    input_items = [{"role": "user", "content": "synthetic"}]

    async def request(model_request: ResponseRequest, request_id: UUID) -> ReceivedModelResponse:
        assert model_request.count_payload()["input"] == input_items
        events.append("model")
        return ReceivedModelResponse(response=response, attempt_id=uuid4())

    async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
        saved = await graph.aget_state(config)
        assert saved.values["response_snapshot"] == snapshot_response(response)
        assert saved.values["operation_seed"] is not None
        events.append("prepare:" + call.call_id)
        return {"operation_id": str(operation_id), "call_id": call.call_id}

    async def execute(prepared: object) -> str:
        saved = await graph.aget_state(config)
        assert saved.values["prepared_tool"] == prepared
        assert isinstance(prepared, dict)
        events.append("execute:" + prepared["call_id"])
        return "result:" + prepared["call_id"]

    result = await graph.ainvoke(
        {
            "request_snapshot": make_request(input_items).create_payload(),
            "request_id": uuid4(),
            "model_step_limit": None,
            "tool_call_limit": 16,
            "capacity_limits": synthetic_capacity_limits(),
        },
        config,
        context=synthetic_response_runtime(
            request_model=request,
            prepare_tool=prepare,
            execute_tool=execute,
            ensure_active=ensure_active,
            account_response=account_response,
        ),
        durability="sync",
    )
    assert events == [
        "model",
        "prepare:call_synthetic",
        "execute:call_synthetic",
        "prepare:second",
        "execute:second",
    ]
    assert result["next_action"] == "continue"
    assert [item["call_id"] for item in result["tool_results"]] == ["call_synthetic", "second"]
    assert result["input_items"][:1] == input_items
    assert len(result["input_items"]) == 7
    assert result["prepared_tool"] is None


@pytest.mark.asyncio
async def test_saved_first_result_and_pending_second_do_not_recall_or_reprepare() -> None:
    response = model_response()
    events = []
    attempts = 0
    prepared_second = None
    saver = InMemorySaver(
        serde=JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)
    )
    graph = _build_response_step(saver, max_tool_calls=16)
    config = {"configurable": {"thread_id": "recover-second"}}

    async def request(model_request: ResponseRequest, request_id: UUID) -> ReceivedModelResponse:
        events.append("model")
        return ReceivedModelResponse(response=response, attempt_id=uuid4())

    async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
        events.append("prepare:" + call.call_id)
        return {"operation_id": str(operation_id), "call_id": call.call_id}

    async def execute(prepared: object) -> str:
        nonlocal attempts, prepared_second
        assert isinstance(prepared, dict)
        events.append("execute:" + prepared["call_id"])
        if prepared["call_id"] == "second":
            attempts += 1
            if attempts == 1:
                prepared_second = deepcopy(prepared)
                raise ConnectionError("synthetic result acknowledgement lost")
            assert prepared == prepared_second
        return "original result:" + prepared["call_id"]

    runtime = synthetic_response_runtime(
        request_model=request,
        prepare_tool=prepare,
        execute_tool=execute,
        ensure_active=ensure_active,
        account_response=account_response,
    )
    with pytest.raises(ConnectionError):
        await graph.ainvoke(
            {
                "request_snapshot": make_request([]).create_payload(),
                "request_id": uuid4(),
                "model_step_limit": None,
                "tool_call_limit": 16,
                "capacity_limits": synthetic_capacity_limits(),
            },
            config,
            context=runtime,
            durability="sync",
        )
    assert (await graph.aget_state(config)).next == ("execute_tool",)
    result = await graph.ainvoke(None, config, context=runtime, durability="sync")
    assert events == [
        "model",
        "prepare:call_synthetic",
        "execute:call_synthetic",
        "prepare:second",
        "execute:second",
        "execute:second",
    ]
    assert [item["call_id"] for item in result["tool_results"]] == ["call_synthetic", "second"]


@pytest.mark.asyncio
async def test_read_or_rejection_is_saved_as_result_without_executing() -> None:
    response = model_response()
    saver = InMemorySaver()
    graph = _build_response_step(saver, max_tool_calls=16)

    async def request(model_request: ResponseRequest, request_id: UUID) -> ReceivedModelResponse:
        return ReceivedModelResponse(response=response, attempt_id=uuid4())

    async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
        return "read or known rejection:" + call.call_id

    async def execute(prepared: object) -> str:
        pytest.fail("A read or known rejection must not dispatch a write")

    result = await graph.ainvoke(
        {
            "request_snapshot": make_request([]).create_payload(),
            "request_id": uuid4(),
            "model_step_limit": None,
            "tool_call_limit": 16,
            "capacity_limits": synthetic_capacity_limits(),
        },
        {"configurable": {"thread_id": "read-only"}},
        context=synthetic_response_runtime(
            request_model=request,
            prepare_tool=prepare,
            execute_tool=execute,
            ensure_active=ensure_active,
            account_response=account_response,
        ),
        durability="sync",
    )
    assert len(result["tool_results"]) == 2
    assert result["next_action"] == "continue"


@pytest.mark.asyncio
async def test_unsupported_response_is_preserved_before_routing_rejects_it() -> None:
    response = model_response()
    response.output[1].phase = None
    saver = InMemorySaver()
    graph = _build_response_step(saver, max_tool_calls=16)
    config = {"configurable": {"thread_id": "unsupported-phase"}}

    async def request(model_request: ResponseRequest, request_id: UUID) -> ReceivedModelResponse:
        return ReceivedModelResponse(response=response, attempt_id=uuid4())

    async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
        pytest.fail("Unsupported protocol cannot reach tools")

    async def execute(prepared: object) -> str:
        pytest.fail("Unsupported protocol cannot reach effects")

    with pytest.raises(UnsupportedModelResponseError):
        await graph.ainvoke(
            {
                "request_snapshot": make_request([]).create_payload(),
                "request_id": uuid4(),
                "model_step_limit": None,
                "tool_call_limit": 16,
                "capacity_limits": synthetic_capacity_limits(),
            },
            config,
            context=synthetic_response_runtime(
                request_model=request,
                prepare_tool=prepare,
                execute_tool=execute,
                ensure_active=ensure_active,
                account_response=account_response,
            ),
            durability="sync",
        )
    saved = await graph.aget_state(config)
    assert saved.values["response_snapshot"] == snapshot_response(response)
    assert saved.next == ("prepare_tool",)


@pytest.mark.asyncio
async def test_public_entry_rejects_restarted_input_and_resumes_same_operation() -> None:
    response = model_response()
    requests = 0
    attempts = 0
    operations = []
    saver = InMemorySaver()

    async def request(model_request: ResponseRequest, request_id: UUID) -> ReceivedModelResponse:
        nonlocal requests
        requests += 1
        return ReceivedModelResponse(response=response, attempt_id=uuid4())

    async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
        return {"call_id": call.call_id, "operation_id": operation_id}

    async def execute(prepared: object) -> str:
        nonlocal attempts
        assert isinstance(prepared, dict)
        if prepared["call_id"] == "second":
            attempts += 1
            if attempts == 1:
                raise ConnectionError("synthetic")
        operations.append(prepared["operation_id"])
        return "done"

    runtime = synthetic_response_runtime(
        request_model=request,
        prepare_tool=prepare,
        execute_tool=execute,
        ensure_active=ensure_active,
        account_response=account_response,
    )
    options = {"thread_id": "protected-entry", "runtime": runtime, "max_tool_calls": 16}
    with pytest.raises(ValueError, match="no saved Step"):
        await run_response_step(saver, request=None, **options)
    with pytest.raises(ConnectionError):
        await run_response_step(saver, request=make_request([]), **options)
    with pytest.raises(ValueError, match="already exists"):
        await run_response_step(saver, request=make_request([]), **options)
    result = await run_response_step(saver, request=None, **options)
    assert requests == 1
    assert len(set(operations)) == len(operations) == 2
    assert result["next_action"] == "continue"


@pytest.mark.asyncio
async def test_configured_tool_bound_rejects_before_any_effect() -> None:
    async def request(model_request: ResponseRequest, request_id: UUID) -> ReceivedModelResponse:
        return ReceivedModelResponse(response=model_response(), attempt_id=uuid4())

    async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
        pytest.fail("Over-limit response cannot dispatch any tool")

    async def execute(prepared: object) -> str:
        pytest.fail("Over-limit response cannot dispatch any effect")

    with pytest.raises(ValueError, match="tool bound"):
        await run_response_step(
            InMemorySaver(),
            thread_id="limited-step",
            request=make_request([]),
            runtime=synthetic_response_runtime(
                request_model=request,
                prepare_tool=prepare,
                execute_tool=execute,
                ensure_active=ensure_active,
                account_response=account_response,
            ),
            max_tool_calls=1,
        )
