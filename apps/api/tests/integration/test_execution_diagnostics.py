"""Real saver payloads, transactional refresh and SQL browsing in a disposable PG schema."""

import json
import runpy
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres import PostgresSaver

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.diagnostics.refresh import refresh_diagnostics
from tests.integration.test_memory_position_storage import (
    batch_position as batch_position,
)
from tests.integration.test_memory_position_storage import (
    execute,
    insert_snapshot,
)
from tests.integration.test_memory_position_storage import (
    published_snapshot as published_snapshot,
)
from tests.integration.test_memory_position_storage import (
    window as window,
)

pytestmark = pytest.mark.postgres


def seed(connection, *, kind="consultant_turn", status="completed"):
    job_id, execution_id = uuid4(), uuid4()
    connection.execute(
        "INSERT INTO job_files (job_file_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,'合成測試','合成測試','測試員工')",
        (job_id,),
    )
    connection.execute(
        "INSERT INTO executions (job_file_id,execution_id,kind,status) VALUES (%s,%s,%s,%s)",
        (job_id, execution_id, kind, status),
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
        "request_id": uuid4(),
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
        values if not pending else {key: values[key] for key in ("request_id", "request_snapshot")}
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
            [
                (key, value)
                for key, value in values.items()
                if key not in ("request_id", "request_snapshot")
            ],
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
    assert connection.execute(
        "SELECT saved_response_count,request_only_count FROM diagnostic_execution_history "
        "WHERE execution_id=%s",
        (other_execution,),
    ).fetchone() == (None, None)
    assert connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (0,)


def test_memory_roles_and_pending_writes_are_not_lost(database_settings, database_connection):
    job_id, execution_id = seed(database_connection, kind="memory_batch")
    for role in ("work_situation_analyst", "work_understanding_analyst"):
        save_step(database_connection, job_id, execution_id, role, pending=True)
    assert refresh_diagnostics(database_settings, execution_id=execution_id) == 1
    assert database_connection.execute(
        "SELECT role,response_source FROM diagnostic_model_steps ORDER BY role"
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


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_request_only_survives_refresh_and_does_not_count_as_saved_response(
    database_settings, database_connection, status
):
    connection = database_connection
    job_id, execution_id = seed(connection, status=status)
    saver = PostgresSaver(connection, serde=create_graph_serializer())
    saver.setup()
    request_id = uuid4()
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {
        "request_id": request_id,
        "request_snapshot": {"model": "synthetic", "input": ["已保存但沒有回應"]},
        "response_snapshot": {},
    }
    checkpoint["channel_versions"] = {key: 1 for key in checkpoint["channel_values"]}
    config = saver.put(
        {
            "configurable": {
                "thread_id": f"{job_id}:{execution_id}:job_consultant:completed_work",
                "checkpoint_ns": "",
            }
        },
        checkpoint,
        {"source": "loop", "step": 0, "parents": {}},
        checkpoint["channel_versions"],
    )

    refresh_diagnostics(database_settings, execution_id=execution_id)
    assert connection.execute(
        "SELECT request_id,response_state,response FROM diagnostic_model_steps"
    ).fetchone() == (str(request_id), "request_only", None)
    assert connection.execute(
        "SELECT saved_response_count,request_only_count,status FROM diagnostic_execution_history"
    ).fetchone() == (0, 1, status)

    saver.put_writes(config, [("response_snapshot", {"id": "late", "output": []})], "model")
    refresh_diagnostics(database_settings, execution_id=execution_id)
    assert connection.execute("SELECT count(*) FROM diagnostic_model_steps").fetchone() == (1,)
    assert connection.execute(
        "SELECT saved_response_count,request_only_count FROM diagnostic_execution_history"
    ).fetchone() == (1, 0)


def test_original_initial_context_binding_is_visible_independently_of_subsequent_state(
    database_settings, database_connection
):
    connection = database_connection
    job_id, execution_id = seed(connection)
    saver = PostgresSaver(connection, serde=create_graph_serializer())
    saver.setup()
    captured_binding = {"snapshot_id": str(uuid4()), "plan_base_revision_id": str(uuid4())}
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {
        "binding": captured_binding,
        "request_snapshot": {"input": ["當時已放入 Context 的導覽"], "authorization": "secret"},
    }
    checkpoint["channel_versions"] = {key: 1 for key in checkpoint["channel_values"]}
    saver.put(
        {
            "configurable": {
                "thread_id": f"{job_id}:{execution_id}:job_consultant:initial_context",
                "checkpoint_ns": "",
            }
        },
        checkpoint,
        {"source": "loop", "step": 1, "parents": {}},
        checkpoint["channel_versions"],
    )
    save_step(connection, job_id, execution_id)

    refresh_diagnostics(database_settings, execution_id=execution_id)
    initial, published = connection.execute(
        "SELECT captured_initial_context,published_snapshot_ids FROM diagnostic_execution_history"
    ).fetchone()
    assert initial["binding"] == captured_binding
    assert initial["request"]["authorization"] == "[redacted]"
    assert initial["request"]["input"] == ["當時已放入 Context 的導覽"]
    assert published is None
    assert connection.execute("SELECT count(*) FROM diagnostic_model_steps").fetchone() == (1,)


def test_past_binding_does_not_follow_the_current_published_memory_head(
    database_settings, database_connection, window, batch_position, published_snapshot
):
    connection = database_connection
    job_id, execution_id = window.job_file_id, uuid4()
    connection.execute(
        "INSERT INTO executions (job_file_id,execution_id,kind,status) "
        "VALUES (%s,%s,'consultant_turn','completed')",
        (job_id, execution_id),
    )
    saver = PostgresSaver(connection, serde=create_graph_serializer())
    saver.setup()
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {
        "request_snapshot": {"input": ["舊導覽"]},
        "binding": {"snapshot_id": str(published_snapshot), "plan_base_revision_id": str(uuid4())},
    }
    checkpoint["channel_versions"] = {key: 1 for key in checkpoint["channel_values"]}
    saver.put(
        {
            "configurable": {
                "thread_id": f"{job_id}:{execution_id}:job_consultant:initial_context",
                "checkpoint_ns": "",
            }
        },
        checkpoint,
        {"source": "loop", "step": 1, "parents": {}},
        checkpoint["channel_versions"],
    )
    refresh_diagnostics(database_settings, execution_id=execution_id)
    next_execution = uuid4()
    connection.execute(
        "INSERT INTO executions (execution_id,job_file_id,kind,status) "
        "VALUES (%s,%s,'memory_batch','completed')",
        (next_execution, job_id),
    )
    connection.execute(
        "INSERT INTO memory_batches "
        "(job_file_id,execution_id,base_snapshot_id,base_position_id,current_position_id,"
        "generation_id,stage_id,phase,status,through_source_id,"
        "covered_through_sequence,through_sequence) "
        "SELECT job_file_id,%s,%s,base_position_id,current_position_id,"
        "generation_id,stage_id,phase,"
        "status,through_source_id,covered_through_sequence,through_sequence FROM memory_batches",
        (next_execution, published_snapshot),
    )
    newer = execute(
        database_settings,
        lambda session: insert_snapshot(
            session, window, next_execution, batch_position.position_id
        ),
    )
    connection.execute(
        "UPDATE memory_heads SET snapshot_id=%s WHERE job_file_id=%s", (newer, job_id)
    )
    refresh_diagnostics(database_settings, execution_id=execution_id)
    captured, current = connection.execute(
        "SELECT captured_initial_context,current_published_snapshot_id "
        "FROM diagnostic_execution_history WHERE execution_id=%s",
        (execution_id,),
    ).fetchone()
    assert captured["binding"]["snapshot_id"] == str(published_snapshot)
    assert captured["request"]["input"] == ["舊導覽"]
    assert current == newer


def test_cli_show_reads_the_existing_copy_without_refresh_or_cross_file_leak(
    database_settings, database_connection, monkeypatch, capsys
):
    connection = database_connection
    job_id, execution_id = seed(connection)
    other_job, other_execution = seed(connection)
    save_step(connection, job_id, execution_id)
    save_step(connection, other_job, other_execution)
    refresh_diagnostics(database_settings, execution_id=execution_id)
    before = connection.execute("SELECT snapshot_at FROM diagnostic_execution_snapshots").fetchone()
    monkeypatch.setenv("CALIBURN_DATABASE_URL", database_settings.url)
    monkeypatch.setenv("CALIBURN_DATABASE_SCHEMA", database_settings.schema)
    script = Path(__file__).parents[2] / "scripts" / "refresh_execution_diagnostics.py"
    monkeypatch.setattr(sys, "argv", [str(script), "--execution-id", str(execution_id), "--show"])
    assert runpy.run_path(str(script))["main"]() == 0
    [document] = json.loads(capsys.readouterr().out)
    assert document["execution"]["execution_id"] == str(execution_id)
    assert document["steps"][0]["request"]["input"][0]["content"] == "盤點"
    assert "private" not in json.dumps(document)
    assert str(other_execution) not in json.dumps(document)
    assert (
        connection.execute("SELECT snapshot_at FROM diagnostic_execution_snapshots").fetchone()
        == before
    )


def test_operation_ids_survive_missing_outputs_and_legacy_stays_unknown(
    database_settings, database_connection
):
    from uuid import uuid5

    connection = database_connection
    job_id, execution_id = seed(connection)
    saver = PostgresSaver(connection, serde=create_graph_serializer())
    saver.setup()
    operation_seed = uuid4()
    thread = f"{job_id}:{execution_id}:job_consultant:completed_work"
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {
        "request_id": uuid4(),
        "request_snapshot": {"model": "synthetic", "input": ["committed but no output"]},
        "operation_seed": operation_seed,
        "response_snapshot": {
            "id": "trusted-response",
            "output": [
                {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": "revise_jd",
                    "arguments": "{}",
                }
                for call_id in ("call-a", "call-b")
            ],
        },
        "tool_results": [],
    }
    checkpoint["channel_versions"] = {key: 1 for key in checkpoint["channel_values"]}
    saver.put(
        {"configurable": {"thread_id": thread, "checkpoint_ns": ""}},
        checkpoint,
        {"source": "loop", "step": 0, "parents": {}},
        checkpoint["channel_versions"],
    )
    refresh_diagnostics(database_settings, execution_id=execution_id)
    assert connection.execute(
        "SELECT call_id,result_state,tool_output,operation_id FROM diagnostic_tool_calls "
        "WHERE execution_id=%s ORDER BY output_index",
        (execution_id,),
    ).fetchall() == [
        ("call-a", "not_recorded", None, uuid5(operation_seed, "call-a")),
        ("call-b", "not_recorded", None, uuid5(operation_seed, "call-b")),
    ]
    legacy_job, legacy_execution = seed(connection)
    save_step(connection, legacy_job, legacy_execution)
    refresh_diagnostics(database_settings, execution_id=legacy_execution)
    assert connection.execute(
        "SELECT operation_id FROM diagnostic_tool_calls WHERE execution_id=%s",
        (legacy_execution,),
    ).fetchall() == [(None,), (None,)]


def test_committed_compound_root_is_queryable_without_a_saved_tool_output(
    client, database_settings, database_connection
):
    from uuid import UUID, uuid5

    from caliburn.features.executions import service as executions
    from caliburn.features.executions.models import ExecutionKind, ExecutionScope
    from caliburn.features.job_description.models import ProfileField, SetProfileField
    from caliburn.workflows.jd_candidates import JdCandidateWorkflow
    from caliburn.workflows.jd_profile_writes import AddProfileSource, JdProfileWriteWorkflow
    from caliburn.workflows.jd_sources import CurrentInputSourceSelection
    from caliburn.workflows.memory_reads import PublishedMemoryRead

    created = client.post(
        "/api/job-files",
        json={
            "command_id": str(uuid4()),
            "display_name": "複合操作診斷",
            "employee_name": "合成人員",
        },
    ).json()
    file_id = UUID(created["job_file_id"])
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "我的職稱是網站工程師。"},
    ).json()
    scope = ExecutionScope(file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN)
    sessions = client.app.state.database.sessions
    workflow = JdProfileWriteWorkflow(sessions)
    operation_seed = uuid4()
    root_id = uuid5(operation_seed, "compound-call")

    async def prepare():
        async with sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        await JdCandidateWorkflow(sessions).start(writer)
        prepared = await workflow.prepare(
            PublishedMemoryRead(scope, None, 1),
            command_id=root_id,
            changes=(SetProfileField(ProfileField.JOB_TITLE, "網站工程師"),),
            sources=(AddProfileSource(ProfileField.JOB_TITLE, CurrentInputSourceSelection()),),
        )
        return writer, prepared

    writer, prepared = client.portal.call(prepare)
    client.portal.call(workflow.execute, writer, prepared)
    saver = PostgresSaver(database_connection, serde=create_graph_serializer())
    saver.setup()
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {
        "request_id": uuid4(),
        "request_snapshot": {"model": "synthetic", "input": []},
        "operation_seed": operation_seed,
        "response_snapshot": {
            "id": "compound-response",
            "output": [
                {
                    "type": "function_call",
                    "call_id": "compound-call",
                    "name": "revise_jd_profile",
                    "arguments": "{}",
                }
            ],
        },
        "tool_results": [],
    }
    checkpoint["channel_versions"] = {key: 1 for key in checkpoint["channel_values"]}
    saver.put(
        {
            "configurable": {
                "thread_id": (
                    f"{writer.scope.job_file_id}:{writer.scope.execution_id}"
                    ":job_consultant:completed_work"
                ),
                "checkpoint_ns": "",
            }
        },
        checkpoint,
        {"source": "loop", "step": 0, "parents": {}},
        checkpoint["channel_versions"],
    )
    refresh_diagnostics(database_settings, execution_id=writer.scope.execution_id)
    row = database_connection.execute(
        "SELECT t.operation_id,t.result_state,t.tool_output,o.kind,o.result_payload "
        "FROM diagnostic_tool_calls t JOIN jd_operations o "
        "ON o.job_file_id=t.job_file_id AND o.candidate_execution_id=t.execution_id "
        "AND o.command_id=t.operation_id WHERE t.execution_id=%s",
        (writer.scope.execution_id,),
    ).fetchone()
    assert row[:4] == (root_id, "not_recorded", None, "compound_edit")
    assert row[4]["effect"] == "updated"
    assert "created_item" not in row[4]


