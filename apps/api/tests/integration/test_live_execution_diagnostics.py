"""Read originals directly, without a refreshed diagnostic copy."""

import asyncio
import json
import os
import runpy
import subprocess
import sys
from uuid import uuid4

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres import PostgresSaver

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.diagnostics.inspection import read_diagnostics
from tests.integration.test_memory_position_storage import (
    batch_position as batch_position,
)
from tests.integration.test_memory_position_storage import (
    create_position,
    create_revision,
    execute,
    insert_snapshot,
    reference,
)
from tests.integration.test_memory_position_storage import window as window

pytestmark = pytest.mark.postgres


def seed_execution(connection, *, kind="consultant_turn", status="completed"):
    job_id, execution_id = uuid4(), uuid4()
    connection.execute(
        "INSERT INTO job_files (job_file_id,initial_display_name,display_name,employee_name) "
        "VALUES (%s,'合成診斷','合成診斷','測試員工')",
        (job_id,),
    )
    connection.execute(
        "INSERT INTO executions (job_file_id,execution_id,kind,status) VALUES (%s,%s,%s,%s)",
        (job_id, execution_id, kind, status),
    )
    return job_id, execution_id


def save_request(connection, job_id, execution_id):
    saver = PostgresSaver(connection, serde=create_graph_serializer())
    saver.setup()
    checkpoint = empty_checkpoint()
    request_id = uuid4()
    checkpoint["channel_values"] = {
        "request_id": request_id,
        "request_snapshot": {"model": "synthetic", "input": [{"role": "user", "content": "盤點"}]},
        "response_snapshot": {"id": "resp_synthetic", "status": "completed", "output": []},
    }
    checkpoint["channel_versions"] = {key: 1 for key in checkpoint["channel_values"]}
    saver.put(
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
    return request_id


def test_saved_response_is_visible_without_refresh(database_settings, database_connection):
    job_id, execution_id = seed_execution(database_connection)
    request_id = save_request(database_connection, job_id, execution_id)
    documents = read(database_settings, execution_id=execution_id)
    assert len(documents) == 1
    assert len(documents[0]["steps"]) == 1
    assert documents[0]["steps"][0]["request_id"] == str(request_id)


def test_request_only_stays_readable_without_implying_remote_success(
    database_settings, database_connection
):
    job_id, execution_id = seed_execution(database_connection)
    request_id = uuid4()
    save_channels(
        database_connection,
        job_id,
        execution_id,
        "job_consultant:completed_work",
        {
            "request_id": request_id,
            "request_snapshot": {"model": "synthetic", "input": ["未回應的原件"]},
            "response_snapshot": {},
            "operation_seed": None,
        },
    )
    document = read(database_settings, execution_id=execution_id, full=True)[0]
    assert document["steps"][0]["response_state"] == "request_only"
    assert document["steps"][0]["response"] is None
    assert document["attempts"] == []
    assert document["tool_calls"] == []


def test_cli_subprocess_help_summary_full_and_safe_failure(database_settings, database_connection):
    file_id, execution_id = seed_execution(database_connection)
    request_id = save_request(database_connection, file_id, execution_id)
    environment = {
        **os.environ,
        "CALIBURN_DATABASE_URL": database_settings.url,
        "CALIBURN_DATABASE_SCHEMA": database_settings.schema,
    }

    def invoke(*arguments):
        return subprocess.run(
            [sys.executable, "-m", "caliburn.diagnostics", *arguments],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )

    help_result = invoke("--help")
    assert help_result.returncode == 0
    assert "--request-id" in help_result.stdout
    summary = invoke("--execution-id", str(execution_id))
    assert summary.returncode == 0
    assert "request" not in json.loads(summary.stdout)[0]["steps"][0]
    full = invoke("--execution-id", str(execution_id), "--request-id", str(request_id), "--full")
    assert full.returncode == 0
    assert json.loads(full.stdout)[0]["steps"][0]["request"]["model"] == "synthetic"
    database_connection.execute(
        "UPDATE checkpoint_blobs SET blob=%s WHERE channel='response_snapshot'",
        (b"sensitive-original-corrupt",),
    )
    failure = invoke("--execution-id", str(execution_id), "--full")
    assert failure.returncode == 1
    assert failure.stdout == ""
    assert "ValueError" in failure.stderr
    assert "sensitive-original-corrupt" not in failure.stderr


def read(settings, **scope):
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(read_diagnostics(settings, **scope))


def read_cli(settings, *, execution_id, full):
    result = subprocess.run(
        [sys.executable, "-m", "caliburn.diagnostics", "--execution-id", str(execution_id)]
        + (["--full"] if full else []),
        env={
            **os.environ,
            "CALIBURN_DATABASE_URL": settings.url,
            "CALIBURN_DATABASE_SCHEMA": settings.schema,
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("continue_work", [False, True])
@pytest.mark.parametrize("final_pause", [False, True])
def test_cli_preserves_native_pause_and_proven_continuation(
    database_settings, database_connection, continue_work, final_pause
):
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg import AsyncConnection

    from caliburn.agent_execution.native_agent import run_native_agent
    from caliburn.agent_execution.response_runtime import ResponseLoopControls
    from tests.fixtures.response_loop import LoopProbe, initial_request, response_at

    file_id, execution_id = seed_execution(database_connection, status="active")
    thread = f"{file_id}:{execution_id}:job_consultant:completed_work"
    probe = LoopProbe([response_at(1, final=final_pause), response_at(2, final=True)])
    pause_requested = True

    async def requested():
        return pause_requested

    async def marked():
        pass

    async def journey():
        nonlocal pause_requested
        async with await AsyncConnection.connect(
            database_settings.url,
            options=f"-c search_path={database_settings.schema}",
            autocommit=True,
        ) as connection:
            saver = AsyncPostgresSaver(connection, serde=create_graph_serializer())
            await saver.setup()
            arguments = dict(
                thread_id=thread,
                runtime=probe.runtime(),
                tools=[],
                max_tool_calls=2,
                max_model_steps=3,
                unknown_tool_output="unknown",
                controls=ResponseLoopControls(requested, marked),
            )
            stopped = await run_native_agent(saver, request=initial_request(), **arguments)
            if continue_work:
                pause_requested = False
                await run_native_agent(
                    saver, request=None, resume_interrupt_id=stopped.interrupt_id, **arguments
                )
            return stopped.interrupt_id

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        interrupt_id = runner.run(journey())
    database_connection.execute(
        "UPDATE executions SET status=%s WHERE execution_id=%s",
        ("completed" if continue_work else "cancelled", execution_id),
    )
    document = read_cli(database_settings, execution_id=execution_id, full=True)[0]
    assert "control_history" in document
    pause = document["control_history"][0]
    assert pause["interrupt_id"] == interrupt_id
    assert pause["completed_steps"] == 1
    assert pause["kind"] == "step_pause"
    assert pause["continuation"]["state"] == ("observed" if continue_work else "not_observed")
    if continue_work:
        assert pause["continuation"]["checkpoint_path"][0] == pause["checkpoint_id"]
        assert pause["continuation"]["completed_steps"] >= 1
    assert "resume" not in json.dumps(pause)
    assert len(document["steps"]) == (2 if continue_work and not final_pause else 1)
    assert document["steps"][0]["request"]["instructions"] == "synthetic fixed instructions"
    assert document["execution"]["status"] == ("completed" if continue_work else "cancelled")


def save_channels(connection, job_id, execution_id, suffix, values, *, pending=None):
    saver = PostgresSaver(connection, serde=create_graph_serializer())
    saver.setup()
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = values
    checkpoint["channel_versions"] = {key: 1 for key in values}
    config = saver.put(
        {"configurable": {"thread_id": f"{job_id}:{execution_id}:{suffix}", "checkpoint_ns": ""}},
        checkpoint,
        {"source": "loop", "step": 0, "parents": {}},
        checkpoint["channel_versions"],
    )
    if pending:
        saver.put_writes(config, list(pending.items()), "saved-result")
    return config


def test_execution_without_saver_setup_is_an_empty_observation(
    database_settings, database_connection
):
    _, execution_id = seed_execution(database_connection)
    document = read(database_settings, execution_id=execution_id, full=True)[0]
    assert document["steps"] == []
    assert document["compactions"] == []


def test_cli_full_preserves_context_tool_definition_arguments_and_output(
    database_settings, database_connection
):
    job_id, execution_id = seed_execution(database_connection)
    snapshot_id = str(uuid4())
    request = {
        "model": "synthetic",
        "instructions": "當時完整提示",
        "input": [{"role": "user", "content": "當時完整 Context"}],
        "tools": [{"type": "function", "name": "read_jd", "parameters": {"type": "object"}}],
    }
    save_channels(
        database_connection,
        job_id,
        execution_id,
        "job_consultant:initial_context",
        {"request_snapshot": request, "binding": {"snapshot_id": snapshot_id}},
    )
    save_channels(
        database_connection,
        job_id,
        execution_id,
        "job_consultant:completed_work",
        {
            "request_id": uuid4(),
            "request_snapshot": request,
            "response_snapshot": {
                "id": "saved-response",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call1",
                        "name": "read_jd",
                        "arguments": '{"read_ref":"jd"}',
                    }
                ],
            },
            "tool_results": [{"call_id": "call1", "output": "當時完整工具結果"}],
        },
    )
    document = read_cli(database_settings, execution_id=execution_id, full=True)[0]
    assert document["captured_initial_context"]["request"] == request
    assert document["captured_initial_context"]["binding"]["snapshot_id"] == snapshot_id
    assert document["steps"][0]["request"] == request
    assert document["steps"][0]["response"]["id"] == "saved-response"
    assert document["tool_calls"][0]["name"] == "read_jd"
    assert document["tool_calls"][0]["arguments"] == '{"read_ref":"jd"}'
    assert document["tool_calls"][0]["output"] == "當時完整工具結果"


def test_pending_compaction_preserves_original_without_claiming_adoption(
    database_settings, database_connection
):
    job_id, execution_id = seed_execution(database_connection)
    request_id = uuid4()
    original = {"model": "synthetic", "input": [{"role": "user", "content": "原始 W"}]}
    compact = {
        "id": "compact_saved",
        "output": [{"type": "compaction", "encrypted_content": "opaque"}],
    }
    save_channels(
        database_connection,
        job_id,
        execution_id,
        f"job_consultant:completed_work:compact:{request_id}",
        {
            "request_id": request_id,
            "request_snapshot": original,
            "adopted": False,
            "input_count": {"input_tokens": 123, "attempt_id": uuid4()},
            "preparation_policy": None,
        },
        pending={"compaction_snapshot": compact, "compaction_attempt_id": uuid4()},
    )
    document = read(database_settings, execution_id=execution_id, full=True)[0]
    assert document["steps"] == []
    boundary = document["compactions"][0]
    assert boundary["request"] == original
    assert boundary["compaction"]["id"] == "compact_saved"
    assert boundary["compaction"]["output"][0]["encrypted_content"] == "[redacted]"
    assert boundary["compaction_source"] == "pending_write"
    assert boundary["adopted"] is False


def test_pending_response_and_operation_id_do_not_imply_tool_result(
    database_settings, database_connection
):
    from uuid import uuid5

    job_id, execution_id = seed_execution(database_connection)
    seed, request_id = uuid4(), uuid4()
    save_channels(
        database_connection,
        job_id,
        execution_id,
        "job_consultant:completed_work",
        {
            "request_id": request_id,
            "request_snapshot": {"model": "synthetic", "input": []},
            "response_snapshot": {},
            "operation_seed": None,
        },
        pending={
            "operation_seed": seed,
            "response_snapshot": {
                "id": "pending-R",
                "output": [
                    {"type": "function_call", "call_id": "c1", "name": "read_jd", "arguments": "{}"}
                ],
            },
        },
    )
    document = read(database_settings, execution_id=execution_id, full=True)[0]
    assert document["steps"][0]["response_source"] == "pending_write"
    call = document["tool_calls"][0]
    assert call["operation_id"] == str(uuid5(seed, "c1"))
    assert call["result_state"] == "not_recorded"
    assert call["output"] is None
    assert call["receipt_state"] == "not_recorded"


def test_file_overview_never_decodes_original_blobs(database_settings, database_connection):
    job_id, execution_id = seed_execution(database_connection)
    save_request(database_connection, job_id, execution_id)
    database_connection.execute(
        "UPDATE checkpoint_blobs SET blob=%s WHERE channel='response_snapshot'", (b"bad",)
    )
    overview = read(database_settings, job_file_id=job_id)
    assert len(overview) == 1
    assert overview[0]["steps"] == []
    with pytest.raises(ValueError):
        read(database_settings, execution_id=execution_id, full=True)


def test_memory_stage_pending_results_and_empty_tool_output_are_preserved(
    database_settings, database_connection
):
    from caliburn.features.executions.history_models import stage_thread_id

    file_id, execution_id = seed_execution(database_connection, kind="memory_batch")
    for role in ("work_situation_analyst", "work_understanding_analyst"):
        thread = stage_thread_id(f"{file_id}:{execution_id}:{role}:completed_work", uuid4())
        save_channels(
            database_connection,
            file_id,
            execution_id,
            thread.split(f"{file_id}:{execution_id}:", 1)[1],
            {"request_id": uuid4(), "request_snapshot": {"model": "synthetic", "input": []}},
            pending={
                "response_snapshot": {
                    "id": "same",
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "a",
                            "name": "read_memory",
                            "arguments": "{}",
                        },
                        {
                            "type": "function_call",
                            "call_id": "b",
                            "name": "read_memory",
                            "arguments": "{}",
                        },
                    ],
                },
                "operation_seed": uuid4(),
                "tool_results": [{"call_id": "b", "output": ""}],
            },
        )
    document = read(database_settings, execution_id=execution_id, full=True)[0]
    assert {step["role"] for step in document["steps"]} == {
        "work_situation_analyst",
        "work_understanding_analyst",
    }
    assert len(document["tool_calls"]) == 4
    assert [(call["result_state"], call["output"]) for call in document["tool_calls"]] == [
        ("not_recorded", None),
        ("recorded", ""),
        ("not_recorded", None),
        ("recorded", ""),
    ]


