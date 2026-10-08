"""Transparent observer that owns its consumed iterator through explicit close.

Used only by the new append batch. Original chunks pass to the SDK unchanged;
the observer creates no additional yield-based async generator of its own.
"""

import json

import httpx2


class OwnedObservedStream(httpx2.AsyncByteStream):
    def __init__(self, original, observer):
        self.original = original
        self.observer = observer
        self.pending = b""
        self.terminal = False
        self._iterator = None
        self._closed = False
        self._observed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._closed:
            raise StopAsyncIteration
        if self._iterator is None:
            self._iterator = self.original.__aiter__()
        chunk = await anext(self._iterator)
        self.pending += chunk
        while b"\n" in self.pending:
            line, self.pending = self.pending.split(b"\n", 1)
            if line.startswith(b"data: ") and line[6:].strip() != b"[DONE]":
                event = json.loads(line[6:])
                if event.get("type") in {
                    "response.completed",
                    "response.incomplete",
                    "response.failed",
                }:
                    self._observe(event["response"])
                elif isinstance(event.get("error"), dict):
                    self._observe(
                        {
                            "error": {"code": event["error"].get("code")},
                            "error_event_keys": list(event),
                        }
                    )
                elif event.get("type") == "error":
                    self._observe({"error": {"code": event.get("code")}})
        return chunk

    def _observe(self, body):
        if not self._observed:
            self._observed = True
            self.terminal = body is not None
            self.observer(body)

    async def aclose(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self._iterator is not None and self._iterator is not self.original:
                close = getattr(self._iterator, "aclose", None)
                if close is not None:
                    await close()
        finally:
            try:
                await self.original.aclose()
            finally:
                if not self._observed:
                    self._observe(None)
