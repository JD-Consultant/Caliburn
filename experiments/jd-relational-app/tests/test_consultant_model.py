"""Real SDK and pinned adapter, synthetic local transports; zero provider calls."""

import asyncio
from copy import deepcopy
from importlib.metadata import version
import json

import anthropic
import httpx2
import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage

from jd_relational.consultant_model import (
    ConfirmedChatAnthropic, ConsultantModelError, create_consultant_model,
)


def events(kind="text", mode="complete"):
    start = {
        "type": "message_start",
        "message": {
            "id": "msg_synthetic", "type": "message", "role": "assistant",
            "content": [], "model": "synthetic", "stop_reason": None,
            "stop_sequence": None, "usage": {"input_tokens": 7, "output_tokens": 1},
        },
    }
    blocks = []
    if kind == "thinking_tool":
        blocks.extend([
            {"type": "content_block_start", "index": 0, "content_block": {
                "type": "thinking", "thinking": "", "signature": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {
                "type": "thinking_delta", "thinking": "synthetic thought"}},
            {"type": "content_block_delta", "index": 0, "delta": {
                "type": "signature_delta", "signature": "synthetic-signature"}},
            {"type": "content_block_stop", "index": 0},
            {"type": "content_block_start", "index": 1, "content_block": {
                "type": "tool_use", "id": "toolu_synthetic", "name": "jd_read", "input": {}}},
            {"type": "content_block_delta", "index": 1, "delta": {
                "type": "input_json_delta", "partial_json": '{"target":"synthetic"}'}},
            {"type": "content_block_stop", "index": 1},
        ])
    else:
        blocks.extend([
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "合成回覆"}},
            {"type": "content_block_stop", "index": 0},
        ])
    result = [start, *blocks, {
        "type": "message_delta", "delta": {
            "stop_reason": "tool_use" if kind == "thinking_tool" else "end_turn",
            "stop_sequence": None,
        }, "usage": {"input_tokens": 7, "output_tokens": 9},
    }]
    if mode == "complete":
        result.append({"type": "message_stop"})
    elif mode == "error":
        result.append({"type": "error", "error": {"type": "overloaded_error", "message": "synthetic"}})
    return [f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode() for event in result]


class SyncBody(httpx2.SyncByteStream):
    def __init__(self, data):
        self.data = data
        self.closed = False

    def __iter__(self):
        yield from self.data

    def close(self):
        self.closed = True


class AsyncBody(httpx2.AsyncByteStream):
    def __init__(self, data, *, stall=False):
        self.data = data
        self.closed = False
        self.stall = stall
        self.waiting = asyncio.Event()

    async def __aiter__(self):
        for index, item in enumerate(self.data):
            yield item
            if self.stall and index == 0:
                self.waiting.set()
                await asyncio.Event().wait()

    async def aclose(self):
        self.closed = True


class Callback(BaseCallbackHandler):
    def __init__(self):
        self.ends = 0
        self.errors = []

    def on_llm_end(self, response, **kwargs):
        self.ends += 1

    def on_llm_error(self, error, **kwargs):
        self.errors.append(error)


@pytest.fixture(autouse=True)
def no_external_clients(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

    def forbidden(**kwargs):
        raise AssertionError("No real HTTP client is allowed in these tests")

    monkeypatch.setattr("langchain_anthropic.chat_models._get_default_httpx_client", forbidden)
    monkeypatch.setattr("langchain_anthropic.chat_models._get_default_async_httpx_client", forbidden)


def model():
    return create_consultant_model(
        model_name="synthetic", api_key="synthetic-not-a-key", timeout=5, max_tokens=32,
    )


def mock_sync(monkeypatch, body):
    requests = []

    def receive(request):
        assert request.url.host == "api.anthropic.com"
        payload = json.loads(request.content)
        assert payload["stream"] is True
        requests.append(payload)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=body, request=request)

    client = httpx2.Client(transport=httpx2.MockTransport(receive), trust_env=False)
    monkeypatch.setattr("langchain_anthropic.chat_models._get_default_httpx_client", lambda **kwargs: client)
    return client, requests