def test_memory_capture_before_first_request_is_visible_without_becoming_a_step(
    database_settings, database_connection
):
    from caliburn.features.executions.history_models import stage_thread_id

    file_id, execution_id = seed_execution(database_connection, kind="memory_batch")
    thread = stage_thread_id(
        f"{file_id}:{execution_id}:work_understanding_analyst:completed_work", uuid4()
    )
    original = {"model": "synthetic", "input": [{"role": "user", "content": "當時 B2 固定資料"}]}
    save_channels(
        database_connection,
        file_id,
        execution_id,
        thread.split(f"{file_id}:{execution_id}:", 1)[1] + ":context",
        {"request_snapshot": original, "situation_changes": [{"change": "當時 B1 handoff"}]},
    )
    document = read(database_settings, execution_id=execution_id, full=True)[0]
    assert document["steps"] == []
    context = document["captured_analysis_contexts"][0]
    assert context["request"] == original
    assert context["situation_changes"] == [{"change": "當時 B1 handoff"}]
    assert context["role"] == "work_understanding_analyst"


@pytest.mark.parametrize("reader", [read, read_cli])
def test_plan_history_retains_body_when_latest_revision_is_null(
    database_settings, database_connection, reader
):
    from caliburn.features.interview_plans import service
    from caliburn.features.interview_plans.models import PlanEdit

    file_id, execution_id = seed_execution(database_connection)
    initial = execute(
        database_settings,
        lambda session: service.start_candidate(session, file_id, execution_id, None),
    )
    changed = execute(
        database_settings,
        lambda session: service.apply_prepared(
            session,
            PlanEdit(
                uuid4(),
                initial.position,
                "synthetic",
                "歷史計畫正文",
                "saved",
            ),
        ),
    )
    cleared = execute(
        database_settings,
        lambda session: service.apply_prepared(
            session,
            PlanEdit(
                uuid4(),
                changed.snapshot.position,
                "synthetic-clear",
                None,
                "cleared",
            ),
        ),
    )
    document = reader(database_settings, execution_id=execution_id, full=True)[0]
    versions = {
        item["position"]["revision_id"]: item["body"]
        for item in document["versions"]["plan"]["revisions"]
    }
    assert versions[str(changed.snapshot.position.revision_id)] == "歷史計畫正文"
    assert versions[str(cleared.snapshot.position.revision_id)] is None
    assert document["candidates"]["plan"]["current_revision_id"] == str(
        cleared.snapshot.position.revision_id
    )


