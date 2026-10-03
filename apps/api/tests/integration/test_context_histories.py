"""Adopted checkpoint references, fencing and caller transactions on real PostgreSQL."""

from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import Barrier
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import history, service
from caliburn.features.executions.history_models import (
    AgentRole,
    ContextBinding,
    ContextPosition,
    HistoryConflictError,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionNotFoundError,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
    StaleWriterError,
)

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


def admit_writer(
    client: TestClient,
    kind: ExecutionKind = ExecutionKind.CONSULTANT_TURN,
    *,
    job_file_id: UUID | None = None,
) -> ExecutionWriter:
    if job_file_id is None:
        response = client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "歷史測試",
                "employee_name": "合成員工",
            },
        )
        assert response.status_code == 201
        job_file_id = UUID(response.json()["job_file_id"])
    scope = ExecutionScope(job_file_id, uuid4(), kind)

    async def admit(session: AsyncSession) -> ExecutionWriter:
        await service.admit_execution(session, scope)
        return await service.claim_writer(session, scope, writer_id=uuid4())

    return transact(client, admit)


def test_empty_history_is_pinned_and_read_back_after_transaction(client: TestClient) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    assert transact(client, lambda s: history.read_context_history(s, writer.scope, role)) is None
    assert (
        transact(client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, role))
        is None
    )
    binding = transact(client, lambda s: history.bind_context_history(s, writer, role))
    assert binding == ContextBinding(role, None, None, None)
    assert (
        transact(client, lambda s: history.read_context_history(s, writer.scope, role)) == binding
    )
    assert transact(client, lambda s: history.bind_context_history(s, writer, role)) == binding


@pytest.mark.parametrize(("thread_id", "checkpoint_id"), [("", "cp"), ("t", ""), (" ", "cp")])
def test_empty_checkpoint_identity_is_rejected(thread_id: str, checkpoint_id: str) -> None:
    with pytest.raises(ValueError):
        ContextPosition(thread_id, checkpoint_id, HistoryWindowKind.PREPARED_HISTORY)


def test_thread_identity_separates_roles_and_window_kinds() -> None:
    scope = ExecutionScope(UUID(int=1), UUID(int=2), ExecutionKind.MEMORY_BATCH)
    assert context_thread_id(
        scope, AgentRole.WORK_SITUATION_ANALYST, HistoryWindowKind.PREPARED_HISTORY
    ) == (
        "00000000-0000-0000-0000-000000000001:00000000-0000-0000-0000-000000000002:"
        "work_situation_analyst:prepared_history"
    )
    assert (
        len(
            {
                context_thread_id(scope, role, kind)
                for role in AgentRole
                for kind in HistoryWindowKind
            }
        )
        == 6
    )


def position(
    writer: ExecutionWriter,
    role: AgentRole = AgentRole.JOB_CONSULTANT,
    kind: HistoryWindowKind = HistoryWindowKind.PREPARED_HISTORY,
    checkpoint_id: str = "prepared-checkpoint",
) -> ContextPosition:
    return ContextPosition(context_thread_id(writer.scope, role, kind), checkpoint_id, kind)


def prepare(
    client: TestClient, writer: ExecutionWriter, role: AgentRole = AgentRole.JOB_CONSULTANT
) -> ContextPosition:
    prepared = position(writer, role)
    transact(client, lambda s: history.bind_context_history(s, writer, role))
    transact(client, lambda s: history.adopt_prepared_context(s, writer, role, prepared))
    return prepared


def test_preparation_advances_head_once_without_refreshing_the_pinned_base(
    client: TestClient,
) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    prepared = prepare(client, writer)
    assert (
        transact(client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, role))
        == prepared
    )
    expected = ContextBinding(role, None, prepared, None)
    assert transact(client, lambda s: history.bind_context_history(s, writer, role)) == expected
    assert (
        transact(client, lambda s: history.adopt_prepared_context(s, writer, role, prepared))
        == expected
    )
    with pytest.raises(HistoryConflictError):
        transact(
            client,
            lambda s: history.adopt_prepared_context(
                s, writer, role, position(writer, checkpoint_id="replacement")
            ),
        )
    assert (
        transact(client, lambda s: history.read_context_history(s, writer.scope, role)) == expected
    )


