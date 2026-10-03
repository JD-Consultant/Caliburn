"""Outbound failure originals survive reentry without releasing reservations or eligibility."""

from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import budget_models, budgets, service
from caliburn.features.executions.budget_models import (
    BudgetConflictError,
    BudgetExceededError,
    BudgetLimit,
    ExecutionBudget,
    OutboundAttempt,
    OutboundKind,
    OutboundRequest,
)
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionNotFoundError,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)

pytestmark = pytest.mark.postgres

RETRY_AT = datetime(2026, 10, 1, 12, 0, tzinfo=timezone(timedelta(hours=8)))


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


@pytest.fixture
def writer(client: TestClient) -> ExecutionWriter:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "合成失敗", "employee_name": "合成員工"},
    )
    assert created.status_code == 201
    scope = ExecutionScope(
        UUID(created.json()["job_file_id"]), uuid4(), ExecutionKind.CONSULTANT_TURN
    )

    async def run(session: AsyncSession) -> ExecutionWriter:
        await service.admit_execution(session, scope)
        owner = await service.claim_writer(session, scope, writer_id=uuid4())
        await budgets.fix_execution_budget(
            session,
            owner,
            ExecutionBudget(
                8, 4, 32, 3, datetime.now(UTC) + timedelta(hours=1), Decimal("0.3"), "synthetic-v1"
            ),
        )
        return owner

    return transact(client, run)


def reserve(client: TestClient, writer: ExecutionWriter) -> OutboundAttempt:
    return transact(
        client,
        lambda session: budgets.reserve_outbound_attempt(
            session,
            writer,
            request=OutboundRequest(uuid4(), OutboundKind.MODEL, "a" * 64),
            attempt_id=uuid4(),
            reserved_cost_usd=Decimal("0.1"),
        ),
    ).attempt


def record_failure(
    client: TestClient,
    scope: ExecutionScope,
    attempt_id: UUID,
    *,
    code: str = "transient_service",
    retry_at: datetime | None = RETRY_AT,
) -> OutboundAttempt:
    return transact(
        client,
        lambda session: budgets.record_attempt_failure(
            session,
            scope,
            attempt_id,
            failure=budget_models.OutboundFailure(code, retry_at),
        ),
    )


@pytest.mark.parametrize(
    "code, retry_at",
    [
        ("remote_result_unknown", RETRY_AT),
        ("transient_service", RETRY_AT),
        ("rate_limited", RETRY_AT),
        ("remote_result_unknown", None),
        ("transient_service", None),
        ("rate_limited", None),
        ("access_blocked", None),
        ("capacity_exceeded", None),
        ("request_rejected", None),
        ("response_protocol", None),
    ],
)
def test_failure_original_round_trips_in_new_session_and_reentry(
    client: TestClient, writer: ExecutionWriter, code: str, retry_at: datetime | None
) -> None:
    original = reserve(client, writer)
    assert original.failure is None
    saved = record_failure(client, writer.scope, original.attempt_id, code=code, retry_at=retry_at)
    assert saved.failure == budget_models.OutboundFailure(code, retry_at)
    assert saved.reported_cost_usd is None
    assert saved.reserved_cost_usd == Decimal("0.1")
    reread = transact(
        client, lambda s: budgets.read_outbound_attempt(s, writer.scope, original.attempt_id)
    )
    assert reread == saved
    assert (
        record_failure(client, writer.scope, original.attempt_id, code=code, retry_at=retry_at)
        == saved
    )
    replay = transact(
        client,
        lambda s: budgets.reserve_outbound_attempt(
            s,
            writer,
            request=original.request,
            attempt_id=original.attempt_id,
            reserved_cost_usd=Decimal("0.1"),
        ),
    )
    assert not replay.created
    assert replay.attempt == saved


@pytest.mark.parametrize(
    "code, retry_at",
    [
        ("provider raw error body", None),
        ("", None),
        ("access_blocked", RETRY_AT),
        ("capacity_exceeded", RETRY_AT),
        ("request_rejected", RETRY_AT),
        ("response_protocol", RETRY_AT),
        ("transient_service", datetime(2026, 10, 1)),
    ],
)
def test_failure_value_rejects_unsafe_code_or_retry_deadline(
    code: str, retry_at: datetime | None
) -> None:
    with pytest.raises(ValueError) as error:
        budget_models.OutboundFailure(code, retry_at)
    assert "provider raw error body" not in str(error.value)