def test_full_interview_originals_are_redacted_without_changing_accepted_or_formal_state(
    database_settings, database_connection
):
    file_id, execution_id = seed_execution(database_connection)
    source_id = uuid4()
    original = '{"password":"synthetic-secret","work":"盤點"}'
    database_connection.execute(
        "INSERT INTO interview_texts(source_id,job_file_id,speaker,interview_text) "
        "VALUES (%s,%s,'employee',%s)",
        (source_id, file_id, original),
    )
    database_connection.execute(
        "INSERT INTO interview_inputs VALUES (%s,%s,%s,%s)",
        (file_id, uuid4(), source_id, execution_id),
    )
    document = read(database_settings, execution_id=execution_id, full=True)[0]
    assert document["interviews"][0]["sequence"] is None
    assert "synthetic-secret" not in str(document)
    assert "[redacted]" in document["interviews"][0]["text"]
    assert database_connection.execute(
        "SELECT interview_text FROM interview_texts WHERE source_id=%s", (source_id,)
    ).fetchone() == (original,)
    assert database_connection.execute("SELECT count(*) FROM formal_interviews").fetchone() == (0,)


def test_native_and_owner_reads_share_read_only_repeatable_read(
    database_settings, database_connection, monkeypatch
):
    from sqlalchemy import text

    from caliburn.diagnostics import inspection

    job_id, execution_id = seed_execution(database_connection)
    save_request(database_connection, job_id, execution_id)
    original = inspection.read_checkpoint_records

    async def interleave(session, **scope):
        assert await session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        assert await session.scalar(text("SHOW transaction_read_only")) == "on"
        database_connection.execute(
            "UPDATE checkpoint_blobs SET blob=%s WHERE channel='response_snapshot'", (b"bad",)
        )
        return await original(session, **scope)

    monkeypatch.setattr(inspection, "read_checkpoint_records", interleave)
    document = read(database_settings, execution_id=execution_id, full=True)[0]
    assert document["steps"][0]["response"]["id"] == "resp_synthetic"
    monkeypatch.setattr(inspection, "read_checkpoint_records", original)
    with pytest.raises(ValueError):
        read(database_settings, execution_id=execution_id, full=True)


