"""Reference candidate state and exact operation outcomes survive real PG transactions."""

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.job_files import service as job_files
from caliburn.features.occupation_references import service
from caliburn.features.occupation_references.models import (
    OccupationReferenceState,
    ReferenceStateConflictError,
    ReferenceStateError,
    ReferenceStatePosition,
    StaleReferenceStateError,
    select_references,
    update_excluded_work,
)

pytestmark = pytest.mark.postgres


def transact[T](
    client: TestClient,
    writer: ExecutionWriter,
    operation: Callable[[AsyncSession], Awaitable[T]],
) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            await executions.lock_active_writer(session, writer)
            return await operation(session)

    return client.portal.call(run)


def writer_for_new_file(client: TestClient) -> ExecutionWriter:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "公版測試", "employee_name": "合成員工"},
    )
    assert created.status_code == 201
    file_id = UUID(created.json()["job_file_id"])
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "正式環境部署及帳務調整由別組負責。"},
    )
    assert accepted.status_code == 202
    scope = ExecutionScope(
        file_id, UUID(accepted.json()["execution_id"]), ExecutionKind.CONSULTANT_TURN
    )

    async def claim() -> ExecutionWriter:
        async with client.app.state.database.sessions.begin() as session:
            return await executions.claim_writer(session, scope, writer_id=uuid4())

    return client.portal.call(claim)


def start(
    client: TestClient, writer: ExecutionWriter, base: OccupationReferenceState | None = None
) -> ReferenceStatePosition:
    return transact(
        client,
        writer,
        lambda session: service.start_candidate(
            session,
            writer.scope.job_file_id,
            writer.scope.execution_id,
            base if base is not None else OccupationReferenceState(),
        ),
    )


def apply(
    client: TestClient,
    writer: ExecutionWriter,
    position: ReferenceStatePosition,
    operation_id: UUID,
    state: OccupationReferenceState,
) -> ReferenceStatePosition:
    return transact(
        client,
        writer,
        lambda session: service.apply_state(
            session, writer.scope.job_file_id, position, operation_id, state
        ),
    )


def read(client: TestClient, writer: ExecutionWriter) -> ReferenceStatePosition | None:
    return transact(
        client,
        writer,
        lambda session: service.read_candidate(
            session, writer.scope.job_file_id, writer.scope.execution_id
        ),
    )


def restore(
    client: TestClient,
    writer: ExecutionWriter,
    position: ReferenceStatePosition,
    target_revision_id: UUID,
    operation_id: UUID,
) -> ReferenceStatePosition:
    return transact(
        client,
        writer,
        lambda session: service.restore_candidate(
            session, writer.scope.job_file_id, position, target_revision_id, operation_id
        ),
    )


def test_candidates_reopen_original_state_and_keep_file_scope(client: TestClient) -> None:
    writer, other = writer_for_new_file(client), writer_for_new_file(client)
    assert read(client, writer) is None
    first = start(client, writer)
    assert first.state == OccupationReferenceState()
    assert start(client, writer, OccupationReferenceState(("should-not-replace",))) == first
    changed = apply(client, writer, first, uuid4(), OccupationReferenceState(()))
    assert read(client, writer) == changed
    assert read(client, other) is None
    listed = transact(
        client, writer, lambda session: service.list_candidates(session, writer.scope.job_file_id)
    )
    assert listed == (changed,)
    assert start(client, other).state.selected_reference_ids is None


def test_replay_returns_exact_result_and_rejects_changed_intent(client: TestClient) -> None:
    writer = writer_for_new_file(client)
    initial = start(client, writer)
    operation_id = uuid4()
    first_state = OccupationReferenceState(("frontend:v1",), ("正式部署",))
    first = apply(client, writer, initial, operation_id, first_state)
    second = apply(client, writer, first, uuid4(), OccupationReferenceState(("backend:v1",)))
    assert apply(client, writer, initial, operation_id, first_state) == first
    assert read(client, writer) == second
    with pytest.raises(ReferenceStateConflictError):
        apply(client, writer, initial, operation_id, OccupationReferenceState(()))
    with pytest.raises(StaleReferenceStateError):
        apply(client, writer, initial, uuid4(), first_state)


