"""Framework-native PostgreSQL runtime for the isolated read-path spike."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

import psycopg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.store.base import AEmbeddingsFunc
from langgraph.store.postgres.aio import AsyncPostgresStore

from memory_read_spike.contracts import (
    MemoryHit,
    SearchSemanticMemoryResult,
)
from memory_read_spike.embeddings import EMBEDDING_DIMENSIONS
from memory_read_spike.fixtures import SemanticMemoryFixture
from memory_read_spike.scope import TrustedReadScope
from memory_read_spike.settings import DatabaseIdentityError, SpikeSettings


class SemanticIndexUnavailableError(RuntimeError):
    pass


@dataclass
class SpikeRuntime:
    saver: AsyncPostgresSaver
    store: AsyncPostgresStore
    graph: Any


async def _read_current_database(connection_string: str) -> str:
    async with await psycopg.AsyncConnection.connect(
        connection_string,
        autocommit=True,
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT current_database()")
            row = await cursor.fetchone()
    if row is None:
        raise RuntimeError("database identity query returned no row")
    return str(row[0])


def _build_canonical_graph(saver: AsyncPostgresSaver):
    builder = StateGraph(MessagesState)
    builder.add_node("persist", lambda _state: {})
    builder.add_edge(START, "persist")
    builder.add_edge("persist", END)
    return builder.compile(checkpointer=saver)


async def _stop_store_background_task(store: AsyncPostgresStore) -> None:
    """Close the pinned Store batch task, which has no public close API."""
    task = store._task  # noqa: SLF001 -- pinned framework lifecycle gap
    if task is not None:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@asynccontextmanager
async def open_spike_runtime(
    settings: SpikeSettings,
    *,
    embed: AEmbeddingsFunc,
) -> AsyncIterator[SpikeRuntime]:
    actual_database = await _read_current_database(settings.connection_string)
    if actual_database != settings.expected_database:
        raise DatabaseIdentityError(
            expected=settings.expected_database,
            actual=actual_database,
        )

    async with AsyncPostgresSaver.from_conn_string(
        settings.connection_string,
    ) as saver:
        async with AsyncPostgresStore.from_conn_string(
            settings.connection_string,
            index={
                "dims": EMBEDDING_DIMENSIONS,
                "embed": embed,
                "fields": ["title", "content"],
            },
        ) as store:
            try:
                await saver.setup()
                await store.setup()
                yield SpikeRuntime(
                    saver=saver,
                    store=store,
                    graph=_build_canonical_graph(saver),
                )
            finally:
                await _stop_store_background_task(store)


async def seed_current_memories(
    runtime: SpikeRuntime,
    scope: TrustedReadScope,
    memories: tuple[SemanticMemoryFixture, ...],
) -> None:
    for memory in memories:
        await runtime.store.aput(
            scope.semantic_namespace,
            memory.memory_id,
            memory.model_dump(mode="json"),
        )


async def search_current_memories(
    runtime: Any,
    scope: TrustedReadScope,
    query: str,
) -> SearchSemanticMemoryResult:
    if not getattr(runtime.store, "index_config", None):
        raise SemanticIndexUnavailableError("semantic index is not configured")
    rows = await runtime.store.asearch(
        scope.semantic_namespace,
        query=query,
        limit=4,
    )
    exact_rows = [row for row in rows if row.namespace == scope.semantic_namespace]
    return SearchSemanticMemoryResult(
        memories=tuple(
            MemoryHit.model_validate(
                {
                    "title": row.value["title"],
                    "content": row.value["content"],
                    "message_refs": row.value["message_refs"],
                }
            )
            for row in exact_rows
        )
    )