@pytest.mark.parametrize("reader", [read, read_cli])
def test_old_memory_binding_reads_fixed_bodies_after_new_head(
    database_settings, database_connection, window, batch_position, reader
):
    old = create_revision(database_settings, window, "舊版")
    old_position = create_position(database_settings, window.job_file_id, (reference(old),))
    old_snapshot = execute(
        database_settings,
        lambda session: insert_snapshot(session, window, batch_position.execution_id, old_position),
    )
    run_id = uuid4()
    database_connection.execute(
        "INSERT INTO executions(job_file_id,execution_id,kind,status) "
        "VALUES (%s,%s,'consultant_turn','completed')",
        (window.job_file_id, run_id),
    )
    missing_plan = uuid4()
    save_channels(
        database_connection,
        window.job_file_id,
        run_id,
        "job_consultant:initial_context",
        {
            "binding": {
                "snapshot_id": str(old_snapshot),
                "plan_base_revision_id": str(missing_plan),
            },
            "request_snapshot": {
                "model": "synthetic",
                "input": ["當時導覽"],
                "authorization": "secret",
            },
        },
    )
    next_run = uuid4()
    database_connection.execute(
        "INSERT INTO executions(job_file_id,execution_id,kind,status) "
        "VALUES (%s,%s,'memory_batch','completed')",
        (window.job_file_id, next_run),
    )
    database_connection.execute(
        "INSERT INTO memory_batches(job_file_id,execution_id,base_snapshot_id,base_position_id,"
        "current_position_id,stage_id,phase,status,through_source_id,covered_through_sequence,"
        "through_sequence) SELECT job_file_id,%s,%s,base_position_id,current_position_id,"
        "stage_id,phase,status,through_source_id,covered_through_sequence,through_sequence "
        "FROM memory_batches",
        (next_run, old_snapshot),
    )
    new_snapshot = execute(
        database_settings,
        lambda session: insert_snapshot(session, window, next_run, batch_position.position_id),
    )
    database_connection.execute(
        "INSERT INTO memory_heads VALUES (%s,%s)", (window.job_file_id, new_snapshot)
    )
    document = reader(database_settings, execution_id=run_id, full=True)[0]
    assert document["captured_initial_context"]["binding"]["snapshot_id"] == str(old_snapshot)
    assert document["captured_initial_context"]["request"]["authorization"] == "[redacted]"
    memory = document["versions"]["memory"]
    assert memory["positions"][0]["position_id"] == str(old_position)
    assert memory["revisions"][0]["content"] == {
        "title": "舊版",
        "description": "描述",
        "body": "正文",
    }
    assert document["versions"]["plan"]["missing"] == [str(missing_plan)]