def test_cancelled_preparation_is_the_next_work_base(client: TestClient) -> None:
    old = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    prepared = prepare(client, old)
    transact(client, lambda s: service.finish_execution(s, old, ExecutionStatus.CANCELLED))
    new = admit_writer(client, job_file_id=old.scope.job_file_id)
    assert transact(client, lambda s: history.bind_context_history(s, new, role)) == ContextBinding(
        role, prepared, None, None
    )


def test_cancelled_prepared_base_can_be_reused_but_other_foreign_references_cannot(
    client: TestClient,
) -> None:
    old = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    prepared = prepare(client, old)
    transact(client, lambda s: service.finish_execution(s, old, ExecutionStatus.CANCELLED))
    new = admit_writer(client, job_file_id=old.scope.job_file_id)
    transact(client, lambda s: history.bind_context_history(s, new, role))
    foreign = ContextPosition(prepared.thread_id, "different-checkpoint", prepared.kind)
    with pytest.raises(HistoryConflictError):
        transact(client, lambda s: history.adopt_prepared_context(s, new, role, foreign))
    for _ in range(2):
        assert transact(
            client, lambda s: history.adopt_prepared_context(s, new, role, prepared)
        ) == ContextBinding(role, prepared, prepared, None)
    assert transact(client, lambda s: history.bind_context_history(s, new, role)) == ContextBinding(
        role, prepared, prepared, None
    )
    assert (
        transact(client, lambda s: history.read_adopted_context(s, new.scope.job_file_id, role))
        == prepared
    )
    with pytest.raises(ExecutionStateError):
        transact(client, lambda s: history.adopt_prepared_context(s, old, role, prepared))
    with pytest.raises(HistoryConflictError):
        transact(
            client,
            lambda s: history.complete_context_histories(
                s, new, {role: position(old, kind=HistoryWindowKind.COMPLETED_WORK)}
            ),
        )
    completed = position(new, kind=HistoryWindowKind.COMPLETED_WORK)
    transact(client, lambda s: history.complete_context_histories(s, new, {role: completed}))
    assert transact(client, lambda s: history.read_context_history(s, new.scope, role)) == (
        ContextBinding(role, prepared, prepared, completed)
    )


@pytest.mark.parametrize("state", ["cancelled", "failed", "paused", "replaced"])
def test_ineligible_writer_cannot_pin_or_adopt_a_late_reference(
    client: TestClient, state: str
) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    transact(client, lambda s: history.bind_context_history(s, writer, role))
    if state == "replaced":
        transact(
            client,
            lambda s: service.claim_writer(
                s, writer.scope, writer_id=uuid4(), replaces_writer_id=writer.writer_id
            ),
        )
        expected_error = StaleWriterError
    elif state == "paused":
        transact(client, lambda s: service.pause_execution(s, writer))
        expected_error = ExecutionStateError
    else:
        transact(client, lambda s: service.finish_execution(s, writer, ExecutionStatus(state)))
        expected_error = ExecutionStateError
    with pytest.raises(expected_error):
        transact(client, lambda s: history.bind_context_history(s, writer, role))
    with pytest.raises(expected_error):
        transact(
            client, lambda s: history.adopt_prepared_context(s, writer, role, position(writer))
        )
    assert (
        transact(client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, role))
        is None
    )


def test_adoption_requires_binding_and_the_roles_own_prepared_window(client: TestClient) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    with pytest.raises(HistoryConflictError):
        transact(
            client, lambda s: history.adopt_prepared_context(s, writer, role, position(writer))
        )
    transact(client, lambda s: history.bind_context_history(s, writer, role))
    foreign = admit_writer(client)
    invalid = [
        position(foreign),
        position(writer, AgentRole.WORK_SITUATION_ANALYST),
        position(writer, kind=HistoryWindowKind.COMPLETED_WORK),
    ]
    for reference in invalid:
        with pytest.raises(HistoryConflictError):
            transact(
                client,
                partial(
                    history.adopt_prepared_context, writer=writer, role=role, position=reference
                ),
            )
    assert transact(client, lambda s: history.read_context_history(s, writer.scope, role)) == (
        ContextBinding(role, None, None, None)
    )


