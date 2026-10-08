"""Original bytes, caller-owned iterator cleanup and exactly-once observation."""

import asyncio
import json
import sys
from pathlib import Path

import httpx2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from append_stream import OwnedObservedStream as Stream  # noqa: E402


class Original(httpx2.AsyncByteStream):
    def __init__(self, chunks, *, read_error=False, close_error=False):
        self.chunks = chunks
        self.read_error = read_error
        self.close_error = close_error
        self.finalized = 0
        self.closed = 0

    async def __aiter__(self):
        try:
            for chunk in self.chunks:
                yield chunk
            if self.read_error:
                raise RuntimeError("read failed")
            await asyncio.Event().wait()
        finally:
            self.finalized += 1

    async def aclose(self):
        self.closed += 1
        if self.close_error:
            raise RuntimeError("close failed")


def terminal():
    body = {"id": "r", "usage": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3}}
    chunk = ("data: " + json.dumps({"type": "response.completed", "response": body}) + "\n\n").encode()
    return body, chunk


def test_early_terminal_close_finalizes_owned_original_iterator_and_preserves_bytes():
    body, chunk = terminal()
    observed = []
    original = Original([chunk])
    stream = Stream(original, observed.append)

    async def run():
        iterator = stream.__aiter__()
        try:
            assert await anext(iterator) == chunk
            await stream.aclose()
            assert original.finalized == 1
            assert original.closed == 1
            assert observed == [body]
        finally:
            await iterator.aclose()

    asyncio.run(run())


def test_unknown_read_error_is_observed_once_even_if_close_repeats():
    observed = []
    original = Original([b"data: [DONE]\n\n"], read_error=True)
    stream = Stream(original, observed.append)

    async def run():
        iterator = stream.__aiter__()
        await anext(iterator)
        with pytest.raises(RuntimeError, match="read failed"):
            await anext(iterator)
        await stream.aclose()
        await stream.aclose()
        assert observed == [None]
        assert original.closed == 1

    asyncio.run(run())


def test_terminal_usage_survives_close_failure_without_unknown_reobservation():
    body, chunk = terminal()
    observed = []
    original = Original([chunk], close_error=True)
    stream = Stream(original, observed.append)

    async def run():
        iterator = stream.__aiter__()
        try:
            await anext(iterator)
            with pytest.raises(RuntimeError, match="close failed"):
                await stream.aclose()
            assert observed == [body]
            assert original.finalized == 1
        finally:
            await iterator.aclose()

    asyncio.run(run())


def test_split_and_multiple_sse_events_keep_every_original_byte_and_terminal():
    body, last = terminal()
    created = b'data: {"type":"response.created","response":{"id":"r"}}\n\n'
    wire = created + last + b"data: [DONE]\n\n"
    chunks = [wire[:8], wire[8:47], wire[47:51], wire[51:]]
    original = Original(chunks)
    observed = []
    stream = Stream(original, observed.append)

    async def run():
        iterator = stream.__aiter__()
        received = [await anext(iterator) for _ in chunks]
        assert received == chunks
        await stream.aclose()
        assert observed == [body]
        assert original.finalized == 1

    asyncio.run(run())


def test_cancellation_before_terminal_keeps_one_unknown_observation():
    original = Original([b"data: [DONE]\n\n"])
    observed = []
    stream = Stream(original, observed.append)

    async def run():
        iterator = stream.__aiter__()
        await anext(iterator)
        task = asyncio.create_task(anext(iterator))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await stream.aclose()
        await stream.aclose()
        assert observed == [None]
        assert original.closed == 1 and original.finalized == 1

    asyncio.run(run())


def test_terminal_then_double_close_observes_original_usage_once():
    body, chunk = terminal()
    original = Original([chunk])
    observed = []
    stream = Stream(original, observed.append)

    async def run():
        await anext(stream.__aiter__())
        await stream.aclose()
        await stream.aclose()
        assert observed == [body]
        assert original.closed == 1 and original.finalized == 1

    asyncio.run(run())
