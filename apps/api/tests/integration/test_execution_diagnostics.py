"""Real saver payloads, transactional refresh and SQL browsing in a disposable PG schema."""

from uuid import uuid4

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres import PostgresSaver

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.diagnostics.refresh import refresh_diagnostics

pytestmark = pytest.mark.postgres


def seed(connection, *, kind="consultant_turn"):
    job_id, execution_id = uuid4(), uuid4()
    connection.execute(
        "INSERT INTO job_files (job_file_id,creation_command_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,%s,'合成測試','合成測試','測試員工')",
        (job_id, uuid4()),
    )
    connection.execute(
        "INSERT INTO executions (job_file_id,execution_id,kind,status) "
        "VALUES (%s,%s,%s,'completed')",
        (job_id, execution_id, kind),
    )
    return job_id, execution_id


def save_step(connection, job_id, execution_id, role="job_consultant", *, pending=False):
    saver = PostgresSaver(connection, serde=create_graph_serializer())
    saver.setup()
    thread = f"{job_id}:{execution_id}:{role}:completed_work"
    if role != "job_consultant":
        thread += f":stage:{uuid4()}:{uuid4()}"
    checkpoint = empty_checkpoint()
    values = {
        "request_snapshot": {"model": "synthetic", "input": [{"role": "user", "content": "盤點"}]},
        "response_snapshot": {
            "id": "response_same",
            "status": "completed",
            "output": [
                {
                    "type": "reasoning",
                    "encrypted_content": "private",
                    "summary": [{"text": "摘要"}],
                },
                {
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "read_jd",
                    "arguments": "{}",
                },
                {
                    "type": "function_call",
                    "call_id": "call_2",
                    "name": "revise_jd",
                    "arguments": "{}",
                },
            ],
        },
        "tool_results": [{"type": "function_call_output", "call_id": "call_2", "output": ""}],
    }
    checkpoint["channel_values"] = (
        values if not pending else {"request_snapshot": values["request_snapshot"]}
    )
    checkpoint["channel_versions"] = {key: 1 for key in checkpoint["channel_values"]}
    config = saver.put(
        {"configurable": {"thread_id": thread, "checkpoint_ns": ""}},
        checkpoint,
        {"source": "loop", "step": 0, "parents": {}},
        checkpoint["channel_versions"],
    )
    if pending:
        saver.put_writes(
            config,
            [(key, value) for key, value in values.items() if key != "request_snapshot"],
            "model-task",
        )
    return thread


def test_refresh_replaces_only_selected_file_and_views_preserve_results(
    database_settings, database_connection
):
    connection = database_connection
    job_id, execution_id = seed(connection)
    other_job, other_execution = seed(connection)
    save_step(connection, job_id, execution_id)
    save_step(connection, other_job, other_execution)
    for _ in range(2):
        assert refresh_diagnostics(database_settings, job_file_id=job_id) == 1
    assert connection.execute("SELECT count(*) FROM diagnostic_execution_snapshots").fetchone() == (
        1,
    )
    assert connection.execute("SELECT execution_id FROM diagnostic_model_steps").fetchone() == (
        execution_id,
    )
    calls = connection.execute(
        "SELECT call_id,result_state,tool_output FROM diagnostic_tool_calls ORDER BY output_index"
    ).fetchall()
    assert calls == [("call_1", "not_recorded", None), ("call_2", "recorded", "")]
    step = connection.execute("SELECT request,response FROM diagnostic_model_steps").fetchone()
    assert step[0]["input"][0]["content"] == "盤點"
    assert step[1]["output"][0]["encrypted_content"] == "[redacted]"
    assert connection.execute("SELECT count(*) FROM diagnostic_execution_history").fetchone() == (
        2,
    )
    assert connection.execute(
        "SELECT snapshot_at FROM diagnostic_execution_history WHERE execution_id=%s",
        (other_execution,),
    ).fetchone() == (None,)
    assert connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (0,)


def test_memory_roles_and_pending_writes_are_not_lost(database_settings, database_connection):
    job_id, execution_id = seed(database_connection, kind="memory_batch")
    for role in ("work_situation_analyst", "work_understanding_analyst"):
        save_step(database_connection, job_id, execution_id, role, pending=True)
    assert refresh_diagnostics(database_settings, execution_id=execution_id) == 1
    assert database_connection.execute(
        "SELECT role,source FROM diagnostic_model_steps ORDER BY role"
    ).fetchall() == [
        ("work_situation_analyst", "pending_write"),
        ("work_understanding_analyst", "pending_write"),
    ]


