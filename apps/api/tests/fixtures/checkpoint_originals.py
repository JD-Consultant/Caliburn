"""Synthetic native originals for deletion/fault tests, without running a Graph or model."""

from uuid import UUID, uuid4

import psycopg
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres import PostgresSaver

from caliburn.adapters.graph_checkpointer import create_graph_serializer


def save_step(
    connection: psycopg.Connection,
    job_file_id: UUID,
    execution_id: UUID,
    *,
    pending: bool = False,
) -> str:
    saver = PostgresSaver(connection, serde=create_graph_serializer())
    saver.setup()
    thread = f"{job_file_id}:{execution_id}:job_consultant:completed_work"
    request = {
        "request_id": uuid4(),
        "request_snapshot": {"model": "synthetic", "input": [{"role": "user", "content": "test"}]},
    }
    result = {"response_snapshot": {"id": "synthetic", "output": []}, "tool_results": []}
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = request if pending else {**request, **result}
    checkpoint["channel_versions"] = {key: 1 for key in checkpoint["channel_values"]}
    config = saver.put(
        {"configurable": {"thread_id": thread, "checkpoint_ns": ""}},
        checkpoint,
        {"source": "loop", "step": 0, "parents": {}},
        checkpoint["channel_versions"],
    )
    if pending:
        saver.put_writes(config, list(result.items()), "synthetic-result")
    return thread