def mock_async(monkeypatch, body):
    requests = []

    async def receive(request):
        assert request.url.host == "api.anthropic.com"
        payload = json.loads(request.content)
        assert payload["stream"] is True
        requests.append(payload)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=body, request=request)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(receive), trust_env=False)
    monkeypatch.setattr("langchain_anthropic.chat_models._get_default_async_httpx_client", lambda **kwargs: client)
    return client, requests


def assert_message(message, kind):
    assert message.usage_metadata["output_tokens"] == 9
    if kind == "text":
        assert message.content == "合成回覆"
        assert message.response_metadata["stop_reason"] == "end_turn"
    else:
        assert message.response_metadata["stop_reason"] == "tool_use"
        assert message.tool_calls == [{"name": "jd_read", "args": {"target": "synthetic"}, "id": "toolu_synthetic", "type": "tool_call"}]
        thinking = next(block for block in message.content if block["type"] == "thinking")
        assert thinking["thinking"] == "synthetic thought"
        assert thinking["signature"] == "synthetic-signature"


def tool_options(kind):
    if kind == "text":
        return {}
    return {"tools": [{"name": "jd_read", "description": "synthetic", "input_schema": {
        "type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"],
    }}], "thinking": {"type": "enabled", "budget_tokens": 1024}}


@pytest.mark.parametrize("kind", ["text", "thinking_tool"])
@pytest.mark.parametrize("mode", ["complete", "missing_stop", "error"])
def test_sync_native_stream_closure(monkeypatch, mode, kind):
    body = SyncBody(events(kind, mode))
    client, requests = mock_sync(monkeypatch, body)
    callback = Callback()
    human = HumanMessage(content="原始合成\n 文字", id="synthetic_input")
    before = deepcopy(human.model_dump())
    with client:
        if mode == "complete":
            result = model().invoke([human], config={"callbacks": [callback]}, **tool_options(kind))
            assert_message(result, kind)
            assert callback.ends == 1 and callback.errors == []
        else:
            error_type = ConsultantModelError if mode == "missing_stop" else anthropic.APIStatusError
            with pytest.raises(error_type) as caught:
                model().invoke([human], config={"callbacks": [callback]}, **tool_options(kind))
            if mode == "missing_stop":
                assert caught.value.code == "incomplete_model_response"
                assert str(caught.value) == "incomplete_model_response"
            assert callback.ends == 0 and len(callback.errors) == 1
        assert body.closed
    assert human.model_dump() == before
    assert len(requests) == 1


@pytest.mark.parametrize("kind", ["text", "thinking_tool"])
@pytest.mark.parametrize("mode", ["complete", "missing_stop", "error"])
def test_async_native_stream_closure(monkeypatch, mode, kind):
    async def scenario():
        body = AsyncBody(events(kind, mode))
        client, requests = mock_async(monkeypatch, body)
        callback = Callback()
        async with client:
            if mode == "complete":
                result = await model().ainvoke([HumanMessage(content="synthetic")], config={"callbacks": [callback]}, **tool_options(kind))
                assert_message(result, kind)
                assert callback.ends == 1 and callback.errors == []
            else:
                error_type = ConsultantModelError if mode == "missing_stop" else anthropic.APIStatusError
                with pytest.raises(error_type) as caught:
                    await model().ainvoke([HumanMessage(content="synthetic")], config={"callbacks": [callback]}, **tool_options(kind))
                if mode == "missing_stop":
                    assert caught.value.code == "incomplete_model_response"
                assert callback.ends == 0 and len(callback.errors) == 1
            assert body.closed
        assert len(requests) == 1
    asyncio.run(scenario())