@pytest.mark.parametrize(
    "code, retry_at",
    [
        ("remote_result_unknown", RETRY_AT),
        ("transient_service", RETRY_AT + timedelta(seconds=1)),
        ("transient_service", None),
    ],
)
def test_failure_original_cannot_be_replaced(
    client: TestClient, writer: ExecutionWriter, code: str, retry_at: datetime | None
) -> None:
    original = reserve(client, writer)
    saved = record_failure(client, writer.scope, original.attempt_id)
    with pytest.raises(BudgetConflictError):
        record_failure(client, writer.scope, original.attempt_id, code=code, retry_at=retry_at)
    assert (
        transact(
            client, lambda s: budgets.read_outbound_attempt(s, writer.scope, original.attempt_id)
        )
        == saved
    )


@pytest.mark.parametrize("cost", [Decimal("0"), Decimal("0.02")])
def test_known_success_cost_cannot_acquire_failure(
    client: TestClient, writer: ExecutionWriter, cost: Decimal
) -> None:
    original = reserve(client, writer)
    transact(
        client,
        lambda s: budgets.record_attempt_cost(s, writer.scope, original.attempt_id, cost_usd=cost),
    )
    with pytest.raises(BudgetConflictError):
        record_failure(client, writer.scope, original.attempt_id)


@pytest.mark.parametrize("control", ["cancel", "replace"])
def test_late_failure_survives_cancel_or_writer_replacement(
    client: TestClient, writer: ExecutionWriter, control: str
) -> None:
    original = reserve(client, writer)
    if control == "cancel":
        transact(client, lambda s: service.finish_execution(s, writer, ExecutionStatus.CANCELLED))
        with pytest.raises(ExecutionStateError):
            reserve(client, writer)
    else:
        transact(
            client,
            lambda s: service.claim_writer(
                s, writer.scope, writer_id=uuid4(), replaces_writer_id=writer.writer_id
            ),
        )
    before = transact(client, lambda s: service.read_execution(s, writer.scope))
    saved = record_failure(client, writer.scope, original.attempt_id)
    assert saved.writer_id == writer.writer_id
    assert record_failure(client, writer.scope, original.attempt_id) == saved
    assert transact(client, lambda s: service.read_execution(s, writer.scope)) == before


def test_failure_writes_and_clock_reads_reject_wrong_scope(
    client: TestClient, writer: ExecutionWriter
) -> None:
    original = reserve(client, writer)
    for scope in (
        replace(writer.scope, job_file_id=uuid4()),
        replace(writer.scope, execution_id=uuid4()),
        replace(writer.scope, kind=ExecutionKind.MEMORY_BATCH),
    ):
        with pytest.raises(ExecutionNotFoundError):
            record_failure(client, scope, original.attempt_id)
        with pytest.raises(ExecutionNotFoundError):
            transact(client, lambda s, scope=scope: budgets.read_execution_time(s, scope))
    with pytest.raises(BudgetConflictError):
        record_failure(client, writer.scope, uuid4())
    assert (
        transact(
            client, lambda s: budgets.read_outbound_attempt(s, writer.scope, original.attempt_id)
        )
        == original
    )


def test_failures_retain_all_attempts_and_cost_reservations(
    client: TestClient, writer: ExecutionWriter
) -> None:
    original = reserve(client, writer)
    record_failure(client, writer.scope, original.attempt_id)
    attempts = [original]
    for _ in range(2):
        attempts.append(
            transact(
                client,
                lambda s: budgets.reserve_outbound_attempt(
                    s,
                    writer,
                    request=original.request,
                    attempt_id=uuid4(),
                    reserved_cost_usd=Decimal("0.1"),
                ),
            ).attempt
        )
    record_failure(
        client, writer.scope, attempts[1].attempt_id, code="request_rejected", retry_at=None
    )
    observed = transact(
        client,
        lambda s: budgets.read_request_attempts(s, writer.scope, original.request.request_id),
    )
    assert {attempt.attempt_id for attempt in observed} == {a.attempt_id for a in attempts}
    assert {attempt.attempt_id: attempt.failure for attempt in observed} == {
        original.attempt_id: budget_models.OutboundFailure("transient_service", RETRY_AT),
        attempts[1].attempt_id: budget_models.OutboundFailure("request_rejected", None),
        attempts[2].attempt_id: None,
    }
    usage = transact(client, lambda s: budgets.read_budget_usage(s, writer.scope))
    assert (usage.outbound_attempts, usage.model_steps) == (3, 1)
    assert usage.accounted_cost_usd == Decimal("0.3")
    with pytest.raises(BudgetExceededError) as error:
        reserve(client, writer)
    assert error.value.limit == BudgetLimit.COST