def test_overview_pagination_and_cli_do_not_leak_other_files(
    database_settings, database_connection, monkeypatch, capsys
):
    first_file, first_run = seed_execution(database_connection)
    other_file, other_run = seed_execution(database_connection)
    second_run = uuid4()
    database_connection.execute(
        "INSERT INTO executions(job_file_id,execution_id,kind,status) "
        "VALUES (%s,%s,'consultant_turn','cancelled')",
        (first_file, second_run),
    )
    first = read(database_settings, job_file_id=first_file, limit=1)
    second = read(database_settings, job_file_id=first_file, after=first_run)
    assert first[0]["execution"]["execution_id"] == str(first_run)
    assert second[0]["execution"]["execution_id"] == str(second_run)
    monkeypatch.setenv("CALIBURN_DATABASE_URL", database_settings.url)
    monkeypatch.setenv("CALIBURN_DATABASE_SCHEMA", database_settings.schema)
    monkeypatch.setattr(sys, "argv", ["inspect_execution", "--job-file-id", str(first_file)])
    with pytest.raises(SystemExit) as exit_result:
        runpy.run_module("caliburn.diagnostics", run_name="__main__")
    assert exit_result.value.code == 0
    output = capsys.readouterr().out
    assert len(json.loads(output)) == 2
    assert str(other_run) not in output
    assert str(other_file) not in output