def test_zero_response_is_inspected_and_bad_refresh_keeps_previous_copy(
    database_settings, database_connection
):
    connection = database_connection
    job_id, execution_id = seed(connection)
    saver = PostgresSaver(connection, serde=create_graph_serializer())
    saver.setup()
    assert refresh_diagnostics(database_settings, execution_id=execution_id) == 1
    before = connection.execute(
        "SELECT snapshot_at,steps FROM diagnostic_execution_snapshots"
    ).fetchone()
    assert before[1] == []
    assert connection.execute(
        "SELECT saved_response_count FROM diagnostic_execution_history"
    ).fetchone() == (0,)
    # A corrupt native original must abort, not replace the usable inspection with an empty success.
    thread = save_step(connection, job_id, execution_id)
    connection.execute(
        "UPDATE checkpoint_blobs SET blob=%s WHERE thread_id=%s AND channel='response_snapshot'",
        (b"invalid-msgpack", thread),
    )
    with pytest.raises((ValueError, TypeError)):
        refresh_diagnostics(database_settings, execution_id=execution_id)
    assert (
        connection.execute(
            "SELECT snapshot_at,steps FROM diagnostic_execution_snapshots"
        ).fetchone()
        == before
    )


def test_overview_does_not_multiply_independent_child_counts(
    database_settings, database_connection
):
    connection = database_connection
    job_id, execution_id = seed(connection)
    save_step(connection, job_id, execution_id)
    # No runtime calls: seed persisted diagnostic evidence and real attempt records independently.
    connection.execute(
        "INSERT INTO execution_budgets VALUES (%s,64,4,512,8,now()+interval '1 hour',NULL,'test')",
        (execution_id,),
    )
    for _ in range(3):
        connection.execute(
            "INSERT INTO execution_outbound_attempts "
            "(execution_id,attempt_id,request_id,kind,fingerprint,writer_id,reserved_cost_usd) "
            "VALUES (%s,%s,%s,'model',%s,%s,0.01)",
            (execution_id, uuid4(), uuid4(), "a" * 64, uuid4()),
        )
    refresh_diagnostics(database_settings, job_file_id=job_id)
    assert connection.execute(
        "SELECT saved_response_count,model_attempt_count FROM diagnostic_execution_history"
    ).fetchone() == (1, 3)
    assert connection.execute("SELECT count(*) FROM diagnostic_tool_calls").fetchone() == (2,)


def test_requires_one_explicit_scope(database_settings):
    with pytest.raises(ValueError):
        refresh_diagnostics(database_settings)
    with pytest.raises(ValueError):
        refresh_diagnostics(database_settings, job_file_id=uuid4(), execution_id=uuid4())
    with pytest.raises(ValueError, match="not found"):
        refresh_diagnostics(database_settings, execution_id=uuid4())


def test_overview_interview_text_uses_same_redaction_without_changing_originals(
    database_settings, database_connection
):
    connection = database_connection
    job_id, execution_id = seed(connection)
    original = '{"password":"synthetic-secret"}'
    input_id, reply_id = uuid4(), uuid4()
    for source_id, speaker in ((input_id, "employee"), (reply_id, "consultant")):
        connection.execute(
            "INSERT INTO interview_texts (source_id,job_file_id,speaker,interview_text) "
            "VALUES (%s,%s,%s,%s)",
            (source_id, job_id, speaker, original),
        )
    connection.execute(
        "INSERT INTO interview_inputs VALUES (%s,%s,%s,%s)",
        (job_id, uuid4(), input_id, execution_id),
    )
    connection.execute(
        "INSERT INTO interview_replies VALUES (%s,%s,%s)", (job_id, execution_id, reply_id)
    )
    save_step(connection, job_id, execution_id)
    refresh_diagnostics(database_settings, execution_id=execution_id)
    texts = connection.execute(
        "SELECT employee_input,final_reply FROM diagnostic_execution_history"
    ).fetchone()
    assert all("synthetic-secret" not in text and "[redacted]" in text for text in texts)
    assert connection.execute(
        "SELECT interview_text FROM interview_texts WHERE source_id=%s", (input_id,)
    ).fetchone() == (original,)