def test_late_cost_settlement_preserves_original_failure(
    client: TestClient, writer: ExecutionWriter
) -> None:
    original = reserve(client, writer)
    saved = record_failure(client, writer.scope, original.attempt_id)
    settled = transact(
        client,
        lambda s: budgets.record_attempt_cost(
            s, writer.scope, original.attempt_id, cost_usd=Decimal("0.02")
        ),
    )
    assert settled.failure == saved.failure
    assert record_failure(client, writer.scope, original.attempt_id) == settled


def test_concurrent_different_failures_have_one_original(
    client: TestClient, writer: ExecutionWriter
) -> None:
    original = reserve(client, writer)

    def compete(code: str) -> str | None:
        try:
            record_failure(client, writer.scope, original.attempt_id, code=code)
            return code
        except BudgetConflictError:
            return None

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(compete, ("transient_service", "remote_result_unknown")))
    assert results.count(None) == 1
    reread = transact(
        client, lambda s: budgets.read_outbound_attempt(s, writer.scope, original.attempt_id)
    )
    assert reread is not None and reread.failure is not None
    assert reread.failure.failure_code in results


def test_public_clock_uses_current_database_time_under_execution_lock(
    client: TestClient, writer: ExecutionWriter
) -> None:
    async def observe(session: AsyncSession) -> tuple[datetime, datetime, datetime]:
        await service.lock_active_writer(session, writer)
        before = (await session.execute(text("SELECT clock_timestamp()"))).scalar_one()
        actual = await budgets.read_execution_time(session, writer.scope)
        after = (await session.execute(text("SELECT clock_timestamp()"))).scalar_one()
        return before, actual, after

    before, actual, after = transact(client, observe)
    assert actual.utcoffset() is not None
    assert before <= actual <= after


def test_db_rejects_invalid_failure_pairs(
    client: TestClient, writer: ExecutionWriter, database_connection: psycopg.Connection
) -> None:
    original = reserve(client, writer)
    for code, retry_at in (
        ("raw provider error body", None),
        (None, RETRY_AT),
        ("access_blocked", RETRY_AT),
        ("capacity_exceeded", RETRY_AT),
        ("request_rejected", RETRY_AT),
        ("response_protocol", RETRY_AT),
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            database_connection.execute(
                "UPDATE execution_outbound_attempts SET failure_code = %s, retry_not_before = %s "
                "WHERE execution_id = %s AND attempt_id = %s",
                (code, retry_at, writer.scope.execution_id, original.attempt_id),
            )


def test_db_cannot_rewrite_failure_identity_or_observed_cost(
    client: TestClient, writer: ExecutionWriter, database_connection: psycopg.Connection
) -> None:
    original = reserve(client, writer)
    record_failure(client, writer.scope, original.attempt_id)
    transact(
        client,
        lambda s: budgets.record_attempt_cost(
            s, writer.scope, original.attempt_id, cost_usd=Decimal("0.02")
        ),
    )
    for assignments in (
        "failure_code = 'remote_result_unknown'",
        "failure_code = NULL, retry_not_before = NULL",
        "retry_not_before = NULL",
        "retry_not_before = retry_not_before + interval '1 second'",
        "request_id = gen_random_uuid()",
        "reserved_cost_usd = 0.01",
        "reported_cost_usd = NULL",
        "reported_cost_usd = 0",
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            database_connection.execute(
                f"UPDATE execution_outbound_attempts SET {assignments} "
                "WHERE execution_id = %s AND attempt_id = %s",
                (writer.scope.execution_id, original.attempt_id),
            )
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            "DELETE FROM execution_outbound_attempts WHERE execution_id = %s AND attempt_id = %s",
            (writer.scope.execution_id, original.attempt_id),
        )
    database_connection.execute(
        "UPDATE execution_outbound_attempts SET failure_code = failure_code, "
        "retry_not_before = retry_not_before WHERE execution_id = %s AND attempt_id = %s",
        (writer.scope.execution_id, original.attempt_id),
    )


def test_db_cannot_relabel_known_success_as_failure(
    client: TestClient, writer: ExecutionWriter, database_connection: psycopg.Connection
) -> None:
    original = reserve(client, writer)
    transact(
        client,
        lambda s: budgets.record_attempt_cost(
            s, writer.scope, original.attempt_id, cost_usd=Decimal("0")
        ),
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            "UPDATE execution_outbound_attempts SET failure_code = 'transient_service' "
            "WHERE execution_id = %s AND attempt_id = %s",
            (writer.scope.execution_id, original.attempt_id),
        )
