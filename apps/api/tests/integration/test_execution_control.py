"""Durable pause intent, terminal arbitration and writer fencing on real PostgreSQL."""

from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import Barrier
from uuid import UUID, uuid4

import psycopg
import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.adapters.database import migration_config
from caliburn.features.executions import service
from caliburn.features.executions.models import (
    ExecutionBusyError,
    ExecutionKind,
    ExecutionNotFoundError,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
    StaleWriterError,
)
from caliburn.features.job_description.models import ProfileField, ReviseJdProfile, SetProfileField
from caliburn.settings import DatabaseSettings
from caliburn.workflows.jd_candidates import JdCandidateWorkflow, adopt_candidate_jd

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


def admit_scope(
    client: TestClient, kind: ExecutionKind = ExecutionKind.CONSULTANT_TURN
) -> ExecutionScope:
    response = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "控制測試", "employee_name": "合成員工"},
    )
    assert response.status_code == 201
    scope = ExecutionScope(UUID(response.json()["job_file_id"]), uuid4(), kind)
    transact(client, lambda s: service.admit_execution(s, scope))
    return scope


def claim_writer(client: TestClient, scope: ExecutionScope) -> ExecutionWriter:
    return transact(client, lambda s: service.claim_writer(s, scope, writer_id=uuid4()))


def test_database_rejects_completion_while_paused(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    writer = claim_writer(client, admit_scope(client))
    transact(client, lambda s: service.pause_execution(s, writer))
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            "UPDATE executions SET status = 'completed' WHERE execution_id = %s",
            (writer.scope.execution_id,),
        )
    assert transact(client, lambda s: service.read_execution(s, writer.scope)).status == (
        ExecutionStatus.PAUSED
    )