def test_sync_close_then_new_incomplete_stream_does_not_inherit_terminal(monkeypatch):
    body = SyncBody(events())
    client, _ = mock_sync(monkeypatch, body)
    with client:
        stream = model()._stream([HumanMessage(content="synthetic")])
        next(stream)
        stream.close()
        assert body.closed
    next_body = SyncBody(events(mode="missing_stop"))
    next_client, _ = mock_sync(monkeypatch, next_body)
    with next_client, pytest.raises(ConsultantModelError):
        list(model()._stream([HumanMessage(content="synthetic")]))


def test_async_close_and_cancel_cleanup(monkeypatch):
    async def scenario():
        body = AsyncBody(events())
        client, _ = mock_async(monkeypatch, body)
        async with client:
            stream = model()._astream([HumanMessage(content="synthetic")])
            await anext(stream)
            await stream.aclose()
            assert body.closed
        stalled = AsyncBody(events(), stall=True)
        client2, _ = mock_async(monkeypatch, stalled)
        async with client2:
            task = asyncio.create_task(model().ainvoke([HumanMessage(content="synthetic")]))
            await asyncio.wait_for(stalled.waiting.wait(), timeout=2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert stalled.closed
        incomplete = AsyncBody(events(mode="missing_stop"))
        client3, _ = mock_async(monkeypatch, incomplete)
        async with client3:
            with pytest.raises(ConsultantModelError):
                await model().ainvoke([HumanMessage(content="synthetic")])
    asyncio.run(scenario())


def test_concurrent_async_calls_on_same_model_keep_independent_completion(monkeypatch):
    async def scenario():
        complete_closed = asyncio.Event()

        class Complete(AsyncBody):
            async def aclose(self):
                await super().aclose()
                complete_closed.set()

        class Incomplete(AsyncBody):
            async def __aiter__(self):
                async for part in super().__aiter__():
                    yield part
                await complete_closed.wait()

        complete = Complete(events())
        incomplete = Incomplete(events(mode="missing_stop"))

        async def receive(request):
            assert request.url.host == "api.anthropic.com"
            payload = json.loads(request.content)
            assert payload["stream"] is True
            body = complete if payload["messages"][0]["content"] == "complete" else incomplete
            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=body, request=request)

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(receive), trust_env=False) as client:
            monkeypatch.setattr("langchain_anthropic.chat_models._get_default_async_httpx_client", lambda **kwargs: client)
            shared = model()
            results = await asyncio.wait_for(asyncio.gather(
                shared.ainvoke([HumanMessage(content="incomplete")]),
                shared.ainvoke([HumanMessage(content="complete")]),
                return_exceptions=True,
            ), timeout=3)
            assert isinstance(results[0], ConsultantModelError)
            assert results[0].code == "incomplete_model_response"
            assert_message(results[1], "text")
            assert complete.closed and incomplete.closed
    asyncio.run(scenario())


def test_interleaved_sync_iterators_in_one_thread_keep_own_terminal(monkeypatch):
    complete = SyncBody(events())
    first_client, _ = mock_sync(monkeypatch, complete)
    with first_client:
        first = model()._stream([HumanMessage(content="first")])
        next(first)
        incomplete = SyncBody(events(mode="missing_stop"))
        second_client, _ = mock_sync(monkeypatch, incomplete)
        with second_client:
            second = model()._stream([HumanMessage(content="second")])
            next(second)
            try:
                first_chunks = list(first)
                assert first_chunks[-1].message.response_metadata["stop_reason"] == "end_turn"
                with pytest.raises(ConsultantModelError, match="^incomplete_model_response$"):
                    list(second)
            finally:
                second.close()
                first.close()
            assert complete.closed and incomplete.closed


def test_interleaved_async_iterators_in_one_task_keep_own_terminal(monkeypatch):
    async def scenario():
        complete = AsyncBody(events())
        first_client, _ = mock_async(monkeypatch, complete)
        async with first_client:
            first = model()._astream([HumanMessage(content="first")])
            await anext(first)
            incomplete = AsyncBody(events(mode="missing_stop"))
            second_client, _ = mock_async(monkeypatch, incomplete)
            async with second_client:
                second = model()._astream([HumanMessage(content="second")])
                await anext(second)
                try:
                    first_chunks = [chunk async for chunk in first]
                    assert first_chunks[-1].message.response_metadata["stop_reason"] == "end_turn"
                    with pytest.raises(ConsultantModelError, match="^incomplete_model_response$"):
                        async for _ in second:
                            pass
                finally:
                    await second.aclose()
                    await first.aclose()
                assert complete.closed and incomplete.closed
    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["complete", "error"])
