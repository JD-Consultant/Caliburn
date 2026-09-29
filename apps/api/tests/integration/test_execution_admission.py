"""Real independent connections test admission, writer fencing and terminal eligibility."""

from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

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
from caliburn.features.job_files import service as job_files

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


def new_scope(
    client: TestClient, kind: ExecutionKind = ExecutionKind.CONSULTANT_TURN
) -> ExecutionScope:
    response = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "工作", "employee_name": "員工"},
    )
    return ExecutionScope(UUID(response.json()["job_file_id"]), uuid4(), kind)


def admit_writer(client: TestClient, scope: ExecutionScope) -> ExecutionWriter:
    async def admit(session: AsyncSession) -> ExecutionWriter:
        await service.admit_execution(session, scope)
        return await service.claim_writer(session, scope, writer_id=uuid4())

    return transact(client, admit)


def test_same_file_has_independent_consultant_and_memory_admission(client: TestClient) -> None:
    consultant = new_scope(client)
    admit_writer(client, consultant)
    memory = ExecutionScope(consultant.job_file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
    admit_writer(client, memory)
    for kind in (ExecutionKind.CONSULTANT_TURN, ExecutionKind.MEMORY_BATCH):
        with pytest.raises(ExecutionBusyError):
            admit_writer(client, ExecutionScope(consultant.job_file_id, uuid4(), kind))
    # Another file remains independent, without a global active-agent lock.
    admit_writer(client, new_scope(client))


def test_database_constraint_arbitrates_admission_without_a_python_mutex(
    client: TestClient,
) -> None:
    original = new_scope(client)

    def admit(_: int) -> bool:
        try:
            admit_writer(client, ExecutionScope(original.job_file_id, uuid4(), original.kind))
            return True
        except ExecutionBusyError:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(admit, range(8))).count(True) == 1


def test_pause_keeps_admission_but_disallows_business_writes(client: TestClient) -> None:
    scope = new_scope(client)
    writer = admit_writer(client, scope)
    transact(client, lambda s: service.pause_execution(s, writer))
    with pytest.raises(ExecutionBusyError):
        admit_writer(client, ExecutionScope(scope.job_file_id, uuid4(), scope.kind))
    with pytest.raises(ExecutionStateError):
        transact(client, lambda s: service.lock_active_writer(s, writer))

    async def check_manual(session: AsyncSession) -> None:
        await job_files.lock_job_file(session, scope.job_file_id)
        await service.require_manual_edit_allowed(session, scope.job_file_id)

    with pytest.raises(ExecutionBusyError):
        transact(client, check_manual)
    transact(client, lambda s: service.resume_execution(s, writer))
    transact(client, lambda s: service.lock_active_writer(s, writer))


def test_writer_claim_is_compare_and_set_and_replayable(client: TestClient) -> None:
    scope = new_scope(client)
    transact(client, lambda s: service.admit_execution(s, scope))

    def claim(_: int) -> ExecutionWriter | None:
        try:
            return transact(client, lambda s: service.claim_writer(s, scope, writer_id=uuid4()))
        except StaleWriterError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        writers = [writer for writer in pool.map(claim, range(8)) if writer is not None]
    assert len(writers) == 1
    writer = writers[0]
    assert (
        transact(client, lambda s: service.claim_writer(s, scope, writer_id=writer.writer_id))
        == writer
    )


def test_replacement_fences_old_writer_and_cannot_be_silently_replaced_again(
    client: TestClient,
) -> None:
    scope = new_scope(client)
    original = admit_writer(client, scope)
    replacement_id = uuid4()
    replacement = transact(
        client,
        lambda s: service.claim_writer(
            s, scope, writer_id=replacement_id, replaces_writer_id=original.writer_id
        ),
    )
    with pytest.raises(StaleWriterError):
        transact(client, lambda s: service.lock_active_writer(s, original))
    with pytest.raises(StaleWriterError):
        transact(client, lambda s: service.finish_execution(s, original, ExecutionStatus.COMPLETED))
    with pytest.raises(StaleWriterError):
        transact(
            client,
            lambda s: service.claim_writer(
                s, scope, writer_id=uuid4(), replaces_writer_id=original.writer_id
            ),
        )
    transact(client, lambda s: service.lock_active_writer(s, replacement))


