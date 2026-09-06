"""Pinned transport characterization, not a provider or model-quality smoke.

Exercise build_model -> ChatOpenAI -> OpenAI SDK -> MockTransport. Only sleep
is replaced; no SDK methods or retry predicates are mocked. The compiled-agent
cases observe the existing build_agent seam, not the controller's root/child
lifecycle. A changed retry owner, swallowed exception, or invented completed
status must fail these checks. Existing passing behavior is not a TDD RED.
"""

from contextlib import contextmanager
import json
import time

import httpx
import pytest
from langchain.agents.middleware import wrap_model_call
from langchain_core.exceptions import ModelAuthenticationError, ModelInvalidRequestError
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from openai import (
    APIConnectionError, APITimeoutError, AuthenticationError, BadRequestError,
    InternalServerError, OpenAI, RateLimitError,
)
from openai.types.responses import Response, ResponseStreamEvent
from pydantic import TypeAdapter

from analysis_agent.provider import build_model
from analysis_agent.runtime import build_agent
from test_native_continuity import assistant_text, response_body


@pytest.fixture
def sleeps(monkeypatch):
    durations = []
    monkeypatch.setattr(time, "sleep", durations.append)
    return durations


@contextmanager
def offline_model(respond):
    with httpx.Client(transport=httpx.MockTransport(respond), trust_env=False) as client:
        yield build_model(model="gpt-5.6-luna", api_key="offline-not-a-key", http_client=client)


def completed():
    return httpx.Response(200, json=response_body([assistant_text("請補充驗收工作。")]))


def status_error(status, headers=None):
    return httpx.Response(status, headers=headers, json={"error": {
        "type": "invalid_request_error" if status in (400, 401) else "server_error",
        "code": "invalid_function_parameters" if status == 400 else None,
        "param": "tools[0].parameters" if status == 400 else None,
        "message": "synthetic schema rejected" if status == 400 else "synthetic failure",
    }})


def invoke(model, entrypoint, model_entries):
    if entrypoint == "adapter":
        return model.invoke([HumanMessage("我負責網站驗收。")])

    @wrap_model_call
    def observe(request, handler):
        # Observation only: one handler call, no exception handling/retries.
        model_entries.append("model")
        return handler(request)

    agent = build_agent(model=model, checkpointer=InMemorySaver(),
                        instructions="離線訪談規則", middleware=[observe])
    result = agent.invoke({"messages": [HumanMessage("我負責網站驗收。", id="employee")]},
                          {"configurable": {"thread_id": "transport"}}, durability="sync")
    assert not any(isinstance(message, ToolMessage) for message in result["messages"])
    return result["messages"][-1]


@pytest.mark.parametrize("entrypoint", ["adapter", "agent"])
@pytest.mark.parametrize("status", [408, 409, 429, 500, 503])
def test_transient_status_recovers_inside_one_model_call(status, entrypoint, sleeps):
    requests, model_entries = [], []

    def respond(request):
        requests.append(request)
        return status_error(status) if len(requests) == 1 else completed()

    with offline_model(respond) as model:
        answer = invoke(model, entrypoint, model_entries)

    assert len(requests) == 2
    assert [request.headers["x-stainless-retry-count"] for request in requests] == ["0", "1"]
    assert all(request.method == "POST" and request.url.path.endswith("/responses") for request in requests)
    assert requests[0].content == requests[1].content
    assert len(sleeps) == 1 and 0.375 <= sleeps[0] <= 0.5
    assert model_entries == (["model"] if entrypoint == "agent" else [])
    assert answer.text == "請補充驗收工作。"
    assert answer.response_metadata["status"] == "completed"


@pytest.mark.parametrize("entrypoint", ["adapter", "agent"])
@pytest.mark.parametrize("status, error_type", [(429, RateLimitError), (503, InternalServerError)])
def test_exhaustion_stops_at_three_http_attempts_without_outer_retry(
    status, error_type, entrypoint, sleeps,
):
    requests, model_entries = [], []

    def respond(request):
        requests.append(request)
        return status_error(status)

    with offline_model(respond) as model:
        with pytest.raises(error_type) as caught:
            invoke(model, entrypoint, model_entries)

    assert caught.value.status_code == status
    assert [request.headers["x-stainless-retry-count"] for request in requests] == ["0", "1", "2"]
    assert len(sleeps) == 2
    assert 0.375 <= sleeps[0] <= 0.5 and 0.75 <= sleeps[1] <= 1.0
    assert model_entries == (["model"] if entrypoint == "agent" else [])