def test_response_cleanup_failure_does_not_replace_primary_error(monkeypatch, mode):
    body = SyncBody(events(mode=mode))
    client, _ = mock_sync(monkeypatch, body)
    original = httpx2.Response.close
    calls = {}

    def close(response):
        original(response)
        count = calls.get(id(response), 0) + 1
        calls[id(response)] = count
        # Complete EOF closes in HTTPX and SDK before our own final cleanup;
        # the error path has only the SDK close. Inject at our cleanup only.
        if count > (2 if mode == "complete" else 1):
            raise RuntimeError("synthetic private cleanup detail")

    monkeypatch.setattr(httpx2.Response, "close", close)
    error_type = ConsultantModelError if mode == "complete" else anthropic.APIStatusError
    with client, pytest.raises(error_type) as caught:
        model().invoke([HumanMessage(content="synthetic")])
    if mode == "complete":
        assert str(caught.value) == "model_response_cleanup_failed"
    else:
        assert caught.value.__notes__ == ["consultant_model_response_cleanup_failed"]
    assert "synthetic private cleanup detail" not in str(caught.value)
    assert body.closed


@pytest.mark.parametrize("mode", ["complete", "error"])
def test_async_response_cleanup_preserves_primary_error(monkeypatch, mode):
    async def scenario():
        body = AsyncBody(events(mode=mode))
        client, _ = mock_async(monkeypatch, body)
        original = httpx2.Response.aclose
        calls = {}

        async def close(response):
            await original(response)
            count = calls.get(id(response), 0) + 1
            calls[id(response)] = count
            if count > (2 if mode == "complete" else 1):
                raise RuntimeError("synthetic private cleanup detail")

        monkeypatch.setattr(httpx2.Response, "aclose", close)
        error_type = ConsultantModelError if mode == "complete" else anthropic.APIStatusError
        async with client:
            with pytest.raises(error_type) as caught:
                await model().ainvoke([HumanMessage(content="synthetic")])
        if mode == "complete":
            assert str(caught.value) == "model_response_cleanup_failed"
        else:
            assert caught.value.__notes__ == ["consultant_model_response_cleanup_failed"]
        assert "synthetic private cleanup detail" not in str(caught.value)
        assert body.closed
    asyncio.run(scenario())


def test_explicit_configuration_and_pinned_native_seam(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://not-the-target.invalid")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-the-synthetic-key")
    monkeypatch.setenv("ANTHROPIC_PROXY", "https://not-the-proxy.invalid")
    value = model()
    assert isinstance(value, ConfirmedChatAnthropic)
    assert value.anthropic_api_url == "https://api.anthropic.com"
    assert value.anthropic_api_key.get_secret_value() == "synthetic-not-a-key"
    assert value.anthropic_proxy is None
    assert value.streaming is True and value.stream_usage is True
    assert value.disable_streaming is False and value.max_retries == 0
    assert value.cache is False
    assert version("langchain-anthropic") == "1.7.2"
    assert version("anthropic") == "1.5.0"


@pytest.mark.parametrize("field,value", [
    ("model_name", ""), ("model_name", " "), ("api_key", ""),
    ("timeout", 0), ("timeout", float("inf")), ("timeout", True),
    ("max_tokens", 0), ("max_tokens", True),
])
def test_bad_explicit_configuration_rejected_without_client(field, value):
    config = {"model_name": "synthetic", "api_key": "synthetic", "timeout": 5, "max_tokens": 32}
    config[field] = value
    with pytest.raises(ConsultantModelError, match="^invalid_model_configuration$"):
        create_consultant_model(**config)