@pytest.mark.parametrize(
    ("kind", "role"),
    [
        (ExecutionKind.CONSULTANT_TURN, AgentRole.WORK_SITUATION_ANALYST),
        (ExecutionKind.CONSULTANT_TURN, AgentRole.WORK_UNDERSTANDING_ANALYST),
        (ExecutionKind.MEMORY_BATCH, AgentRole.JOB_CONSULTANT),
    ],
)
def test_roles_cannot_cross_execution_kind(
    client: TestClient, kind: ExecutionKind, role: AgentRole
) -> None:
    writer = admit_writer(client, kind)
    with pytest.raises(HistoryConflictError):
        transact(client, lambda s: history.bind_context_history(s, writer, role))
    with pytest.raises(HistoryConflictError):
        transact(client, lambda s: history.read_context_history(s, writer.scope, role))
    with pytest.raises(HistoryConflictError):
        transact(
            client,
            lambda s: history.adopt_prepared_context(s, writer, role, position(writer, role)),
        )


@pytest.mark.parametrize("mismatch", ["job", "execution", "kind"])
def test_binding_queries_and_writes_require_the_real_execution_scope(
    client: TestClient, mismatch: str
) -> None:
    writer = admit_writer(client)
    real = writer.scope
    scope = ExecutionScope(
        uuid4() if mismatch == "job" else real.job_file_id,
        uuid4() if mismatch == "execution" else real.execution_id,
        ExecutionKind.MEMORY_BATCH if mismatch == "kind" else real.kind,
    )
    forged = ExecutionWriter(scope, writer.writer_id)
    role = AgentRole.JOB_CONSULTANT
    with pytest.raises(ExecutionNotFoundError):
        transact(client, lambda s: history.read_context_history(s, scope, role))
    with pytest.raises(ExecutionNotFoundError):
        transact(client, lambda s: history.bind_context_history(s, forged, role))
    with pytest.raises(ExecutionNotFoundError):
        transact(
            client, lambda s: history.adopt_prepared_context(s, forged, role, position(writer))
        )
    with pytest.raises(ExecutionNotFoundError):
        transact(
            client,
            lambda s: history.complete_context_histories(s, forged, {role: position(writer)}),
        )


def test_completion_adopts_own_finished_window_and_new_work_pins_it(client: TestClient) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    prepared = prepare(client, writer)
    completed = position(writer, kind=HistoryWindowKind.COMPLETED_WORK, checkpoint_id="finished")
    transact(client, lambda s: history.complete_context_histories(s, writer, {role: completed}))
    assert transact(client, lambda s: service.read_execution(s, writer.scope)).status == (
        ExecutionStatus.COMPLETED
    )
    assert (
        transact(client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, role))
        == completed
    )
    assert transact(client, lambda s: history.read_context_history(s, writer.scope, role)) == (
        ContextBinding(role, None, prepared, completed)
    )
    new = admit_writer(client, job_file_id=writer.scope.job_file_id)
    assert transact(client, lambda s: history.bind_context_history(s, new, role)) == ContextBinding(
        role, completed, None, None
    )


def test_completed_ack_replay_after_new_head_does_not_rewind_it(client: TestClient) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    prepared = prepare(client, writer)
    completed = position(writer, kind=HistoryWindowKind.COMPLETED_WORK, checkpoint_id="finished")
    transact(client, lambda s: history.complete_context_histories(s, writer, {role: completed}))
    new = admit_writer(client, job_file_id=writer.scope.job_file_id)
    latest = prepare(client, new)
    for _ in range(2):
        assert (
            transact(
                client, lambda s: history.complete_context_histories(s, writer, {role: completed})
            )
            is None
        )
    different = position(writer, kind=HistoryWindowKind.COMPLETED_WORK, checkpoint_id="replacement")
    with pytest.raises(HistoryConflictError):
        transact(client, lambda s: history.complete_context_histories(s, writer, {role: different}))
    assert (
        transact(client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, role))
        == latest
    )
    assert transact(client, lambda s: history.read_context_history(s, writer.scope, role)) == (
        ContextBinding(role, None, prepared, completed)
    )


