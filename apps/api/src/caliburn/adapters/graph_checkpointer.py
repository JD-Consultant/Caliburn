"""Configure the official checkpoint serializer; payload allowlists belong to callers."""

from collections.abc import Iterable
from uuid import UUID

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg import AsyncConnection
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def create_graph_serializer(*, allowed_types: Iterable[type[object]] = ()) -> JsonPlusSerializer:
    """Allow only the supplied custom types in addition to framework-safe types.

    Callers must enumerate nested dataclasses and enums as well as the outer
    payload. UUID and frozenset already belong to the framework's safe set.
    Checkpoint 4.2.0 returns raw dicts/values for blocked constructors, and may
    return None when reconstruction fails; it does not always raise. Validate
    the restored payload's nested types before executing a prepared command.

    Native tuples decode as lists even when tuple is allowlisted. Use a State
    shape that accepts this framework behavior; this factory adds no codec,
    implicit domain registry, or pickle fallback. Legacy JSON custom
    constructors remain disabled independently of the msgpack allowlist.
    """
    return JsonPlusSerializer(
        pickle_fallback=False,
        allowed_json_modules=None,
        allowed_msgpack_modules=tuple(allowed_types),
    )


async def delete_job_file_checkpoints(session: AsyncSession, job_file_id: UUID) -> None:
    """Use the native saver on the caller's transaction, never a second committing pool."""
    thread_ids = await session.scalars(
        text(
            "SELECT thread_id FROM checkpoints WHERE thread_id LIKE :prefix "
            "UNION SELECT thread_id FROM checkpoint_blobs WHERE thread_id LIKE :prefix "
            "UNION SELECT thread_id FROM checkpoint_writes WHERE thread_id LIKE :prefix"
        ),
        {"prefix": f"{job_file_id}:%"},
    )
    connection = await session.connection()
    raw_connection = await connection.get_raw_connection()
    driver = raw_connection.driver_connection
    if not isinstance(driver, AsyncConnection):
        raise RuntimeError("Checkpoint deletion requires the configured psycopg driver")
    saver = AsyncPostgresSaver(driver)
    for thread_id in thread_ids:
        await saver.adelete_thread(thread_id)
