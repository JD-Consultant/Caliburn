"""The native framework reader borrows the caller's transaction without replay."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import text

from caliburn.adapters.database import consistent_read_session
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.native_checkpoint_reads import read_native_records

pytestmark = pytest.mark.postgres

constructed = 0


@dataclass
class PreparedOriginal:
    body: str

    def __post_init__(self):
        global constructed
        constructed += 1


def seed(connection):
    saver = PostgresSaver(
        connection, serde=create_graph_serializer(allowed_types=[PreparedOriginal])
    )
    saver.setup()
    thread = f"synthetic:{uuid4()}"
    request_id = uuid4()
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {
        "request_id": request_id,
        "request_snapshot": {"input": []},
        "prepared_tool": PreparedOriginal("not executable"),
        "bytes": b"not public JSON",
    }
    checkpoint["channel_versions"] = {key: "1" for key in checkpoint["channel_values"]}
    config = saver.put(
        {"configurable": {"thread_id": thread, "checkpoint_ns": ""}},
        checkpoint,
        {"source": "loop", "step": 0, "parents": {}},
        checkpoint["channel_versions"],
    )
    saver.put_writes(config, [("tool_results", [{"call_id": "a", "output": ""}])], "task_a")
    saver.put_writes(config, [("response_snapshot", {"id": "resp_b", "output": []})], "task_b")
    return thread, request_id


def test_official_reader_borrows_same_readonly_transaction_and_preserves_pending_tasks(
    client, database_connection, monkeypatch
):
    global constructed
    thread, request_id = seed(database_connection)
    constructed = 0
    observed = []
    original = AsyncPostgresSaver.alist

    async def inspect(saver, config, **kwargs):
        async with saver.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT pg_backend_pid(),current_setting('transaction_isolation'),"
                "current_setting('transaction_read_only')"
            )
            observed.append(await cursor.fetchone())
        assert config == {"configurable": {"thread_id": thread, "checkpoint_ns": ""}}
        async for saved in original(saver, config, **kwargs):
            yield saved

    monkeypatch.setattr(AsyncPostgresSaver, "alist", inspect)

    async def read():
        async with consistent_read_session(client.app.state.database.sessions) as session:
            pid = await session.scalar(text("SELECT pg_backend_pid()"))
            result = await read_native_records(
                session,
                threads={thread: "synthetic"},
                channels=("request_id", "request_snapshot", "response_snapshot", "tool_results"),
            )
            assert await session.scalar(text("SELECT pg_backend_pid()")) == pid
            return pid, result

    pid, records = client.portal.call(read)
    assert observed == [(pid, "repeatable read", "on")]
    assert constructed == 0
    assert len(records) == 3
    assert records[0]["values"]["request_id"] == str(request_id)
    tasks = {
        record["task_id"]: record["values"]
        for record in records
        if record["source"] == "pending_write"
    }
    assert "response_snapshot" not in tasks["task_a"]
    assert "tool_results" not in tasks["task_b"]
    assert tasks["task_a"]["tool_results"][0]["output"] == ""


def test_missing_selected_blob_fails_instead_of_becoming_an_empty_observation(
    client, database_connection
):
    thread, _ = seed(database_connection)
    database_connection.execute(
        "DELETE FROM checkpoint_blobs WHERE thread_id=%s AND channel='request_snapshot'",
        (thread,),
    )

    async def read():
        async with consistent_read_session(client.app.state.database.sessions) as session:
            return await read_native_records(
                session, threads={thread: "synthetic"}, channels=("request_snapshot",)
            )

    with pytest.raises(ValueError, match="referenced checkpoint channel blob is missing"):
        client.portal.call(read)


@pytest.mark.parametrize(
    "case", ["null_version", "inline_null", "empty", "unselected", "other_namespace"]
)
def test_missing_blob_guard_keeps_legal_empty_and_unselected_cases(
    client, database_connection, case
):
    thread, _ = seed(database_connection)
    if case == "null_version":
        database_connection.execute(
            "UPDATE checkpoints SET checkpoint=jsonb_set(checkpoint,"
            "'{channel_versions,request_snapshot}','null') WHERE thread_id=%s",
            (thread,),
        )
    elif case == "inline_null":
        database_connection.execute(
            "UPDATE checkpoints SET checkpoint=jsonb_set(checkpoint,"
            "'{channel_values,request_snapshot}','null') WHERE thread_id=%s",
            (thread,),
        )
    if case == "empty":
        database_connection.execute(
            "UPDATE checkpoint_blobs SET type='empty',blob=NULL "
            "WHERE thread_id=%s AND channel='request_snapshot'",
            (thread,),
        )
    elif case == "other_namespace":
        database_connection.execute(
            "INSERT INTO checkpoints(thread_id,checkpoint_ns,checkpoint_id,parent_checkpoint_id,"
            "type,checkpoint,metadata) SELECT thread_id,'foreign',checkpoint_id,"
            "parent_checkpoint_id,type,checkpoint,metadata FROM checkpoints WHERE thread_id=%s",
            (thread,),
        )
    else:
        channel = "prepared_tool" if case == "unselected" else "request_snapshot"
        database_connection.execute(
            "DELETE FROM checkpoint_blobs WHERE thread_id=%s AND channel=%s",
            (thread, channel),
        )

    async def read():
        async with consistent_read_session(client.app.state.database.sessions) as session:
            return await read_native_records(
                session, threads={thread: "synthetic"}, channels=("request_snapshot",)
            )

    records = client.portal.call(read)
    assert len(records) == 1
    if case in {"null_version", "empty"}:
        assert "request_snapshot" not in records[0]["values"]
    elif case == "inline_null":
        assert records[0]["values"]["request_snapshot"] is None
    else:
        assert records[0]["values"]["request_snapshot"] == {"input": []}
