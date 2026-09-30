"""An owner reconciliation is not an unlimited or transferable resend permit."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import httpx2
import pytest

from caliburn.features.executions import budgets, service
from caliburn.features.executions.budget_models import BudgetExceededError, BudgetLimit
from caliburn.features.executions.models import ExecutionStateError, ExecutionStatus
from caliburn.workflows.model_requests import (
    PriorAttemptRecovery,
    PriorCompactionAttemptError,
    PriorInputCountAttemptError,
    PriorModelAttemptError,
)
from tests.integration.test_outbound_retry import (
    request_fixture,
    retry_executor,
    success_fixture,
)
from tests.integration.test_outbound_retry import (
    retry_file_id as retry_file_id,
)

pytestmark = pytest.mark.postgres


def run(scenario):
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


async def attempts_for(executor, request_id):
    async with executor.sessions.begin() as session:
        return await budgets.read_request_attempts(session, executor.writer.scope, request_id)


@pytest.mark.parametrize(
    "disposition",
    [PriorAttemptRecovery.ORIGINAL_AVAILABLE, PriorAttemptRecovery.IN_FLIGHT_OR_UNKNOWN],
)
def test_available_or_unknown_original_never_resends(database_settings, retry_file_id, disposition):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx2.Response(200, json=success_fixture())

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond) as executor:
            request_id = uuid4()
            original = await executor.request_model(request_fixture(), request_id)
            checks = []

            async def reconcile(writer, attempts):
                checks.append(attempts)
                assert writer == executor.writer
                assert [attempt.attempt_id for attempt in attempts] == [original.attempt_id]
                # The common caller must release its DB lock before consulting the owner.
                async with asyncio.timeout(3), executor.sessions.begin() as session:
                    await service.lock_active_writer(session, writer)
                return disposition

            with pytest.raises(PriorModelAttemptError) as stopped:
                await replace(executor, reconcile_prior_attempts=reconcile).request_model(
                    request_fixture(), request_id
                )
            assert stopped.value.recovery is disposition
            assert len(checks) == 1
            assert len(await attempts_for(executor, request_id)) == len(calls) == 1

    run(scenario)


@pytest.mark.parametrize("operation", ["request_model", "count_input", "request_compaction"])
def test_confirmed_lost_original_adds_budgeted_attempt_without_erasing_old_one(
    database_settings, retry_file_id, operation
):
    calls = []

    def respond(request):
        calls.append(request.content)
        if operation == "count_input":
            body = {"object": "response.input_tokens", "input_tokens": 123}
        elif operation == "request_compaction":
            body = {
                "object": "response.compaction",
                "id": "cmp_synthetic",
                "created_at": 1790000000,
                "output": [{"type": "compaction", "id": "ci", "encrypted_content": "opaque"}],
                "usage": {
                    "input_tokens": 120,
                    "output_tokens": 30,
                    "total_tokens": 150,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens_details": {"reasoning_tokens": 0},
                },
            }
        else:
            body = success_fixture()
        return httpx2.Response(200, json=body)

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond) as executor:
            request_id = uuid4()
            await getattr(executor, operation)(request_fixture(), request_id)
            original = await attempts_for(executor, request_id)
            async with executor.sessions.begin() as session:
                replacement = await service.claim_writer(
                    session,
                    executor.writer.scope,
                    writer_id=uuid4(),
                    replaces_writer_id=executor.writer.writer_id,
                )
            # A takeover alone proves neither producer exit nor loss of a held result.
            executor = replace(executor, writer=replacement)
            with pytest.raises(
                (
                    PriorModelAttemptError,
                    PriorInputCountAttemptError,
                    PriorCompactionAttemptError,
                )
            ):
                await getattr(executor, operation)(request_fixture(), request_id)

            async def reconcile(writer, attempts):
                assert attempts == original
                assert all(attempt.writer_id != writer.writer_id for attempt in attempts)
                return PriorAttemptRecovery.LOCAL_ORIGINAL_UNRECOVERABLE

            recovered = replace(executor, reconcile_prior_attempts=reconcile)
            await getattr(recovered, operation)(request_fixture(), request_id)
            attempts = await attempts_for(executor, request_id)
            assert len(attempts) == len(calls) == 2
            assert original[0] in attempts  # No fake failure, deletion, or settlement.
            assert len({attempt.attempt_id for attempt in attempts}) == 2
            assert all(attempt.request == original[0].request for attempt in attempts)
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.accounted_cost_usd == original[0].reserved_cost_usd * 2
            assert usage.model_steps == (operation == "request_model")
            assert usage.compactions == (operation == "request_compaction")
            assert calls[0] == calls[1]

    run(scenario)


@pytest.mark.parametrize(
    ("options", "limit"),
    [
        ({"attempts": 1}, BudgetLimit.REQUEST_ATTEMPTS),
        ({"outbound_attempts": 1}, BudgetLimit.OUTBOUND_ATTEMPTS),
        ({"cost": "0.15"}, BudgetLimit.COST),
    ],
)
def test_reconciliation_does_not_reset_original_budget(
    database_settings, retry_file_id, options, limit
):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx2.Response(200, json=success_fixture())

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond, **options) as executor:
            request_id = uuid4()
            await executor.request_model(request_fixture(), request_id)

            async def reconcile(writer, attempts):
                return PriorAttemptRecovery.LOCAL_ORIGINAL_UNRECOVERABLE

            with pytest.raises(BudgetExceededError) as stopped:
                await replace(executor, reconcile_prior_attempts=reconcile).request_model(
                    request_fixture(), request_id
                )
            assert stopped.value.limit is limit
            assert len(await attempts_for(executor, request_id)) == len(calls) == 1

    run(scenario)


def test_cancel_during_reconciliation_prevents_readmission(database_settings, retry_file_id):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx2.Response(200, json=success_fixture())

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond) as executor:
            request_id = uuid4()
            await executor.request_model(request_fixture(), request_id)

            async def reconcile(writer, attempts):
                async with executor.sessions.begin() as session:
                    await service.finish_execution(
                        session, writer, outcome=ExecutionStatus.CANCELLED
                    )
                return PriorAttemptRecovery.LOCAL_ORIGINAL_UNRECOVERABLE

            with pytest.raises(ExecutionStateError):
                await replace(executor, reconcile_prior_attempts=reconcile).request_model(
                    request_fixture(), request_id
                )
            assert len(await attempts_for(executor, request_id)) == len(calls) == 1

    run(scenario)


def test_two_reconciliations_cannot_authorize_duplicate_new_attempts(
    database_settings, retry_file_id
):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx2.Response(200, json=success_fixture())

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond) as executor:
            request_id = uuid4()
            await executor.request_model(request_fixture(), request_id)
            original = await attempts_for(executor, request_id)
            barrier = asyncio.Barrier(2)
            checks = []

            async def reconcile(writer, attempts):
                assert attempts == original
                checks.append(attempts)
                await barrier.wait()
                return PriorAttemptRecovery.LOCAL_ORIGINAL_UNRECOVERABLE

            recovered = replace(executor, reconcile_prior_attempts=reconcile)
            async with asyncio.timeout(5):
                outcomes = await asyncio.gather(
                    recovered.request_model(request_fixture(), request_id),
                    recovered.request_model(request_fixture(), request_id),
                    return_exceptions=True,
                )
            assert sum(isinstance(value, PriorModelAttemptError) for value in outcomes) == 1
            assert len(checks) == 2  # Never re-probe the competitor's new, unknown attempt.
            assert len(await attempts_for(executor, request_id)) == len(calls) == 2
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.accounted_cost_usd == Decimal("0.2")

    run(scenario)


@pytest.mark.parametrize("change", ["writer", "settlement", "deadline"])
def test_recheck_after_owner_await_rejects_stale_evidence(database_settings, retry_file_id, change):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx2.Response(200, json=success_fixture())

    async def scenario():
        async with retry_executor(
            database_settings,
            retry_file_id,
            respond,
            deadline_seconds=2 if change == "deadline" else 60,
        ) as executor:
            request_id = uuid4()
            await executor.request_model(request_fixture(), request_id)

            async def reconcile(writer, attempts):
                async with executor.sessions.begin() as session:
                    if change == "writer":
                        await service.claim_writer(
                            session,
                            writer.scope,
                            writer_id=uuid4(),
                            replaces_writer_id=writer.writer_id,
                        )
                    elif change == "settlement":
                        await budgets.record_attempt_cost(
                            session, writer.scope, attempts[0].attempt_id, cost_usd=Decimal("0.01")
                        )
                    else:
                        policy = await budgets.read_execution_budget(session, writer.scope)
                if change == "deadline":
                    await asyncio.sleep(
                        max(0, (policy.deadline_at - datetime.now(UTC)).total_seconds()) + 0.02
                    )
                return PriorAttemptRecovery.LOCAL_ORIGINAL_UNRECOVERABLE

            error = {
                "writer": ExecutionStateError,
                "settlement": PriorModelAttemptError,
                "deadline": BudgetExceededError,
            }[change]
            with pytest.raises(error) as stopped:
                await replace(executor, reconcile_prior_attempts=reconcile).request_model(
                    request_fixture(), request_id
                )
            if change == "deadline":
                assert stopped.value.limit is BudgetLimit.DEADLINE
            assert len(await attempts_for(executor, request_id)) == len(calls) == 1

    run(scenario)


@pytest.mark.parametrize("fault", ["unavailable", "untyped"])
def test_failed_or_untyped_owner_check_fails_closed(database_settings, retry_file_id, fault):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx2.Response(200, json=success_fixture())

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond) as executor:
            request_id = uuid4()
            await executor.request_model(request_fixture(), request_id)

            async def reconcile(writer, attempts):
                if fault == "unavailable":
                    raise ConnectionError("synthetic reconciliation unavailable")
                return "local_original_unrecoverable"

            with pytest.raises(
                ConnectionError if fault == "unavailable" else PriorModelAttemptError
            ):
                await replace(executor, reconcile_prior_attempts=reconcile).request_model(
                    request_fixture(), request_id
                )
            assert len(await attempts_for(executor, request_id)) == len(calls) == 1

    run(scenario)


def test_known_failure_after_readmission_still_uses_existing_retry_budget(
    database_settings, retry_file_id
):
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) == 2:
            return httpx2.Response(503, json={"error": {"message": "synthetic unavailable"}})
        return httpx2.Response(200, json=success_fixture())

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond) as executor:
            request_id = uuid4()
            await executor.request_model(request_fixture(), request_id)
            checks = []

            async def reconcile(writer, attempts):
                checks.append(attempts)
                return PriorAttemptRecovery.LOCAL_ORIGINAL_UNRECOVERABLE

            await replace(executor, reconcile_prior_attempts=reconcile).request_model(
                request_fixture(), request_id
            )
            attempts = await attempts_for(executor, request_id)
            assert len(attempts) == len(calls) == 3
            assert len(checks) == 1
            assert sum(attempt.failure is not None for attempt in attempts) == 1
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.accounted_cost_usd == Decimal("0.3")

    run(scenario)