@pytest.mark.parametrize("entrypoint", ["adapter", "agent"])
@pytest.mark.parametrize("status, sdk_type, model_type", [
    (400, BadRequestError, ModelInvalidRequestError),
    (401, AuthenticationError, ModelAuthenticationError),
])
def test_schema_and_auth_failure_escape_without_blind_retry(
    status, sdk_type, model_type, entrypoint, sleeps,
):
    requests, model_entries = [], []

    def respond(request):
        requests.append(request)
        # A hidden retry would obtain success and fail pytest.raises.
        return status_error(status, {"x-request-id": "req_offline"}) if len(requests) == 1 else completed()

    with offline_model(respond) as model:
        with pytest.raises(sdk_type) as caught:
            invoke(model, entrypoint, model_entries)

    assert len(requests) == 1 and sleeps == []
    assert model_entries == (["model"] if entrypoint == "agent" else [])
    assert isinstance(caught.value, model_type)
    assert caught.value.is_retryable is False
    assert caught.value.status_code == status
    assert caught.value.request_id == "req_offline"


@pytest.mark.parametrize("headers, seconds", [
    ({"retry-after": "7"}, 7.0),
    ({"retry-after": "120"}, 120.0),
    ({"retry-after-ms": "1250", "retry-after": "7"}, 1.25),
])
def test_applicable_retry_after_is_the_actual_sdk_sleep(headers, seconds, sleeps):
    events = []

    def respond(request):
        events.append(tuple(sleeps))
        return status_error(429, headers) if len(events) == 1 else completed()

    with offline_model(respond) as model:
        answer = model.invoke([HumanMessage("離線重試")])

    assert events == [(), (seconds,)]
    assert sleeps == [seconds]
    assert answer.response_metadata["status"] == "completed"


def test_retry_after_above_sdk_ceiling_does_not_resend_early(sleeps):
    requests = []

    def respond(request):
        requests.append(request)
        return status_error(429, {"retry-after": "121"}) if len(requests) == 1 else completed()

    with offline_model(respond) as model:
        with pytest.raises(RateLimitError):
            model.invoke([HumanMessage("離線重試")])

    assert len(requests) == 1 and sleeps == []


@pytest.mark.parametrize("http_error, sdk_error", [
    (httpx.ConnectError, APIConnectionError),
    (httpx.ReadTimeout, APITimeoutError),
])
@pytest.mark.parametrize("recover", [True, False])
def test_pre_response_transport_errors_retry_but_remain_typed_on_exhaustion(
    http_error, sdk_error, recover, sleeps,
):
    requests = []

    def respond(request):
        requests.append(request)
        if recover and len(requests) == 2:
            return completed()
        raise http_error("synthetic pre-response transport failure", request=request)

    with offline_model(respond) as model:
        if recover:
            answer = model.invoke([HumanMessage("離線網路中斷")])
            assert answer.response_metadata["status"] == "completed"
        else:
            with pytest.raises(sdk_error):
                model.invoke([HumanMessage("離線網路中斷")])

    assert len(requests) == (2 if recover else 3)
    assert len(sleeps) == (1 if recover else 2)


def incomplete_body():
    item = assistant_text("尚未說完的分析")
    item["status"] = "incomplete"
    body = response_body([item])
    body.update(status="incomplete", incomplete_details={"reason": "max_output_tokens"}, usage=None)
    return Response.model_validate(body).model_dump(mode="json", exclude_none=True)


def test_nonstream_incomplete_is_returned_as_incomplete_not_transport_or_tool_error(sleeps):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=incomplete_body())

    with offline_model(respond) as model:
        answer = model.invoke([HumanMessage("離線未完成回覆")])

    assert len(requests) == 1 and sleeps == []
    assert answer.text == "尚未說完的分析"
    assert answer.response_metadata["status"] == "incomplete"
    assert answer.response_metadata["incomplete_details"] == {"reason": "max_output_tokens"}
    assert answer.usage_metadata is None  # Unknown usage is not zero.
    assert answer.tool_calls == [] and not isinstance(answer, ToolMessage)


def test_bare_agent_end_without_completion_guard_is_not_provider_success(sleeps):
    """The basic factory does not itself enforce the Memory/root completion gate."""
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=incomplete_body())

    config = {"configurable": {"thread_id": "partial-transport"}}
    with offline_model(respond) as model:
        agent = build_agent(model=model, checkpointer=InMemorySaver(), instructions="離線訪談規則")
        result = agent.invoke({"messages": [HumanMessage("員工原話", id="employee")]},
                              config, durability="sync")
        snapshot = agent.get_state(config)

    assert len(requests) == 1 and sleeps == []
    assert snapshot.next == ()
    assert result["messages"][0].content == "員工原話"
    assert result["messages"][-1].response_metadata["status"] == "incomplete"
    assert not any(isinstance(message, ToolMessage) for message in result["messages"])


