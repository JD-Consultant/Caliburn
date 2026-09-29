"""Real transactions arbitrate the last allowance and preserve unknown external costs."""

import json
import subprocess
import sys
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import budgets, service
from caliburn.features.executions.budget_models import (
    BudgetConflictError,
    BudgetExceededError,
    BudgetLimit,
    ExecutionBudget,
    OutboundAdmission,
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
from caliburn.settings import DatabaseSettings

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


def policy(**changes: object) -> ExecutionBudget:
    return replace(
        ExecutionBudget(
            8, 4, 32, 3, datetime.now(UTC) + timedelta(hours=1), Decimal("1"), "synthetic-v1"
        ),
        **changes,
    )


def admit(client: TestClient, limits: ExecutionBudget) -> ExecutionWriter:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "合成額度", "employee_name": "合成員工"},
    )
    scope = ExecutionScope(
        UUID(created.json()["job_file_id"]), uuid4(), ExecutionKind.CONSULTANT_TURN
    )

    async def run(session: AsyncSession) -> ExecutionWriter:
        await service.admit_execution(session, scope)
        writer = await service.claim_writer(session, scope, writer_id=uuid4())
        await budgets.fix_execution_budget(session, writer, limits)
        return writer

    return transact(client, run)


def reserve(
    client: TestClient,
    writer: ExecutionWriter,
    *,
    request: OutboundRequest | None = None,
    attempt_id: UUID | None = None,
    cost: str = "0.1",
) -> OutboundAdmission:
    return transact(
        client,
        lambda s: budgets.reserve_outbound_attempt(
            s,
            writer,
            request=request or OutboundRequest(uuid4(), OutboundKind.MODEL, "a" * 64),
            attempt_id=attempt_id or uuid4(),
            reserved_cost_usd=Decimal(cost),
        ),
    )


def test_last_outbound_allowance_has_one_winner_across_connections(client: TestClient) -> None:
    writer = admit(client, policy(max_outbound_attempts=1))

    def compete(_: int) -> bool:
        try:
            reserve(client, writer)
            return True
        except BudgetExceededError as error:
            assert error.limit == BudgetLimit.OUTBOUND_ATTEMPTS
            return False

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert list(workers.map(compete, range(2))).count(True) == 1
    assert (
        transact(client, lambda s: budgets.read_budget_usage(s, writer.scope)).outbound_attempts
        == 1
    )


def test_unknown_attempt_reserves_cost_and_reentry_is_not_permission_to_send(
    client: TestClient,
) -> None:
    writer = admit(client, policy(max_cost_usd=Decimal("0.1")))
    request = OutboundRequest(uuid4(), OutboundKind.MODEL, "a" * 64)
    attempt_id = uuid4()
    assert reserve(client, writer, request=request, attempt_id=attempt_id).created
    # New transaction models lost commit acknowledgement; the original reservation survives.
    assert not reserve(client, writer, request=request, attempt_id=attempt_id).created
    with pytest.raises(BudgetExceededError) as error:
        reserve(client, writer, request=request)
    assert error.value.limit == BudgetLimit.COST
    usage = transact(client, lambda s: budgets.read_budget_usage(s, writer.scope))
    assert usage.accounted_cost_usd == Decimal("0.1")
    assert usage.model_steps == 1


@pytest.mark.parametrize(
    "limit, changes, kind",
    [
        (BudgetLimit.MODEL_STEPS, {"max_model_steps": 1}, OutboundKind.MODEL),
        (BudgetLimit.COMPACTIONS, {"max_compactions": 1}, OutboundKind.COMPACTION),
        (
            BudgetLimit.DEADLINE,
            {"deadline_at": datetime(2000, 1, 1, tzinfo=UTC)},
            OutboundKind.MODEL,
        ),
    ],
)
def test_independent_limits_are_enforced(
    client: TestClient, limit: BudgetLimit, changes: dict[str, object], kind: OutboundKind
) -> None:
    writer = admit(client, policy(**changes))
    if limit != BudgetLimit.DEADLINE:
        reserve(client, writer, request=OutboundRequest(uuid4(), kind, "a" * 64))
    with pytest.raises(BudgetExceededError) as error:
        reserve(client, writer, request=OutboundRequest(uuid4(), kind, "a" * 64))
    assert error.value.limit == limit