@pytest.mark.parametrize("reader", [read, read_cli])
def test_committed_compound_root_is_queryable_without_a_saved_tool_output(
    client, database_settings, database_connection, reader
):
    from uuid import UUID, uuid5

    from caliburn.features.executions import service as executions
    from caliburn.features.executions.models import ExecutionKind, ExecutionScope
    from caliburn.features.job_description.models import ProfileField, SetProfileField
    from caliburn.features.job_description.source_intents import InterviewSourceSelection
    from caliburn.workflows.job_description.candidates import JdCandidateWorkflow
    from caliburn.workflows.job_description.profile_writes import (
        AddProfileSource,
        JdProfileWriteWorkflow,
    )
    from caliburn.workflows.work_memory.reads import PublishedMemoryRead

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
            sources=(AddProfileSource(ProfileField.JOB_TITLE, InterviewSourceSelection(2)),),
        )
        return writer, prepared

    writer, prepared = client.portal.call(prepare)
    from caliburn.workflows.job_description.compound_writes import execute_prepared_jd_edit

    client.portal.call(execute_prepared_jd_edit, workflow.sessions, writer, prepared)
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
    document = reader(database_settings, execution_id=writer.scope.execution_id, full=True)[0]
    call = document["tool_calls"][0]
    assert call["operation_id"] == str(root_id)
    assert call["result_state"] == "not_recorded"
    assert call["output"] is None
    assert call["receipt_state"] == "recorded"
    root = next(item for item in document["operations"]["jd"] if item["command_id"] == str(root_id))
    assert root["kind"] == "compound_edit"
    assert root["result_payload"]["effect"] == "updated"
    assert "created_item" not in root["result_payload"]
    versions = document["versions"]["jd"]["revisions"]
    assert any(item["snapshot"]["profile"]["job_title"] == "網站工程師" for item in versions)
