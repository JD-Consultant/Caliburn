"""Idempotently initialize LangGraph and consultant catalog storage."""

from __future__ import annotations

import asyncio
import sys

from app.adapters.langgraph.postgres import open_postgres_consultant_runtime
from app.config import settings


async def main() -> None:
    async with open_postgres_consultant_runtime(settings.database_url) as runtime:
        await runtime.setup()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