def test_pause_request_is_durable_idempotent_and_does_not_need_a_writer(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    scope = admit_scope(client)
    assert transact(client, lambda s: service.read_execution(s, scope)).pause_requested is False
    for _ in range(2):
        assert transact(client, lambda s: service.request_pause(s, scope)) is None
    assert database_connection.execute(
        "SELECT status, pause_requested, writer_id FROM executions WHERE execution_id = %s",
        (scope.execution_id,),
    ).fetchone() == ("active", True, None)
    writer = claim_writer(client, scope)
    info = transact(client, lambda s: service.read_execution(s, scope))
    assert info.status == ExecutionStatus.ACTIVE
    assert info.pause_requested is True
    assert info.writer_id == writer.writer_id


def test_pending_pause_allows_inflight_candidate_effects_but_blocks_formal_completion(
    client: TestClient,
) -> None:
    writer = claim_writer(client, admit_scope(client))
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(workflow.start, writer)
    transact(client, lambda s: service.request_pause(s, writer.scope))
    edited = client.portal.call(
        workflow.edit,
        writer,
        start.scope,
        ReviseJdProfile(
            uuid4(), start.revision_id, (SetProfileField(ProfileField.JOB_TITLE, "在途結果"),)
        ),
    )
    assert client.portal.call(workflow.read, writer.scope).profile.job_title == "在途結果"

    async def complete(session: AsyncSession) -> None:
        await adopt_candidate_jd(session, writer, edited, uuid4())
        await service.finish_execution(session, writer, ExecutionStatus.COMPLETED)

    with pytest.raises(ExecutionStateError):
        transact(client, complete)
    formal = client.get(f"/api/job-files/{writer.scope.job_file_id}/jd/profile").json()
    assert formal["revision_id"] == str(start.revision_id)
    assert formal["profile"]["job_title"] is None
    assert client.portal.call(workflow.read, writer.scope).position == edited
    with pytest.raises(ExecutionBusyError):
        transact(client, lambda s: service.require_manual_edit_allowed(s, writer.scope.job_file_id))
    with pytest.raises(ExecutionBusyError):
        transact(
            client,
            lambda s: service.admit_execution(
                s, ExecutionScope(writer.scope.job_file_id, uuid4(), writer.scope.kind)
            ),
        )


@pytest.mark.parametrize("stop_at_boundary", [False, True])
def test_resume_consumes_pause_intent_and_allows_completion(
    client: TestClient, stop_at_boundary: bool
) -> None:
    writer = claim_writer(client, admit_scope(client))
    transact(client, lambda s: service.request_pause(s, writer.scope))
    if stop_at_boundary:
        # The caller must already have persisted the native Graph interrupt.
        for _ in range(2):
            transact(client, lambda s: service.pause_execution(s, writer))
            transact(client, lambda s: service.request_pause(s, writer.scope))
        info = transact(client, lambda s: service.read_execution(s, writer.scope))
        assert info.status == ExecutionStatus.PAUSED
        assert info.pause_requested is True
        with pytest.raises(ExecutionStateError):
            transact(client, lambda s: service.lock_active_writer(s, writer))
        with pytest.raises(ExecutionStateError):
            transact(
                client, lambda s: service.finish_execution(s, writer, ExecutionStatus.COMPLETED)
            )
    for _ in range(2):
        transact(client, lambda s: service.resume_execution(s, writer))
    info = transact(client, lambda s: service.read_execution(s, writer.scope))
    assert info.status == ExecutionStatus.ACTIVE
    assert info.pause_requested is False
    transact(client, lambda s: service.lock_active_writer(s, writer))
    transact(client, lambda s: service.finish_execution(s, writer, ExecutionStatus.COMPLETED))


@pytest.mark.parametrize("outcome", [ExecutionStatus.CANCELLED, ExecutionStatus.FAILED])
@pytest.mark.parametrize("stop_at_boundary", [False, True])
def test_cancel_or_failure_can_terminate_pending_or_paused_work(
    client: TestClient, outcome: ExecutionStatus, stop_at_boundary: bool
) -> None:
    writer = claim_writer(client, admit_scope(client))
    transact(client, lambda s: service.request_pause(s, writer.scope))
    if stop_at_boundary:
        transact(client, lambda s: service.pause_execution(s, writer))
    for _ in range(2):
        transact(client, lambda s: service.finish_execution(s, writer, outcome))
    info = transact(client, lambda s: service.read_execution(s, writer.scope))
    assert info.status == outcome
    assert info.pause_requested is False
    with pytest.raises(ExecutionStateError):
        transact(client, lambda s: service.lock_active_writer(s, writer))


@pytest.mark.parametrize(
    "outcome", [ExecutionStatus.COMPLETED, ExecutionStatus.CANCELLED, ExecutionStatus.FAILED]
)
def test_terminal_work_rejects_late_pause_requests(
    client: TestClient, outcome: ExecutionStatus
) -> None:
    writer = claim_writer(client, admit_scope(client))
    transact(client, lambda s: service.finish_execution(s, writer, outcome))
    with pytest.raises(ExecutionStateError):
        transact(client, lambda s: service.request_pause(s, writer.scope))
    info = transact(client, lambda s: service.read_execution(s, writer.scope))
    assert info.status == outcome
    assert info.pause_requested is False


def test_memory_and_wrong_scopes_cannot_request_pause(client: TestClient) -> None:
    scope = admit_scope(client)
    memory = admit_scope(client, ExecutionKind.MEMORY_BATCH)
    with pytest.raises(ExecutionStateError):
        transact(client, lambda s: service.request_pause(s, memory))
    wrong_scopes = (
        ExecutionScope(memory.job_file_id, scope.execution_id, scope.kind),
        ExecutionScope(scope.job_file_id, scope.execution_id, ExecutionKind.MEMORY_BATCH),
        ExecutionScope(scope.job_file_id, uuid4(), scope.kind),
    )
    for wrong in wrong_scopes:
        with pytest.raises(ExecutionNotFoundError):
            transact(client, partial(service.request_pause, scope=wrong))
    assert transact(client, lambda s: service.read_execution(s, scope)).pause_requested is False
    assert transact(client, lambda s: service.read_execution(s, memory)).pause_requested is False


def test_pause_request_survives_writer_replacement_without_unfencing_old_worker(
    client: TestClient,
) -> None:
    scope = admit_scope(client)
    original = claim_writer(client, scope)
    transact(client, lambda s: service.request_pause(s, scope))
    replacement = transact(
        client,
        lambda s: service.claim_writer(
            s, scope, writer_id=uuid4(), replaces_writer_id=original.writer_id
        ),
    )
    for control in (service.pause_execution, service.resume_execution, service.lock_active_writer):
        with pytest.raises(StaleWriterError):
            transact(client, partial(control, writer=original))
    for outcome in (ExecutionStatus.COMPLETED, ExecutionStatus.CANCELLED, ExecutionStatus.FAILED):
        with pytest.raises(StaleWriterError):
            transact(client, partial(service.finish_execution, writer=original, outcome=outcome))
    assert transact(client, lambda s: service.read_execution(s, scope)).pause_requested is True
    transact(client, lambda s: service.lock_active_writer(s, replacement))
    transact(client, lambda s: service.pause_execution(s, replacement))
    transact(client, lambda s: service.resume_execution(s, replacement))


def test_pause_request_and_completion_have_one_durable_winner(client: TestClient) -> None:
    writer = claim_writer(client, admit_scope(client))
    ready = Barrier(2)

    def compete(action: str) -> str | None:
        ready.wait(timeout=10)
        try:
            if action == "pause":
                transact(client, lambda s: service.request_pause(s, writer.scope))
            else:
                transact(
                    client, lambda s: service.finish_execution(s, writer, ExecutionStatus.COMPLETED)
                )
            return action
        except ExecutionStateError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        winners = [result for result in pool.map(compete, ("pause", "complete")) if result]
    assert len(winners) == 1
    info = transact(client, lambda s: service.read_execution(s, writer.scope))
    if winners == ["pause"]:
        assert info.status == ExecutionStatus.ACTIVE
        assert info.pause_requested is True
    else:
        assert info.status == ExecutionStatus.COMPLETED
        assert info.pause_requested is False


def test_pause_request_participates_in_callers_transaction(client: TestClient) -> None:
    scope = admit_scope(client)

    async def aborted_request(session: AsyncSession) -> None:
        await service.request_pause(session, scope)
        raise RuntimeError("caller transaction failed")

    with pytest.raises(RuntimeError, match="caller transaction failed"):
        transact(client, aborted_request)
    assert transact(client, lambda s: service.read_execution(s, scope)).pause_requested is False


def test_database_rejects_clearing_pending_pause_during_completion(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    scope = admit_scope(client)
    transact(client, lambda s: service.request_pause(s, scope))
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            "UPDATE executions SET status = 'completed', pause_requested = false "
            "WHERE execution_id = %s",
            (scope.execution_id,),
        )
    assert transact(client, lambda s: service.read_execution(s, scope)).pause_requested is True


@pytest.mark.parametrize(
    ("kind", "status"),
    [
        (ExecutionKind.MEMORY_BATCH, ExecutionStatus.ACTIVE),
        (ExecutionKind.CONSULTANT_TURN, ExecutionStatus.COMPLETED),
        (ExecutionKind.CONSULTANT_TURN, ExecutionStatus.CANCELLED),
        (ExecutionKind.CONSULTANT_TURN, ExecutionStatus.FAILED),
    ],
)
def test_database_rejects_pause_intent_outside_unfinished_consultant_work(
    client: TestClient,
    database_connection: psycopg.Connection,
    kind: ExecutionKind,
    status: ExecutionStatus,
) -> None:
    scope = admit_scope(client, kind)
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            "INSERT INTO executions (execution_id, job_file_id, kind, status, pause_requested) "
            "VALUES (%s, %s, %s, %s, true)",
            (uuid4(), scope.job_file_id, kind.value, status.value),
        )


