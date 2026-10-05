"""Whole-file deletion is atomic, isolated and unavailable during live work."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import AsyncExitStack
from functools import partial
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.pregel._executor import AsyncBackgroundExecutor
from langgraph.pregel._loop import AsyncPregelLoop
from psycopg import sql
from psycopg.conninfo import make_conninfo

from caliburn.adapters.process_lock import PostgresProcessLock
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionBusyError,
    ExecutionKind,
    ExecutionScope,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_files import service as job_file_service
from caliburn.features.work_memory.candidates import CreateMemoryObject
from caliburn.features.work_memory.models import MemoryContent
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.workflows import job_files as job_file_workflows
from caliburn.workflows.consultant_controls import ConsultantControlWorkflow
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor
from caliburn.workflows.execution_failures import run_with_failure_boundary
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from caliburn.workflows.memory_supervisor import MemorySupervisor
from tests.integration.test_consultant_completion import complete, start_turn
from tests.integration.test_execution_diagnostics import save_step

pytestmark = pytest.mark.postgres


def create_file(client: TestClient) -> str:
    response = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "刪除測試", "employee_name": "合成員工"},
    )
    assert response.status_code == 201
    return response.json()["job_file_id"]


def test_delete_removes_history_and_jd_without_touching_another_file(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    removed, retained = create_file(client), create_file(client)
    client.post(
        f"/api/job-files/{removed}/rename",
        json={"command_id": str(uuid4()), "display_name": "待刪除", "expected_name_revision": 1},
    ).raise_for_status()
    turn = start_turn(client, file_id=UUID(removed))
    exchange = complete(client, turn)
    sessions = client.app.state.database.sessions
    memory = MemoryCandidateWorkflow(sessions)

    async def publish_memory() -> None:
        scope = ExecutionScope(UUID(removed), uuid4(), ExecutionKind.MEMORY_BATCH)
        async with sessions.begin() as session:
            await executions.admit_execution(session, scope)
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        stage = await memory.start(writer, exchange.employee_input.source_id)
        assert stage is not None
        situation = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                stage,
                MemoryLayer.WORK_SITUATION,
                MemoryContent("進貨驗收", "驗收工作", "核對單據及到貨。"),
                reference_ids=frozenset({exchange.employee_input.source_id}),
            ),
        )
        next_stage = await memory.handoff(writer, situation.position, uuid4())
        understanding = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                next_stage,
                MemoryLayer.WORK_UNDERSTANDING,
                MemoryContent("庫存管理", "核對庫存", "維護進貨資料。"),
                reference_ids=frozenset({situation.object_id}),
            ),
        )
        await memory.publish(writer, understanding.position, uuid4())

    client.portal.call(publish_memory)
    save_step(database_connection, UUID(removed), turn.writer.scope.execution_id, pending=True)
    save_step(database_connection, UUID(retained), uuid4())
    retained_before = client.get(f"/api/job-files/{retained}/interviews").json()

    response = client.delete(f"/api/job-files/{removed}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.delete(f"/api/job-files/{removed}").status_code == 204
    for suffix in ("", "/interviews", "/jd/profile", "/jd/work"):
        assert client.get(f"/api/job-files/{removed}{suffix}").status_code == 404
    assert [row["job_file_id"] for row in client.get("/api/job-files").json()["job_files"]] == [
        retained
    ]
    assert client.get(f"/api/job-files/{retained}/interviews").json() == retained_before
    tables = database_connection.execute(
        "SELECT table_name FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND column_name = 'job_file_id'"
    ).fetchall()
    for (table,) in tables:
        assert database_connection.execute(
            sql.SQL("SELECT count(*) FROM {} WHERE job_file_id = %s").format(sql.Identifier(table)),
            (removed,),
        ).fetchone() == (0,), table
    for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
        assert database_connection.execute(
            sql.SQL("SELECT count(*) FROM {} WHERE thread_id LIKE %s").format(
                sql.Identifier(table)
            ),
            (f"{removed}:%",),
        ).fetchone() == (0,)
    assert database_connection.execute("SELECT count(*) FROM checkpoint_blobs").fetchone()[0] > 0


@pytest.mark.parametrize(
    ("kind", "status"),
    [("consultant_turn", "active"), ("consultant_turn", "paused"), ("memory_batch", "active")],
)
def test_busy_file_cannot_be_deleted(
    client: TestClient, database_connection: psycopg.Connection, kind: str, status: str
) -> None:
    file_id = create_file(client)
    database_connection.execute(
        "INSERT INTO executions (execution_id, job_file_id, kind, status) VALUES (%s,%s,%s,%s)",
        (uuid4(), file_id, kind, status),
    )
    result = client.delete(f"/api/job-files/{file_id}")
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "job_file_busy"
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute("DELETE FROM job_files WHERE job_file_id=%s", (file_id,))
    assert client.get(f"/api/job-files/{file_id}").status_code == 200
    assert len(client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]) == 1


def test_individual_originals_still_cannot_be_deleted(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    file_id = create_file(client)
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute("DELETE FROM interview_texts WHERE job_file_id=%s", (file_id,))
    complete(client, start_turn(client, file_id=UUID(file_id)))
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute("DELETE FROM executions WHERE job_file_id=%s", (file_id,))
    assert client.get(f"/api/job-files/{file_id}").status_code == 200


@pytest.mark.parametrize("write_kind", ["checkpoint", "writes"])
def test_late_native_write_cannot_recreate_a_deleted_file(
    client: TestClient, database_connection: psycopg.Connection, write_kind: str
) -> None:
    file_id = create_file(client)
    saver = client.app.state.consultant_status_workflow.checkpointer
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {"received_response": {"original": "retained"}}
    checkpoint["channel_versions"] = {"received_response": 1}
    config = {
        "configurable": {
            "thread_id": f"{file_id}:{uuid4()}",
            "checkpoint_ns": "",
        }
    }
    metadata = {"source": "loop", "step": 0, "parents": {}}
    config = client.portal.call(
        saver.aput, config, checkpoint, metadata, checkpoint["channel_versions"]
    )
    assert client.delete(f"/api/job-files/{file_id}").status_code == 204
    with pytest.raises(LookupError, match="Checkpoint job file no longer exists"):
        if write_kind == "checkpoint":
            client.portal.call(
                saver.aput, config, checkpoint, metadata, checkpoint["channel_versions"]
            )
        else:
            client.portal.call(saver.aput_writes, config, [("received_response", "late")], "exit")
    for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
        assert database_connection.execute(
            sql.SQL("SELECT count(*) FROM {} WHERE thread_id LIKE %s").format(
                sql.Identifier(table)
            ),
            (f"{file_id}:%",),
        ).fetchone() == (0,)


@pytest.mark.parametrize("cancellation", ["native_exit", "write", "repeated_write"])
def test_native_write_keeps_the_file_fence_after_cancellation(
    client: TestClient,
    database_connection: psycopg.Connection,
    monkeypatch: pytest.MonkeyPatch,
    cancellation: str,
) -> None:
    file_id = UUID(create_file(client))
    saver = client.app.state.consultant_status_workflow.checkpointer
    native_put = AsyncPostgresSaver.aput
    lock_file = job_file_service.lock_job_file

    async def scenario() -> None:
        entered, release, saved, deleting = (asyncio.Event() for _ in range(4))

        async def delayed_put(self, *args):
            entered.set()
            await release.wait()
            result = await native_put(self, *args)
            saved.set()
            return result

        async def observed_lock(session, identity):
            deleting.set()
            return await lock_file(session, identity)

        monkeypatch.setattr(AsyncPostgresSaver, "aput", delayed_put)
        monkeypatch.setattr(job_file_service, "lock_job_file", observed_lock)
        checkpoint = empty_checkpoint()
        checkpoint["channel_values"] = {"held_response": {"original": "retained"}}
        checkpoint["channel_versions"] = {"held_response": 1}
        config = {"configurable": {"thread_id": f"{file_id}:{uuid4()}", "checkpoint_ns": ""}}

        async def write():
            return await saver.aput(
                config,
                checkpoint,
                {"source": "loop", "step": 0, "parents": {}},
                checkpoint["channel_versions"],
            )

        delete_task = None
        exit_task = None
        if cancellation == "native_exit":
            # Execute the pinned framework's actual exit implementation. Its
            # cancelled exit carrier does not cancel the executor's saver future.
            executor = AsyncBackgroundExecutor({})
            stack = AsyncExitStack()
            await stack.enter_async_context(executor)
            write_task = executor.submit(write)
            await asyncio.wait_for(entered.wait(), 5)
            exit_task = asyncio.create_task(
                AsyncPregelLoop.__aexit__(SimpleNamespace(stack=stack), None, None, None)
            )
            await asyncio.sleep(0)
            exit_task.cancel()
            with pytest.raises(asyncio.CancelledError) as stopped:
                await exit_task
            assert any(
                isinstance(arg, asyncio.Task) and arg.cancelled() for arg in stopped.value.args
            )
        else:
            write_task = asyncio.create_task(write())
            await asyncio.wait_for(entered.wait(), 5)
            write_task.cancel()
        try:
            delete_task = asyncio.create_task(client.app.state.job_file_workflow.delete(file_id))
            await asyncio.wait_for(deleting.wait(), 5)
            assert not write_task.done()
            assert not delete_task.done(), "Deletion must serialize after the actual native write"
            if cancellation == "repeated_write":
                write_task.cancel()
            release.set()
            await asyncio.wait_for(asyncio.gather(write_task, return_exceptions=True), 5)
            await asyncio.wait_for(delete_task, 5)
            assert saved.is_set()
        finally:
            release.set()
            await asyncio.gather(write_task, return_exceptions=True)
            if delete_task is not None:
                await asyncio.gather(delete_task, return_exceptions=True)

    client.portal.call(scenario)
    assert client.get(f"/api/job-files/{file_id}").status_code == 404
    for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
        assert database_connection.execute(
            sql.SQL("SELECT count(*) FROM {} WHERE thread_id LIKE %s").format(
                sql.Identifier(table)
            ),
            (f"{file_id}:%",),
        ).fetchone() == (0,)


def test_checkpoint_failure_rolls_back_business_and_native_deletion(
    client: TestClient, database_connection: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_id = create_file(client)
    save_step(database_connection, UUID(file_id), uuid4(), pending=True)
    original = job_file_workflows.delete_job_file_checkpoints

    async def fail_after_native_delete(session, identity) -> None:
        await original(session, identity)
        raise RuntimeError("Injected failure before deletion commit")

    monkeypatch.setattr(job_file_workflows, "delete_job_file_checkpoints", fail_after_native_delete)
    with pytest.raises(RuntimeError, match="before deletion commit"):
        client.delete(f"/api/job-files/{file_id}")
    assert client.get(f"/api/job-files/{file_id}").status_code == 200
    assert len(client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]) == 1
    for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
        assert (
            database_connection.execute(
                sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
            ).fetchone()[0]
            > 0
        )


def test_concurrent_input_and_deletion_cannot_leave_orphaned_work(client: TestClient) -> None:
    file_id = create_file(client)
    barrier = Barrier(2)

    def submit() -> int:
        barrier.wait()
        return client.post(
            f"/api/job-files/{file_id}/inputs",
            json={"command_id": str(uuid4()), "text": "我負責盤點。"},
        ).status_code

    def remove() -> int:
        barrier.wait()
        return client.delete(f"/api/job-files/{file_id}").status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        accepted, deleted = pool.submit(submit), pool.submit(remove)
        result = (accepted.result(), deleted.result())
    assert result in ((202, 409), (404, 204))
    assert client.get(f"/api/job-files/{file_id}").status_code == (200 if result[0] == 202 else 404)


@pytest.mark.parametrize(
    ("kind", "outcome"),
    [
        (ExecutionKind.CONSULTANT_TURN, ExecutionStatus.CANCELLED),
        (ExecutionKind.CONSULTANT_TURN, ExecutionStatus.COMPLETED),
        (ExecutionKind.MEMORY_BATCH, ExecutionStatus.COMPLETED),
    ],
)
@pytest.mark.parametrize("detached_cleanup", [False, True])
def test_terminal_runner_must_finish_checkpoint_cleanup_before_file_deletion(
    client: TestClient,
    database_connection: psycopg.Connection,
    kind: ExecutionKind,
    outcome: ExecutionStatus,
    detached_cleanup: bool,
) -> None:
    file_id = UUID(create_file(client))
    retained_id = UUID(create_file(client))
    turn = start_turn(client, file_id=file_id)
    if kind == ExecutionKind.MEMORY_BATCH:
        client.portal.call(
            MemoryConsolidationWorkflow(client.app.state.database.sessions).request,
            turn.writer,
            uuid4(),
        )
        complete(client, turn)

    async def scenario() -> None:
        database = client.app.state.database
        entered = asyncio.Event()
        cleanup_started = asyncio.Event()
        release_cleanup = asyncio.Event()
        checkpoint_saved = asyncio.Event()
        seen: list[ExecutionWriter] = []
        native_tasks: list[asyncio.Task[None]] = []
        parent_tasks: list[asyncio.Task[object]] = []
        dsn = make_conninfo(
            database.settings.sqlalchemy_url.set(drivername="postgresql").render_as_string(
                hide_password=False
            ),
            options=f"-c search_path={database.settings.schema}",
        )
        async with AsyncPostgresSaver.from_conn_string(dsn) as saver:

            async def run(writer: ExecutionWriter) -> None:
                parent = asyncio.current_task()
                assert parent is not None
                parent_tasks.append(parent)
                seen.append(writer)
                entered.set()
                if outcome == ExecutionStatus.CANCELLED:
                    try:
                        await asyncio.Event().wait()
                    except asyncio.CancelledError as error:
                        if detached_cleanup:
                            native = asyncio.create_task(cleanup(writer))
                            native_tasks.append(native)
                            error.args = (*error.args, native)
                            raise
                        await cleanup(writer)
                        raise
                else:
                    if writer.scope.kind == ExecutionKind.MEMORY_BATCH:
                        work = await MemoryConsolidationWorkflow(database.sessions).read_work(
                            writer.scope
                        )
                        candidates = MemoryCandidateWorkflow(database.sessions)
                        stage = await candidates.handoff(writer, work.position, uuid4())
                        await candidates.publish(writer, stage, uuid4())
                    else:
                        async with database.sessions.begin() as session:
                            await executions.finish_execution(session, writer, outcome)
                    if detached_cleanup:
                        native = asyncio.create_task(cleanup(writer))
                        native_tasks.append(native)
                        raise RuntimeError(
                            "Native graph exit interrupted"
                        ) from asyncio.CancelledError(native)
                    await cleanup(writer)

            async def cleanup(writer: ExecutionWriter) -> None:
                cleanup_started.set()
                await release_cleanup.wait()
                await save_checkpoint(writer)

            async def settle_failure(writer: ExecutionWriter, error: Exception) -> None:
                assert checkpoint_saved.is_set()

            async def save_checkpoint(writer: ExecutionWriter) -> None:
                checkpoint = empty_checkpoint()
                checkpoint["channel_values"] = {"received_response": "synthetic complete result"}
                checkpoint["channel_versions"] = {"received_response": 1}
                config = await saver.aput(
                    {
                        "configurable": {
                            "thread_id": f"{file_id}:{writer.scope.execution_id}",
                            "checkpoint_ns": "",
                        }
                    },
                    checkpoint,
                    {"source": "loop", "step": 0, "parents": {}},
                    checkpoint["channel_versions"],
                )
                await saver.aput_writes(config, [("received_response", "saved")], "cleanup")
                checkpoint_saved.set()

            leader = PostgresProcessLock(database.settings)
            consultant = ConsultantSupervisor(
                sessions=database.sessions,
                run=partial(run_with_failure_boundary, run=run, settle_failure=settle_failure),
                process_lock=leader,
            )
            memory = MemorySupervisor(
                database.sessions,
                run=partial(run_with_failure_boundary, run=run, settle_failure=settle_failure),
                check_leadership=leader.check,
            )
            workflow = job_file_workflows.JobFileWorkflow(
                database.sessions,
                consultant_supervisor=consultant,
                memory_supervisor=memory,
            )
            cancel_task: asyncio.Task[object] | None = None
            try:
                await consultant.start()
                await memory.start()
                await asyncio.wait_for(entered.wait(), 5)
                if outcome == ExecutionStatus.CANCELLED:
                    controls = ConsultantControlWorkflow(database.sessions, saver, consultant)
                    cancel_task = asyncio.create_task(controls.cancel(seen[0].scope))
                await asyncio.wait_for(cleanup_started.wait(), 5)
                async with database.sessions() as session:
                    assert (
                        await executions.read_execution(session, seen[0].scope)
                    ).status == outcome
                rejected = False
                try:
                    await workflow.delete(file_id)
                except ExecutionBusyError:
                    rejected = True
                assert rejected, "A terminal status must not bypass live checkpoint cleanup"
                # A different idle file remains deletable while this runner finishes.
                await workflow.delete(retained_id)
                release_cleanup.set()
                await asyncio.wait_for(checkpoint_saved.wait(), 5)
                await asyncio.wait_for(asyncio.gather(*parent_tasks, return_exceptions=True), 5)
                if cancel_task is not None:
                    await cancel_task
                await workflow.delete(file_id)
                await workflow.delete(file_id)
            finally:
                release_cleanup.set()
                if cancel_task is not None:
                    await asyncio.gather(cancel_task, return_exceptions=True)
                await memory.close()
                await consultant.close()
                await asyncio.gather(*native_tasks, return_exceptions=True)

    client.portal.call(scenario)
    assert client.get(f"/api/job-files/{file_id}").status_code == 404
    for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
        assert database_connection.execute(
            sql.SQL("SELECT count(*) FROM {} WHERE thread_id LIKE %s").format(
                sql.Identifier(table)
            ),
            (f"{file_id}:%",),
        ).fetchone() == (0,)
