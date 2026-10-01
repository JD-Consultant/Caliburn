from __future__ import annotations

import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from memory_read_spike.canonical import (
    append_canonical_round,
    latest_canonical_messages,
)
from memory_read_spike.embeddings import DeterministicEmbeddingSpy
from memory_read_spike.fixtures import load_canonical_rounds
from memory_read_spike.runtime import open_spike_runtime
from memory_read_spike.scope import TrustedReadScope
from memory_read_spike.settings import SpikeSettings


TABLES = ("checkpoints", "checkpoint_writes", "checkpoint_blobs")


def _settings() -> SpikeSettings:
    return SpikeSettings(
        database_url=os.environ["MEMORY_ROUTING_SPIKE_DATABASE_URL"],
        expected_database=os.environ["MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE"],
        production_database_url=os.environ.get("DATABASE_URL"),
    )


def _rounds(count: int, repetition: int) -> tuple[tuple[HumanMessage, AIMessage], ...]:
    source = load_canonical_rounds()
    return tuple(
        (
            HumanMessage(
                id=f"growth-{count}-{repetition}-h-{index:03d}",
                content=f"{source[index % len(source)][0].content}（量測 {index + 1}）",
            ),
            AIMessage(
                id=f"growth-{count}-{repetition}-a-{index:03d}",
                content=f"{source[index % len(source)][1].content}（量測 {index + 1}）",
            ),
        )
        for index in range(count)
    )


async def _table_metrics(
    settings: SpikeSettings,
    *,
    thread_id: str,
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    async with await psycopg.AsyncConnection.connect(
        settings.connection_string,
        autocommit=True,
    ) as connection:
        async with connection.cursor() as cursor:
            for table in TABLES:
                await cursor.execute(
                    f"SELECT count(*), coalesce(sum(pg_column_size(t)), 0) "
                    f"FROM {table} AS t WHERE thread_id = %s",
                    (thread_id,),
                )
                row = await cursor.fetchone()
                assert row is not None
                result[table] = {"rows": int(row[0]), "row_bytes": int(row[1])}
    return result


@pytest.mark.asyncio
async def test_checkpoint_growth_is_measured_per_thread_without_assumed_threshold(
) -> None:
    settings = _settings()
    observations: list[dict[str, Any]] = []

    for round_count in (40, 100, 200):
        for repetition in range(1, 4):
            scope = TrustedReadScope(
                run_id=uuid4(),
                document_id=uuid4(),
                thread_id=f"growth-{round_count}-{repetition}-{uuid4()}",
            )
            rounds = _rounds(round_count, repetition)
            expected = tuple(message for pair in rounds for message in pair)
            append_round_wall_seconds: list[float] = []

            async with open_spike_runtime(
                settings,
                embed=DeterministicEmbeddingSpy(),
            ) as runtime:
                for human, assistant in rounds:
                    started = perf_counter()
                    await append_canonical_round(runtime, scope, human, assistant)
                    append_round_wall_seconds.append(perf_counter() - started)

            async with open_spike_runtime(
                settings,
                embed=DeterministicEmbeddingSpy(),
            ) as restarted:
                started = perf_counter()
                actual = await latest_canonical_messages(restarted, scope)
                read_wall_seconds = perf_counter() - started

            assert [type(message) for message in actual] == [
                type(message) for message in expected
            ]
            assert [message.id for message in actual] == [
                message.id for message in expected
            ]
            assert [message.content for message in actual] == [
                message.content for message in expected
            ]

            checkpoint_thread_id = scope.checkpoint_config["configurable"]["thread_id"]
            tables = await _table_metrics(
                settings,
                thread_id=checkpoint_thread_id,
            )
            assert all(metric["rows"] > 0 for metric in tables.values())
            assert len(append_round_wall_seconds) == round_count
            observations.append(
                {
                    "round_count": round_count,
                    "repetition": repetition,
                    "message_count": len(actual),
                    "append_round_wall_seconds": append_round_wall_seconds,
                    "restart_read_wall_seconds": read_wall_seconds,
                    "tables": tables,
                }
            )

    output = (
        Path(__file__).resolve().parents[1]
        / "trials"
        / ".storage-growth-observations.tmp.json"
    )
    output.write_text(
        json.dumps({"observations": observations}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert len(loaded["observations"]) == 9
    assert {
        (item["round_count"], item["repetition"])
        for item in loaded["observations"]
    } == {(count, repetition) for count in (40, 100, 200) for repetition in range(1, 4)}
    assert all(
        len(item["append_round_wall_seconds"]) == item["round_count"]
        for item in loaded["observations"]
    )
    assert all("verdict" not in item for item in loaded["observations"])
