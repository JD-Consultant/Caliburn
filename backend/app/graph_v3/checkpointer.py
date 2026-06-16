from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


def _to_psycopg_dsn(url: str) -> str:
    # 接受 sqlalchemy 風格 → 轉成 psycopg 可用 dsn
    return url.replace("postgresql+asyncpg://", "postgresql://").replace("+psycopg", "")


@asynccontextmanager
async def open_pg_checkpointer(database_url: str):
    dsn = _to_psycopg_dsn(database_url)
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()
        yield saver
