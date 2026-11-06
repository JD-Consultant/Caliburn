"""完整消費公開 Agent 串流，保留其中例外供測例斷言。"""

from collections.abc import AsyncIterator


async def consume(events: AsyncIterator[object]) -> None:
    async for _ in events:
        pass