def test_scope_cannot_be_changed_by_reusing_execution_or_writer_identity(
    client: TestClient,
) -> None:
    scope = new_scope(client)
    original = admit_writer(client, scope)
    other = new_scope(client)
    wrong = ExecutionScope(other.job_file_id, scope.execution_id, scope.kind)
    with pytest.raises(ExecutionNotFoundError):
        transact(
            client,
            lambda s: service.lock_active_writer(s, ExecutionWriter(wrong, original.writer_id)),
        )
    with pytest.raises(ExecutionNotFoundError):
        transact(client, lambda s: service.read_execution(s, wrong))
    wrong_kind = ExecutionScope(scope.job_file_id, scope.execution_id, ExecutionKind.MEMORY_BATCH)
    with pytest.raises(ExecutionNotFoundError):
        transact(client, lambda s: service.read_execution(s, wrong_kind))


@pytest.mark.parametrize(
    "outcome", [ExecutionStatus.COMPLETED, ExecutionStatus.CANCELLED, ExecutionStatus.FAILED]
)
def test_terminal_eligibility_is_stable_and_late_writes_are_rejected(
    client: TestClient, database_connection: psycopg.Connection, outcome: ExecutionStatus
) -> None:
    scope = new_scope(client)
    writer = admit_writer(client, scope)
    transact(client, lambda s: service.finish_execution(s, writer, outcome))
    transact(client, lambda s: service.finish_execution(s, writer, outcome))
    assert transact(client, lambda s: service.admit_execution(s, scope)).status == outcome
    with pytest.raises(ExecutionStateError):
        transact(client, lambda s: service.lock_active_writer(s, writer))
    with pytest.raises(ExecutionStateError):
        transact(client, lambda s: service.claim_writer(s, scope, writer_id=uuid4()))
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            "UPDATE executions SET status = 'active' WHERE execution_id = %s", (scope.execution_id,)
        )
    admit_writer(client, ExecutionScope(scope.job_file_id, uuid4(), scope.kind))


def test_memory_has_no_user_pause_or_cancel_policy(client: TestClient) -> None:
    writer = admit_writer(client, new_scope(client, ExecutionKind.MEMORY_BATCH))
    with pytest.raises(ExecutionStateError):
        transact(client, lambda s: service.pause_execution(s, writer))
    with pytest.raises(ExecutionStateError):
        transact(client, lambda s: service.finish_execution(s, writer, ExecutionStatus.CANCELLED))
    transact(client, lambda s: service.finish_execution(s, writer, ExecutionStatus.FAILED))


def test_cancel_and_complete_compete_for_one_durable_terminal_outcome(client: TestClient) -> None:
    writer = admit_writer(client, new_scope(client))

    def finish(outcome: ExecutionStatus) -> ExecutionStatus | None:
        try:
            transact(client, lambda s: service.finish_execution(s, writer, outcome))
            return outcome
        except ExecutionStateError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(finish, (ExecutionStatus.CANCELLED, ExecutionStatus.COMPLETED)))
    winner = [result for result in results if result is not None]
    assert len(winner) == 1
    assert transact(client, lambda s: service.read_execution(s, writer.scope)).status == winner[0]


def test_rejected_writer_cannot_change_data_in_its_business_transaction(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    from sqlalchemy import text

    original = admit_writer(client, new_scope(client))
    transact(
        client,
        lambda s: service.claim_writer(
            s, original.scope, writer_id=uuid4(), replaces_writer_id=original.writer_id
        ),
    )

    async def late_effect(session: AsyncSession) -> None:
        await job_files.lock_job_file(session, original.scope.job_file_id)
        await service.lock_active_writer(session, original)
        await session.execute(
            text("UPDATE job_files SET display_name = 'late effect' WHERE job_file_id = :file_id"),
            {"file_id": original.scope.job_file_id},
        )

    with pytest.raises(StaleWriterError):
        transact(client, late_effect)
    assert database_connection.execute(
        "SELECT display_name FROM job_files WHERE job_file_id = %s", (original.scope.job_file_id,)
    ).fetchone() == ("工作",)