def stream_events(ending):
    """Synthetic Responses events checked against the pinned public SDK schema."""
    created = response_body([])
    created.update(status="in_progress", usage=None)
    item = assistant_text("")
    item.update(status="in_progress", content=[])
    events = [
        {"type": "response.created", "sequence_number": 0, "response": created},
        {"type": "response.output_item.added", "sequence_number": 1,
         "output_index": 0, "item": item},
        {"type": "response.content_part.added", "sequence_number": 2,
         "item_id": "msg_test", "output_index": 0, "content_index": 0,
         "part": {"type": "output_text", "text": "", "annotations": [], "logprobs": []}},
        {"type": "response.output_text.delta", "sequence_number": 3,
         "item_id": "msg_test", "output_index": 0, "content_index": 0,
         "delta": "尚未說完的分析", "logprobs": []},
    ]
    if ending in ("completed", "incomplete"):
        body = incomplete_body() if ending == "incomplete" else response_body([assistant_text("尚未說完的分析")])
        events.append({"type": "response." + ending, "sequence_number": 4, "response": body})
    elif ending == "error":
        events.append({"type": "error", "sequence_number": 4, "code": "server_error",
                       "message": "synthetic stream failure", "param": None})
    elif ending == "failed":
        body = incomplete_body()
        body.update(status="failed", incomplete_details=None,
                    error={"code": "server_error", "message": "synthetic stream failure"})
        events.append({"type": "response.failed", "sequence_number": 4, "response": body})
    else:
        assert ending == "eof"
    schema = TypeAdapter(ResponseStreamEvent)
    return [schema.validate_python(event).model_dump(mode="json", exclude_none=True) for event in events]


def sse(events):
    return "".join(f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events).encode()


@pytest.mark.parametrize("ending", ["completed", "incomplete"])
def test_stream_terminal_chunk_preserves_provider_status_not_just_last_marker(ending, sleeps):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              content=sse(stream_events(ending)))

    with offline_model(respond) as model:
        chunks = list(model.stream([HumanMessage("離線串流")]))

    assert len(requests) == 1 and sleeps == []
    assert json.loads(requests[0].content)["stream"] is True
    assert "".join(chunk.text for chunk in chunks) == "尚未說完的分析"
    assert chunks[-1].chunk_position == "last"
    assert chunks[-1].response_metadata["status"] == ending
    if ending == "incomplete":
        assert chunks[-1].response_metadata["incomplete_details"] == {"reason": "max_output_tokens"}
        assert all(chunk.usage_metadata is None for chunk in chunks)
        assert all(chunk.response_metadata.get("status") != "completed" for chunk in chunks)


@pytest.mark.parametrize("ending", ["error", "failed", "eof"])
def test_adapter_ends_partial_stream_without_completed_status_or_raising(ending, sleeps):
    """Concern: flat error/response.failed are not surfaced as typed exceptions.

    Natural iterator exhaustion (including clean EOF) is not provider success.
    An outer completion guard is necessary; this test does not implement one.
    """
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              content=sse(stream_events(ending)))

    with offline_model(respond) as model:
        chunks = list(model.stream([HumanMessage("離線部分串流")]))

    assert len(requests) == 1 and sleeps == []
    assert "".join(chunk.text for chunk in chunks) == "尚未說完的分析"
    assert all(chunk.response_metadata.get("status") is None for chunk in chunks)
    assert all(chunk.usage_metadata is None for chunk in chunks)
    assert all(chunk.tool_calls == [] for chunk in chunks)


@pytest.mark.parametrize("ending, event_type", [("error", "error"), ("failed", "response.failed")])
def test_sdk_itself_yields_typed_failure_events_which_adapter_does_not_surface(
    ending, event_type, sleeps,
):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              content=sse(stream_events(ending)))

    with httpx.Client(transport=httpx.MockTransport(respond), trust_env=False) as client:
        with OpenAI(api_key="offline-not-a-key", http_client=client,
                    base_url="https://offline.invalid/v1") as sdk:
            with sdk.responses.create(model="gpt-5.6-luna", input="離線部分串流",
                                      store=False, stream=True) as stream:
                events = list(stream)

    assert len(requests) == 1 and sleeps == []
    assert [event.type for event in events] == [
        "response.created", "response.output_item.added", "response.content_part.added",
        "response.output_text.delta", event_type,
    ]
    if ending == "error":
        assert events[-1].code == "server_error"
        assert events[-1].message == "synthetic stream failure"
    else:
        assert events[-1].response.status == "failed"
        assert events[-1].response.error.code == "server_error"


class InterruptedStream(httpx.SyncByteStream):
    def __init__(self, request):
        self.request = request
        self.closed = False

    def __iter__(self):
        yield sse(stream_events("eof"))
        raise httpx.ReadError("synthetic disconnect after HTTP 200", request=self.request)

    def close(self):
        self.closed = True


def test_disconnect_during_body_iteration_does_not_replay_or_complete_partial_stream(sleeps):
    requests, streams, chunks = [], [], []

    def respond(request):
        requests.append(request)
        streams.append(InterruptedStream(request))
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=streams[-1])

    with offline_model(respond) as model:
        with pytest.raises(httpx.ReadError, match="synthetic disconnect"):
            for chunk in model.stream([HumanMessage("離線串流中斷")]):
                chunks.append(chunk)

    assert len(requests) == 1 and sleeps == []
    assert streams[0].closed
    assert "".join(chunk.text for chunk in chunks) == "尚未說完的分析"
    assert all(chunk.response_metadata.get("status") != "completed" for chunk in chunks)
    assert all(chunk.usage_metadata is None for chunk in chunks)