@pytest.mark.parametrize("state", ["cancelled", "failed", "paused", "pause_requested", "replaced"])
def test_completion_uses_existing_control_and_writer_fences(client: TestClient, state: str) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    prepared = prepare(client, writer)
    if state == "replaced":
        transact(
            client,
            lambda s: service.claim_writer(
                s, writer.scope, writer_id=uuid4(), replaces_writer_id=writer.writer_id
            ),
        )
        expected_error = StaleWriterError
    elif state == "pause_requested":
        transact(client, lambda s: service.request_pause(s, writer.scope))
        expected_error = ExecutionStateError
    elif state == "paused":
        transact(client, lambda s: service.pause_execution(s, writer))
        expected_error = ExecutionStateError
    else:
        transact(client, lambda s: service.finish_execution(s, writer, ExecutionStatus(state)))
        expected_error = ExecutionStateError
    completed = position(writer, kind=HistoryWindowKind.COMPLETED_WORK)
    with pytest.raises(expected_error):
        transact(client, lambda s: history.complete_context_histories(s, writer, {role: completed}))
    assert (
        transact(client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, role))
        == prepared
    )
    assert transact(client, lambda s: history.read_context_history(s, writer.scope, role)) == (
        ContextBinding(role, None, prepared, None)
    )


def test_memory_roles_complete_together_without_touching_another_role_or_job(
    client: TestClient,
) -> None:
    consultant = admit_writer(client)
    consultant_head = prepare(client, consultant)
    other_job = admit_writer(client)
    other_head = prepare(client, other_job)
    memory = admit_writer(
        client, ExecutionKind.MEMORY_BATCH, job_file_id=consultant.scope.job_file_id
    )
    situation = AgentRole.WORK_SITUATION_ANALYST
    understanding = AgentRole.WORK_UNDERSTANDING_ANALYST
    originals = {role: prepare(client, memory, role) for role in (situation, understanding)}
    completed = {
        role: position(memory, role, HistoryWindowKind.COMPLETED_WORK, role.value)
        for role in (
            understanding,
            situation,
        )  # Caller order must not determine the head lock order.
    }
    for invalid in (
        {},
        {situation: completed[situation]},
        {**completed, AgentRole.JOB_CONSULTANT: other_head},
    ):
        with pytest.raises(HistoryConflictError):
            transact(
                client,
                partial(history.complete_context_histories, writer=memory, positions=invalid),
            )
    for role in originals:
        assert (
            transact(
                client,
                partial(
                    history.read_adopted_context, job_file_id=memory.scope.job_file_id, role=role
                ),
            )
            == originals[role]
        )
    transact(client, lambda s: history.complete_context_histories(s, memory, completed))
    for role in completed:
        assert (
            transact(
                client,
                partial(
                    history.read_adopted_context, job_file_id=memory.scope.job_file_id, role=role
                ),
            )
            == completed[role]
        )
        assert transact(
            client, partial(history.read_context_history, scope=memory.scope, role=role)
        ) == (ContextBinding(role, None, originals[role], completed[role]))
    for writer, expected in ((consultant, consultant_head), (other_job, other_head)):
        assert (
            transact(
                client,
                partial(
                    history.read_adopted_context,
                    job_file_id=writer.scope.job_file_id,
                    role=AgentRole.JOB_CONSULTANT,
                ),
            )
            == expected
        )


@pytest.mark.parametrize("missing", ["binding", "preparation"])
def test_memory_completion_requires_preparation_for_both_roles(
    client: TestClient, missing: str
) -> None:
    writer = admit_writer(client, ExecutionKind.MEMORY_BATCH)
    situation = AgentRole.WORK_SITUATION_ANALYST
    understanding = AgentRole.WORK_UNDERSTANDING_ANALYST
    prepared = prepare(client, writer, situation)
    if missing == "preparation":
        transact(client, lambda s: history.bind_context_history(s, writer, understanding))
    completed = {
        role: position(writer, role, HistoryWindowKind.COMPLETED_WORK)
        for role in (situation, understanding)
    }
    with pytest.raises(HistoryConflictError):
        transact(client, lambda s: history.complete_context_histories(s, writer, completed))
    assert (
        transact(client, lambda s: service.read_execution(s, writer.scope)).status
        == ExecutionStatus.ACTIVE
    )
    assert (
        transact(
            client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, situation)
        )
        == prepared
    )