def test_pause_migration_preserves_existing_status_and_terminal_identity(
    empty_database_settings: DatabaseSettings,
) -> None:
    settings = empty_database_settings
    engine = create_engine(
        settings.sqlalchemy_url, connect_args={"options": f"-c search_path={settings.schema}"}
    )
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes.update(connection=connection, schema=settings.schema)
            command.upgrade(config, "0013_execution_budgets")
            file_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO job_files (job_file_id, creation_command_id, "
                    "initial_display_name, display_name, employee_name) "
                    "VALUES (:file_id, :command_id, '合成升級', '合成升級', '合成員工')"
                ),
                {"file_id": file_id, "command_id": uuid4()},
            )
            for kind, status in (
                ("consultant_turn", "paused"),
                ("consultant_turn", "completed"),
                ("memory_batch", "active"),
            ):
                connection.execute(
                    text(
                        "INSERT INTO executions (execution_id, job_file_id, kind, status) "
                        "VALUES (:execution_id, :file_id, :kind, :status)"
                    ),
                    {"execution_id": uuid4(), "file_id": file_id, "kind": kind, "status": status},
                )
            command.upgrade(config, "head")
            command.upgrade(config, "head")
            assert connection.execute(
                text("SELECT kind, status, pause_requested FROM executions ORDER BY kind, status")
            ).all() == [
                ("consultant_turn", "completed", False),
                ("consultant_turn", "paused", False),
                ("memory_batch", "active", False),
            ]
        with psycopg.connect(
            settings.url, options=f"-c search_path={settings.schema}", autocommit=True
        ) as connection:
            for statement in (
                "UPDATE executions SET created_at = created_at + interval '1 second'",
                "UPDATE executions SET writer_id = %s WHERE status = 'completed'",
                "UPDATE executions SET status = 'active' WHERE status = 'completed'",
            ):
                with pytest.raises(psycopg.errors.CheckViolation):
                    connection.execute(statement, (uuid4(),) if "%s" in statement else None)
    finally:
        engine.dispose()
