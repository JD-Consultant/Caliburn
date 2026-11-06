"""管理官方 PostgreSQL pool／saver，接入 SDK 欄位存在性適配。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import get_args

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from openai.types.responses import (
    CompactedResponse,
    ParsedResponse,
    ParsedResponseFunctionToolCall,
    ParsedResponseOutputMessage,
    ParsedResponseOutputText,
    ResponseOutputItem,
)
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from caliburn.modules.agent.infrastructure.persistence.openai_field_sets import (
    OpenAIFieldSetSerializer,
)


def openai_checkpoint_serializer() -> JsonPlusSerializer:
    """只允許官方 output union、完整 C 及串流實際產生的 parsed 類別。"""
    output_types = get_args(get_args(ResponseOutputItem)[0])
    return OpenAIFieldSetSerializer(
        allowed_msgpack_modules=output_types
    ).with_msgpack_allowlist(
        (
            CompactedResponse,
            ParsedResponse,
            ParsedResponseFunctionToolCall,
            ParsedResponseOutputMessage,
            ParsedResponseOutputText,
        )
    )


@asynccontextmanager
async def open_postgres_checkpointer(
    conninfo: str,
    *,
    initialize: bool = False,
    serde: JsonPlusSerializer | None = None,
) -> AsyncIterator[AsyncPostgresSaver]:
    """啟動時借出 saver；首次初始化／升級明示 setup，退出時關閉自有 pool。"""
    async with AsyncConnectionPool[AsyncConnection[DictRow]](
        conninfo,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    ) as pool:
        await pool.wait()
        saver = AsyncPostgresSaver(pool, serde=serde or openai_checkpoint_serializer())
        if initialize:
            await saver.setup()
        yield saver
