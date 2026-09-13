"""Bounded terminal-event check around the pinned native Anthropic adapter.

Pinned seams: langchain-anthropic 1.7.2 / anthropic 1.5.0. Both native stream
methods send all SDK events through _make_message_chunk_from_anthropic_event.
The _create/_acreate hook only retains the native HTTP response for explicit
close on early exit: closing the adapter generator alone does not close it.
These private hooks require upgrade tests. Context is installed only while
advancing or closing our native iterator, never across a yield to its caller.
The native SDK/parser and all tool, thinking, usage and message conversion
remain unchanged.

Completion here proves a stream reached its provider terminal event, not that
the model understood the input, a tool succeeded, or a checkpoint was saved.
The caller still validates the final response and owns durable publication.
"""

from collections.abc import AsyncIterator, Iterator
from contextvars import ContextVar
from dataclasses import dataclass
import math
from typing import Any

import anthropic
import httpx2
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGenerationChunk


class ConsultantModelError(ValueError):
    """Fixed local diagnostic; never includes model inputs or credentials."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(slots=True)
class _StreamCompletion:
    terminal: bool = False
    response: httpx2.Response | None = None


_completion: ContextVar[_StreamCompletion | None] = ContextVar(
    "jd_consultant_stream_completion", default=None,
)


class ConfirmedChatAnthropic(ChatAnthropic):
    """Native streaming with per-iterator evidence of message_stop."""

    def _stream(
        self, messages: list[BaseMessage], *args: Any, **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        completion = _StreamCompletion()
        stream = super()._stream(messages, *args, **kwargs)
        failure: BaseException | None = None
        try:
            while True:
                token = _completion.set(completion)
                try:
                    chunk = next(stream)
                except StopIteration:
                    break
                finally:
                    _completion.reset(token)
                yield chunk
            if not completion.terminal:
                raise ConsultantModelError("incomplete_model_response")
        except BaseException as error:
            failure = error
            raise
        finally:
            token = _completion.set(completion)
            cleanup_error: BaseException | None = None
            try:
                try:
                    stream.close()
                except BaseException as error:
                    cleanup_error = error
                try:
                    if completion.response is not None:
                        completion.response.close()
                except BaseException as error:
                    if cleanup_error is None or not isinstance(error, Exception):
                        cleanup_error = error
                if cleanup_error is not None:
                    if failure is None:
                        if not isinstance(cleanup_error, Exception):
                            raise cleanup_error
                        raise ConsultantModelError("model_response_cleanup_failed") from None
                    failure.add_note("consultant_model_response_cleanup_failed")
            finally:
                _completion.reset(token)

    async def _astream(
        self, messages: list[BaseMessage], *args: Any, **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        completion = _StreamCompletion()
        stream = super()._astream(messages, *args, **kwargs)
        failure: BaseException | None = None
        try:
            while True:
                token = _completion.set(completion)
                try:
                    chunk = await anext(stream)
                except StopAsyncIteration:
                    break
                finally:
                    _completion.reset(token)
                yield chunk
            if not completion.terminal:
                raise ConsultantModelError("incomplete_model_response")
        except BaseException as error:
            failure = error
            raise
        finally:
            token = _completion.set(completion)
            cleanup_error: BaseException | None = None
            try:
                try:
                    await stream.aclose()
                except BaseException as error:
                    cleanup_error = error
                try:
                    if completion.response is not None:
                        await completion.response.aclose()
                except BaseException as error:
                    if cleanup_error is None or not isinstance(error, Exception):
                        cleanup_error = error
                if cleanup_error is not None:
                    if failure is None:
                        if not isinstance(cleanup_error, Exception):
                            raise cleanup_error
                        raise ConsultantModelError("model_response_cleanup_failed") from None
                    failure.add_note("consultant_model_response_cleanup_failed")
            finally:
                _completion.reset(token)

    def _create(self, payload: dict) -> Any:
        response = super()._create(payload)
        completion = _completion.get()
        if payload.get("stream") and completion is not None:
            completion.response = response.http_response
        return response

    async def _acreate(self, payload: dict) -> Any:
        response = await super()._acreate(payload)
        completion = _completion.get()
        if payload.get("stream") and completion is not None:
            completion.response = response.http_response
        return response

    def _make_message_chunk_from_anthropic_event(
        self,
        event: anthropic.types.RawMessageStreamEvent,
        **kwargs: Any,
    ) -> tuple[AIMessageChunk | None, anthropic.types.RawMessageStreamEvent | None]:
        result = super()._make_message_chunk_from_anthropic_event(event, **kwargs)
        completion = _completion.get()
        if event.type == "message_stop" and completion is not None:
            completion.terminal = True
        return result


def create_consultant_model(
    *, model_name: str, api_key: str, timeout: float, max_tokens: int,
) -> ConfirmedChatAnthropic:
    """Build from explicit caller inputs; no configuration or environment lookup.

    The official endpoint, no proxy, no cache and no implicit retry are fixed.
    Scope/run ownership, request context and checkpoint persistence belong to
    the application runtime; they are not model parameters.
    """
    if (
        any(type(value) is not str or not value.strip() or "\0" in value
            for value in (model_name, api_key))
        or type(timeout) not in (int, float)
        or not math.isfinite(timeout) or timeout <= 0
        or type(max_tokens) is not int or max_tokens <= 0
    ):
        raise ConsultantModelError("invalid_model_configuration")
    return ConfirmedChatAnthropic(
        model=model_name,
        api_key=api_key,
        base_url="https://api.anthropic.com",
        anthropic_proxy=None,
        timeout=timeout,
        max_tokens=max_tokens,
        streaming=True,
        stream_usage=True,
        disable_streaming=False,
        max_retries=0,
        cache=False,
        output_version=None,
    )