@pytest.mark.parametrize("mismatch", ["kind", "execution", "role"])
def test_completion_rejects_windows_outside_its_role_and_execution(
    client: TestClient, mismatch: str
) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    prepared = prepare(client, writer)
    if mismatch == "kind":
        invalid = prepared
    elif mismatch == "execution":
        foreign = admit_writer(client)
        invalid = position(foreign, kind=HistoryWindowKind.COMPLETED_WORK)
    else:
        invalid = position(
            writer, AgentRole.WORK_SITUATION_ANALYST, HistoryWindowKind.COMPLETED_WORK
        )
    with pytest.raises(HistoryConflictError):
        transact(client, lambda s: history.complete_context_histories(s, writer, {role: invalid}))
    assert (
        transact(client, lambda s: service.read_execution(s, writer.scope)).status
        == ExecutionStatus.ACTIVE
    )
    assert (
        transact(client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, role))
        == prepared
    )


def test_preparation_and_completion_participate_in_the_whole_caller_transaction(
    client: TestClient,
) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    transact(client, lambda s: history.bind_context_history(s, writer, role))
    prepared = position(writer)

    async def aborted_preparation(session: AsyncSession) -> None:
        await history.adopt_prepared_context(session, writer, role, prepared)
        raise RuntimeError("later workflow effect failed")

    with pytest.raises(RuntimeError, match="later workflow effect failed"):
        transact(client, aborted_preparation)
    assert (
        transact(client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, role))
        is None
    )
    assert transact(client, lambda s: history.read_context_history(s, writer.scope, role)) == (
        ContextBinding(role, None, None, None)
    )
    transact(client, lambda s: history.adopt_prepared_context(s, writer, role, prepared))
    completed = position(writer, kind=HistoryWindowKind.COMPLETED_WORK)

    async def aborted_completion(session: AsyncSession) -> None:
        await history.complete_context_histories(session, writer, {role: completed})
        raise RuntimeError("later workflow effect failed")

    with pytest.raises(RuntimeError, match="later workflow effect failed"):
        transact(client, aborted_completion)
    assert (
        transact(client, lambda s: service.read_execution(s, writer.scope)).status
        == ExecutionStatus.ACTIVE
    )
    assert (
        transact(client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, role))
        == prepared
    )
    assert transact(client, lambda s: history.read_context_history(s, writer.scope, role)) == (
        ContextBinding(role, None, prepared, None)
    )


def test_cancel_and_completion_compete_for_one_consistent_head(client: TestClient) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    prepared = prepare(client, writer)
    completed = position(writer, kind=HistoryWindowKind.COMPLETED_WORK)
    ready = Barrier(2)

    def compete(action: str) -> str | None:
        ready.wait(timeout=10)
        try:
            if action == "cancel":
                transact(
                    client, lambda s: service.finish_execution(s, writer, ExecutionStatus.CANCELLED)
                )
            else:
                transact(
                    client,
                    lambda s: history.complete_context_histories(s, writer, {role: completed}),
                )
            return action
        except ExecutionStateError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        winners = [winner for winner in pool.map(compete, ("cancel", "complete")) if winner]
    assert len(winners) == 1
    expected = completed if winners == ["complete"] else prepared
    assert (
        transact(client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, role))
        == expected
    )
    info = transact(client, lambda s: service.read_execution(s, writer.scope))
    assert info.status == (
        ExecutionStatus.COMPLETED if winners == ["complete"] else ExecutionStatus.CANCELLED
    )


def test_queries_work_in_read_only_transactions_without_creating_heads(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT

    async def read_only(
        session: AsyncSession,
    ) -> tuple[ContextBinding | None, ContextPosition | None]:
        await session.execute(text("SET TRANSACTION READ ONLY"))
        return (
            await history.read_context_history(session, writer.scope, role),
            await history.read_adopted_context(session, writer.scope.job_file_id, role),
        )

    assert transact(client, read_only) == (None, None)
    assert database_connection.execute("SELECT count(*) FROM context_history_heads").fetchone() == (
        0,
    )
    prepared = prepare(client, writer)
    assert transact(client, read_only) == (ContextBinding(role, None, prepared, None), prepared)


def test_concurrent_preparations_cannot_replace_the_winner(client: TestClient) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    ready = Barrier(2)

    def adopt(checkpoint_id: str) -> ContextPosition | None:
        ready.wait(timeout=10)
        reference = position(writer, checkpoint_id=checkpoint_id)
        try:

            async def bind_and_adopt(session: AsyncSession) -> ContextBinding:
                await history.bind_context_history(session, writer, role)
                return await history.adopt_prepared_context(session, writer, role, reference)

            transact(client, bind_and_adopt)
            return reference
        except HistoryConflictError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        winners = [winner for winner in pool.map(adopt, ("first", "second")) if winner is not None]
    assert len(winners) == 1
    assert transact(client, lambda s: history.read_context_history(s, writer.scope, role)) == (
        ContextBinding(role, None, winners[0], None)
    )
    assert (
        transact(client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, role))
        == winners[0]
    )