def test_native_null_seed_and_unrelated_custom_channel_do_not_break_safe_refresh(
    database_settings, database_connection
):
    connection = database_connection
    job_id, execution_id = seed(connection)
    thread = save_step(connection, job_id, execution_id)
    connection.execute(
        "INSERT INTO checkpoint_blobs(thread_id,checkpoint_ns,channel,version,type,blob) "
        "VALUES (%s,'','prepared_tool','custom-version','pickle',%s),"
        "(%s,'','operation_seed','null-version','null',%s)",
        (thread, b"never-deserialize-custom", thread, b""),
    )
    connection.execute(
        "UPDATE checkpoints SET checkpoint=jsonb_set(checkpoint,'{channel_versions}', "
        "(checkpoint->'channel_versions') || %s::jsonb) WHERE thread_id=%s",
        (json.dumps({"prepared_tool": "custom-version", "operation_seed": "null-version"}), thread),
    )
    assert refresh_diagnostics(database_settings, execution_id=execution_id) == 1
    assert connection.execute(
        "SELECT operation_id FROM diagnostic_tool_calls WHERE execution_id=%s",
        (execution_id,),
    ).fetchall() == [(None,), (None,)]


def test_pending_response_carries_its_own_operation_seed(database_settings, database_connection):
    from uuid import uuid5

    connection = database_connection
    job_id, execution_id = seed(connection)
    saver = PostgresSaver(connection, serde=create_graph_serializer())
    saver.setup()
    operation_seed = uuid4()
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {
        "request_id": uuid4(),
        "request_snapshot": {"model": "synthetic", "input": []},
        "operation_seed": None,
        "response_snapshot": {},
    }
    checkpoint["channel_versions"] = {key: 1 for key in checkpoint["channel_values"]}
    config = saver.put(
        {
            "configurable": {
                "thread_id": f"{job_id}:{execution_id}:job_consultant:completed_work",
                "checkpoint_ns": "",
            }
        },
        checkpoint,
        {"source": "loop", "step": 0, "parents": {}},
        checkpoint["channel_versions"],
    )
    saver.put_writes(
        config,
        [
            (
                "response_snapshot",
                {
                    "id": "pending-response",
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "pending-call",
                            "name": "revise_jd",
                            "arguments": "{}",
                        }
                    ],
                },
            ),
            ("operation_seed", operation_seed),
        ],
        "model-response",
    )
    refresh_diagnostics(database_settings, execution_id=execution_id)
    assert connection.execute(
        "SELECT call_id,operation_id,result_state FROM diagnostic_tool_calls WHERE execution_id=%s",
        (execution_id,),
    ).fetchone() == ("pending-call", uuid5(operation_seed, "pending-call"), "not_recorded")
    assert connection.execute(
        "SELECT response_source FROM diagnostic_model_steps WHERE execution_id=%s",
        (execution_id,),
    ).fetchone() == ("pending_write",)
