"""HTTP 串流邊界的收尾故障；仍由真 SDK 解析所有合成 SSE。"""

import asyncio
from collections.abc import AsyncIterator

from tests.unit.modules.agent.offline_openai import EventStream


class TerminalStream(EventStream):
    def __init__(
        self,
        events: list[dict[str, object]],
        *,
        read_error: BaseException | None = None,
        close_error: BaseException | None = None,
        block_close: bool = False,
    ):
        super().__init__(events)
        self.read_error = read_error
        self.close_error = close_error
        self.block_close = block_close
        self.tail_read = False
        self.close_started = asyncio.Event()

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in super().__aiter__():
            yield chunk
        self.tail_read = True
        if self.read_error is not None:
            raise self.read_error

    async def aclose(self) -> None:
        await super().aclose()
        self.close_started.set()
        try:
            if self.block_close:
                await asyncio.Event().wait()
        finally:
            if self.close_error is not None:
                raise self.close_error