def test_concurrent_completion_replays_the_same_original_positions(client: TestClient) -> None:
    writer = admit_writer(client, ExecutionKind.MEMORY_BATCH)
    roles = (AgentRole.WORK_SITUATION_ANALYST, AgentRole.WORK_UNDERSTANDING_ANALYST)
    for role in roles:
        prepare(client, writer, role)
    completed = {role: position(writer, role, HistoryWindowKind.COMPLETED_WORK) for role in roles}
    ready = Barrier(2)

    def complete(reverse: bool) -> None:
        ready.wait(timeout=10)
        references = dict(reversed(list(completed.items()))) if reverse else completed
        transact(client, lambda s: history.complete_context_histories(s, writer, references))

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(complete, (True, False))) == [None, None]
    for role, reference in completed.items():
        assert (
            transact(
                client,
                partial(
                    history.read_adopted_context, job_file_id=writer.scope.job_file_id, role=role
                ),
            )
            == reference
        )


def test_moved_head_cannot_refresh_a_binding_or_be_overwritten_by_preparation(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    original = transact(client, lambda s: history.bind_context_history(s, writer, role))
    moved = position(writer, checkpoint_id="different-adoption")
    database_connection.execute(
        "UPDATE context_history_heads SET thread_id = %s, checkpoint_id = %s, kind = %s "
        "WHERE job_file_id = %s AND role = %s",
        (
            moved.thread_id,
            moved.checkpoint_id,
            moved.kind.value,
            writer.scope.job_file_id,
            role.value,
        ),
    )
    assert transact(client, lambda s: history.bind_context_history(s, writer, role)) == original
    with pytest.raises(HistoryConflictError):
        transact(
            client, lambda s: history.adopt_prepared_context(s, writer, role, position(writer))
        )
    assert (
        transact(client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, role))
        == moved
    )


def test_second_role_head_conflict_leaves_the_first_role_and_execution_untouched(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    writer = admit_writer(client, ExecutionKind.MEMORY_BATCH)
    first = AgentRole.WORK_SITUATION_ANALYST
    second = AgentRole.WORK_UNDERSTANDING_ANALYST
    prepared = {role: prepare(client, writer, role) for role in (first, second)}
    completed = {
        role: position(writer, role, HistoryWindowKind.COMPLETED_WORK) for role in prepared
    }
    database_connection.execute(
        "UPDATE context_history_heads SET checkpoint_id = 'moved' "
        "WHERE job_file_id = %s AND role = %s",
        (writer.scope.job_file_id, second.value),
    )

    async def catch_inside_transaction(session: AsyncSession) -> None:
        with pytest.raises(HistoryConflictError):
            await history.complete_context_histories(session, writer, completed)

    # Even when the caller catches the domain error, validation must not leave partial writes.
    transact(client, catch_inside_transaction)
    assert (
        transact(client, lambda s: service.read_execution(s, writer.scope)).status
        == ExecutionStatus.ACTIVE
    )
    assert (
        transact(client, lambda s: history.read_adopted_context(s, writer.scope.job_file_id, first))
        == prepared[first]
    )
    for role in prepared:
        assert transact(
            client, partial(history.read_context_history, scope=writer.scope, role=role)
        ) == (ContextBinding(role, None, prepared[role], None))


def test_database_rejects_cross_job_bindings_and_partial_references(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    writer = admit_writer(client)
    other = admit_writer(client)
    prepare(client, writer)
    prepare(client, other)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            "UPDATE context_history_bindings SET job_file_id = %s WHERE execution_id = %s",
            (other.scope.job_file_id, writer.scope.execution_id),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            "UPDATE context_history_bindings SET prepared_checkpoint_id = NULL "
            "WHERE execution_id = %s",
            (writer.scope.execution_id,),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            "UPDATE context_history_heads SET checkpoint_id = '' WHERE job_file_id = %s",
            (writer.scope.job_file_id,),
        )