def test_request_retries_share_step_and_cannot_change_payload(client: TestClient) -> None:
    writer = admit(client, policy(max_model_steps=1, max_attempts_per_request=2))
    request = OutboundRequest(uuid4(), OutboundKind.MODEL, "a" * 64)
    original = reserve(client, writer, request=request)
    with pytest.raises(BudgetConflictError):
        reserve(client, writer, request=replace(request, fingerprint="b" * 64))
    with pytest.raises(BudgetConflictError):
        reserve(
            client,
            writer,
            request=replace(request, kind=OutboundKind.COMPACTION),
            attempt_id=original.attempt.attempt_id,
        )
    reserve(client, writer, request=request)
    with pytest.raises(BudgetExceededError) as error:
        reserve(client, writer, request=request)
    assert error.value.limit == BudgetLimit.REQUEST_ATTEMPTS
    usage = transact(client, lambda s: budgets.read_budget_usage(s, writer.scope))
    assert usage.model_steps == 1
    assert usage.outbound_attempts == 2


def test_count_and_compact_share_money_not_model_steps(client: TestClient) -> None:
    writer = admit(client, policy())
    for kind in OutboundKind:
        reserve(client, writer, request=OutboundRequest(uuid4(), kind, "a" * 64))
    usage = transact(client, lambda s: budgets.read_budget_usage(s, writer.scope))
    assert (usage.model_steps, usage.compactions, usage.outbound_attempts) == (1, 1, 3)
    assert usage.accounted_cost_usd == Decimal("0.3")


def test_cancelled_work_accepts_original_accounting_but_no_new_send(client: TestClient) -> None:
    writer = admit(client, policy())
    original = reserve(client, writer)
    transact(client, lambda s: service.finish_execution(s, writer, ExecutionStatus.CANCELLED))
    with pytest.raises(ExecutionStateError):
        reserve(client, writer)
    for _ in range(2):
        recorded = transact(
            client,
            lambda s: budgets.record_attempt_cost(
                s, writer.scope, original.attempt.attempt_id, cost_usd=Decimal("0.02")
            ),
        )
        assert recorded.reported_cost_usd == Decimal("0.02")
    with pytest.raises(BudgetConflictError):
        transact(
            client,
            lambda s: budgets.record_attempt_cost(
                s, writer.scope, original.attempt.attempt_id, cost_usd=Decimal("0")
            ),
        )
    assert (
        transact(client, lambda s: service.read_execution(s, writer.scope)).status
        == ExecutionStatus.CANCELLED
    )


def test_replacement_does_not_reset_policy_or_cost(client: TestClient) -> None:
    limits = policy(max_cost_usd=Decimal("0.1"))
    writer = admit(client, limits)
    original = reserve(client, writer)
    replacement = transact(
        client,
        lambda s: service.claim_writer(
            s, writer.scope, writer_id=uuid4(), replaces_writer_id=writer.writer_id
        ),
    )
    transact(client, lambda s: budgets.fix_execution_budget(s, replacement, limits))
    with pytest.raises(BudgetConflictError):
        transact(client, lambda s: budgets.fix_execution_budget(s, replacement, policy()))
    with pytest.raises(BudgetExceededError):
        reserve(client, replacement)
    # Late measured costs are recorded even if above the estimate; do not falsify spending.
    transact(
        client,
        lambda s: budgets.record_attempt_cost(
            s, writer.scope, original.attempt.attempt_id, cost_usd=Decimal("0.2")
        ),
    )
    assert transact(
        client, lambda s: budgets.read_budget_usage(s, writer.scope)
    ).accounted_cost_usd == Decimal("0.2")
    wrong_scope = replace(writer.scope, job_file_id=uuid4())
    with pytest.raises(ExecutionNotFoundError):
        transact(
            client,
            lambda s: budgets.read_outbound_attempt(s, wrong_scope, original.attempt.attempt_id),
        )


def test_db_rejects_erasing_accounting_history(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    writer = admit(client, policy())
    reserve(client, writer)
    for statement in (
        "DELETE FROM execution_budgets WHERE execution_id = %s",
        "UPDATE execution_budgets SET max_cost_usd = 99 WHERE execution_id = %s",
        "DELETE FROM execution_outbound_attempts WHERE execution_id = %s",
        "UPDATE execution_outbound_attempts SET reserved_cost_usd = 0.01 WHERE execution_id = %s",
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            database_connection.execute(statement, (writer.scope.execution_id,))


def test_fresh_process_keeps_existing_limits_and_reservations(
    client: TestClient, database_settings: DatabaseSettings
) -> None:
    writer = admit(client, policy(max_outbound_attempts=1))
    reserve(client, writer)
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[1] / "fixtures/budget_worker.py"),
            database_settings.schema,
            str(writer.scope.job_file_id),
            str(writer.scope.execution_id),
            str(writer.writer_id),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"denied": "outbound_attempts", "attempts": 1}