def test_restore_fences_old_writes_and_keeps_its_original_result(client: TestClient) -> None:
    writer = writer_for_new_file(client)
    initial = start(client, writer)
    first_id = uuid4()
    first_state = OccupationReferenceState(("frontend:v1",), ("正式部署",))
    first = apply(client, writer, initial, first_id, first_state)
    abandoned = apply(client, writer, first, uuid4(), OccupationReferenceState((), ("帳務調整",)))
    restore_id = uuid4()
    restored = restore(client, writer, abandoned, first.revision_id, restore_id)
    assert restored.state == first_state
    assert restored.generation_id != first.generation_id
    with pytest.raises(StaleReferenceStateError):
        apply(client, writer, initial, first_id, first_state)
    continued = apply(client, writer, restored, uuid4(), OccupationReferenceState(("new:v1",)))
    assert restore(client, writer, abandoned, first.revision_id, restore_id) == restored
    assert read(client, writer) == continued
    with pytest.raises(ReferenceStateError):
        restore(client, writer, continued, abandoned.revision_id, uuid4())


def test_restore_cannot_select_other_turn_or_unknown_revision(client: TestClient) -> None:
    writer, other = writer_for_new_file(client), writer_for_new_file(client)
    initial, foreign = start(client, writer), start(client, other)
    for target in (foreign.revision_id, uuid4()):
        with pytest.raises(ReferenceStateError):
            restore(client, writer, initial, target, uuid4())
    with pytest.raises(ReferenceStateError):
        apply(client, writer, foreign, uuid4(), OccupationReferenceState(()))
    assert read(client, writer) == initial


def test_rollback_cannot_leave_state_without_its_original_result(client: TestClient) -> None:
    writer = writer_for_new_file(client)
    initial = start(client, writer)
    operation_id = uuid4()
    new_state = select_references(initial.state, ("backend:v1",))

    async def interrupted(session: AsyncSession) -> None:
        await service.apply_state(
            session, writer.scope.job_file_id, initial, operation_id, new_state
        )
        raise RuntimeError("Abort caller transaction")

    with pytest.raises(RuntimeError, match="Abort caller"):
        transact(client, writer, interrupted)
    assert read(client, writer) == initial
    saved = apply(client, writer, initial, operation_id, new_state)
    assert read(client, writer) == saved


def test_excluded_work_is_saved_and_corrections_can_remove_it(client: TestClient) -> None:
    writer = writer_for_new_file(client)
    base = OccupationReferenceState(excluded_work=("正式環境部署", "帳務調整"))
    initial = start(client, writer, base)
    changed = apply(client, writer, initial, uuid4(), select_references(base, ("backend:v1",)))
    assert read(client, writer) == changed
    assert changed.state.excluded_work == ("正式環境部署", "帳務調整")
    correction_id = uuid4()
    correction = update_excluded_work(changed.state, ("資料庫維護",), ("正式環境部署",))
    corrected = apply(client, writer, changed, correction_id, correction)
    assert read(client, writer) == corrected
    assert corrected.state.excluded_work == ("帳務調整", "資料庫維護")
    assert apply(client, writer, changed, correction_id, correction) == corrected


def test_database_keeps_original_results_immutable_and_scoped(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    writer, other = writer_for_new_file(client), writer_for_new_file(client)
    initial, foreign = start(client, writer), start(client, other)
    connection = database_connection
    for statement in (
        "UPDATE occupation_reference_operations SET state = '{}'::jsonb WHERE job_file_id = %s",
        "DELETE FROM occupation_reference_operations WHERE job_file_id = %s",
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            connection.execute(statement, (writer.scope.job_file_id,))
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        connection.execute(
            "UPDATE occupation_reference_candidates SET current_revision_id = %s "
            "WHERE job_file_id = %s AND execution_id = %s",
            (foreign.revision_id, writer.scope.job_file_id, writer.scope.execution_id),
        )
    assert read(client, writer) == initial


@pytest.mark.parametrize(
    "obsolete",
    [
        {"selected_reference_ids": None, "confirmations": []},
        {"selected_reference_ids": None, "excluded_work": [], "answer_refs": []},
    ],
)
def test_database_rejects_obsolete_or_extra_state_fields(
    client: TestClient, database_connection: psycopg.Connection, obsolete: dict[str, object]
) -> None:
    writer = writer_for_new_file(client)
    initial = start(client, writer)
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            "INSERT INTO occupation_reference_operations "
            "(job_file_id, operation_id, execution_id, kind, generation_id, "
            "result_generation_id, expected_revision_id, parent_revision_id, revision_id, state) "
            "VALUES (%s,%s,%s,'start',%s,%s,NULL,NULL,%s,%s)",
            (
                writer.scope.job_file_id,
                uuid4(),
                writer.scope.execution_id,
                initial.generation_id,
                initial.generation_id,
                uuid4(),
                Jsonb(obsolete),
            ),
        )
    assert read(client, writer) == initial
