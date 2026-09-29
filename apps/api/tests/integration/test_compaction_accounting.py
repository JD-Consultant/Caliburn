"""Real PG admission/accounting around SDK MockTransport; no remote provider calls."""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

import httpx2
import psycopg
import pytest
from openai.types.responses.compacted_response import CompactedResponse

from caliburn.adapters.database import Database
from caliburn.adapters.openai_responses import ResponseRequest, create_responses_client
from caliburn.adapters.response_serialization import snapshot_compaction
from caliburn.agent_execution.context_compaction import ReceivedCompaction
from caliburn.agent_execution.response_retries import ResponseRetryPolicy
from caliburn.features.executions import budgets, service
from caliburn.features.executions.budget_models import (
    BudgetConflictError,
    BudgetExceededError,
    BudgetLimit,
    ExecutionBudget,
    OutboundKind,
    OutboundRequest,
)
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.settings import DatabaseSettings
from caliburn.workflows.model_requests import (
    ModelRequestAccounting,
    ModelRequestExecutor,
    ModelUsageUnavailableError,
    PriorCompactionAttemptError,
)

pytestmark = pytest.mark.postgres


@pytest.fixture
def runner() -> Iterator[asyncio.Runner]:
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as value:
        yield value


@pytest.fixture
def file_id(database_connection: psycopg.Connection) -> UUID:
    value = uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,creation_command_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,%s,'compact','compact','synthetic')",
        (value, uuid4()),
    )
    return value


def request_fixture() -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic role outside compact payload",
        input_items=[
            {"role": "user", "content": "合成工作"},
            {
                "type": "reasoning",
                "id": "rs_synthetic",
                "summary": [],
                "encrypted_content": "synthetic-opaque-input",
            },
        ],
        tools=[],
        reasoning_effort="low",
        max_output_tokens=512,
    )


def compaction_fixture() -> dict[str, object]:
    return {
        "id": "cmp_synthetic",
        "created_at": 1_790_000_000,
        "object": "response.compaction",
        "output": [
            {"type": "message", "role": "user", "content": "合成工作"},
            {
                "type": "compaction",
                "id": "ci_synthetic",
                "encrypted_content": "synthetic-opaque-output",
                "provider_extension": {"retained": True},
            },
        ],
        "usage": {
            "input_tokens": 120,
            "input_tokens_details": {"cached_tokens": 20},
            "output_tokens": 30,
            "output_tokens_details": {"reasoning_tokens": 10},
            "total_tokens": 150,
        },
        "provider_extension": {"original": True},
    }


def accounting_fixture(
    observed: Callable[[CompactedResponse], Decimal | None],
) -> ModelRequestAccounting:
    return ModelRequestAccounting(
        "synthetic-v1",
        Decimal("0.1"),
        lambda _: pytest.fail("Compaction must not use model pricing"),
        token_count_reservation_usd=Decimal("0.001"),
        compaction_reservation_usd=Decimal("0.2"),
        observed_compaction_cost=observed,
    )


@asynccontextmanager
async def admitted_executor(
    settings: DatabaseSettings,
    file_id: UUID,
    respond: Callable[[httpx2.Request], httpx2.Response | Awaitable[httpx2.Response]],
    accounting: ModelRequestAccounting,
    *,
    max_compactions: int = 4,
) -> AsyncIterator[ModelRequestExecutor]:
    database = Database(settings)
    try:
        scope = ExecutionScope(file_id, uuid4(), ExecutionKind.CONSULTANT_TURN)
        async with database.sessions.begin() as session:
            await service.admit_execution(session, scope)
            writer = await service.claim_writer(session, scope, writer_id=uuid4())
            await budgets.fix_execution_budget(
                session,
                writer,
                ExecutionBudget(
                    8,
                    max_compactions,
                    32,
                    3,
                    datetime.now(UTC) + timedelta(hours=1),
                    Decimal("1"),
                    accounting.cost_basis,
                ),
            )
        async with create_responses_client(
            api_key="synthetic-only",
            timeout_seconds=5,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        ) as client:
            yield ModelRequestExecutor(
                database.sessions,
                writer,
                client,
                accounting,
                retry_policy=ResponseRetryPolicy(0.001, 0.001),
            )
    finally:
        await database.close()


def test_committed_admission_precedes_one_compact_and_original_precedes_accounting(
    database_settings: DatabaseSettings, file_id: UUID, runner: asyncio.Runner
) -> None:
    async def scenario() -> None:
        http_requests = []
        observed_responses = []
        request_id = uuid4()
        raw = compaction_fixture()

        def observed(response: CompactedResponse) -> Decimal:
            observed_responses.append(response)
            assert snapshot_compaction(response) == raw
            return Decimal("0.03")

        async def respond(request: httpx2.Request) -> httpx2.Response:
            http_requests.append(request)
            assert request.url.path == "/v1/responses/compact"
            # A second transaction can take the lock and observe COMMIT during HTTP.
            async with asyncio.timeout(3), executor.sessions.begin() as session:
                await service.lock_active_writer(session, executor.writer)
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
                attempts = await budgets.read_request_attempts(
                    session, executor.writer.scope, request_id
                )
            assert usage.outbound_attempts == usage.compactions == 1
            assert usage.model_steps == 0
            assert usage.accounted_cost_usd == Decimal("0.2")
            assert len(attempts) == 1
            assert attempts[0].request.kind == OutboundKind.COMPACTION
            assert attempts[0].reported_cost_usd is None
            expected_payload = {
                "model": "gpt-6-luna",
                "service_tier": "default",
                "input": [
                    {"role": "user", "content": "合成工作"},
                    {
                        "type": "reasoning",
                        "id": "rs_synthetic",
                        "summary": [],
                        "encrypted_content": "synthetic-opaque-input",
                    },
                ],
            }
            assert json.loads(request.content) == expected_payload
            canonical = json.dumps(
                expected_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            )
            assert attempts[0].request.fingerprint == sha256(canonical.encode()).hexdigest()
            return httpx2.Response(200, json=raw)

        async with admitted_executor(
            database_settings, file_id, respond, accounting_fixture(observed)
        ) as executor:
            received = await executor.request_compaction(request_fixture(), request_id)
            assert isinstance(received.response, CompactedResponse)
            assert snapshot_compaction(received.response) == raw
            assert observed_responses == [], "Hand original C to Graph before evaluating cost"
            async with executor.sessions.begin() as session:
                attempt = await budgets.read_outbound_attempt(
                    session, executor.writer.scope, received.attempt_id
                )
            assert attempt is not None and attempt.request.request_id == request_id
            assert attempt.reported_cost_usd is None
            await executor.account_compaction(received)
            await executor.account_compaction(received)
            assert all(response is received.response for response in observed_responses)
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.accounted_cost_usd == Decimal("0.03")
            assert usage.outbound_attempts == usage.compactions == len(http_requests) == 1
            assert usage.model_steps == 0

    runner.run(scenario())


@pytest.mark.parametrize("missing", ["compaction_reservation_usd", "observed_compaction_cost"])
def test_missing_compaction_policy_stops_before_admission_and_http(
    database_settings: DatabaseSettings, file_id: UUID, runner: asyncio.Runner, missing: str
) -> None:
    async def scenario() -> None:
        def respond(request: httpx2.Request) -> httpx2.Response:
            pytest.fail("No HTTP without explicit compaction policy")

        policy = replace(accounting_fixture(lambda _: Decimal("0.03")), **{missing: None})
        async with admitted_executor(database_settings, file_id, respond, policy) as executor:
            with pytest.raises(ValueError, match="compaction"):
                await executor.request_compaction(request_fixture(), uuid4())
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.outbound_attempts == 0
            assert usage.accounted_cost_usd == 0

    runner.run(scenario())


@pytest.mark.parametrize("failure", ["unknown", "calculation_error"])
def test_unavailable_compaction_cost_keeps_original_and_reservation(
    database_settings: DatabaseSettings, file_id: UUID, runner: asyncio.Runner, failure: str
) -> None:
    async def scenario() -> None:
        http_requests = []
        calculations = []

        def respond(request: httpx2.Request) -> httpx2.Response:
            http_requests.append(request)
            return httpx2.Response(200, json=compaction_fixture())

        def observed(response: CompactedResponse) -> None:
            calculations.append(response)
            if failure == "calculation_error":
                raise ArithmeticError("synthetic pricing unavailable")

        async with admitted_executor(
            database_settings, file_id, respond, accounting_fixture(observed)
        ) as executor:
            received = await executor.request_compaction(request_fixture(), uuid4())
            assert snapshot_compaction(received.response) == compaction_fixture()
            assert calculations == []
            expected = (
                ArithmeticError if failure == "calculation_error" else ModelUsageUnavailableError
            )
            with pytest.raises(expected):
                await executor.account_compaction(received)
            async with executor.sessions.begin() as session:
                attempt = await budgets.read_outbound_attempt(
                    session, executor.writer.scope, received.attempt_id
                )
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert attempt is not None and attempt.reported_cost_usd is None
            assert usage.accounted_cost_usd == Decimal("0.2")
            assert len(http_requests) == 1
            assert calculations == [received.response]
            # Reliable zero is valid only when the explicitly supplied calculator observes it.
            recovered = replace(executor, accounting=accounting_fixture(lambda _: Decimal("0")))
            await recovered.account_compaction(received)
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.accounted_cost_usd == 0
            assert len(http_requests) == 1

    runner.run(scenario())


@pytest.mark.parametrize("failure_boundary", ["admission_ack", "http_timeout"])
def test_unknown_admission_stops_and_confirmed_timeouts_exhaust_original_budget(
    database_settings: DatabaseSettings,
    file_id: UUID,
    runner: asyncio.Runner,
    failure_boundary: str,
) -> None:
    async def scenario() -> None:
        http_requests = []
        request_id = uuid4()

        def timeout(request: httpx2.Request) -> httpx2.Response:
            http_requests.append(request)
            raise httpx2.ReadTimeout("synthetic timeout", request=request)

        async with admitted_executor(
            database_settings, file_id, timeout, accounting_fixture(lambda _: Decimal("0.03"))
        ) as executor:

            class CommitAcknowledgementLoss:
                @asynccontextmanager
                async def begin(self):
                    async with executor.sessions.begin() as session:
                        yield session
                    raise ConnectionError("synthetic admission acknowledgement lost")

            initial = (
                replace(executor, sessions=CommitAcknowledgementLoss())
                if failure_boundary == "admission_ack"
                else executor
            )
            expected = (
                ConnectionError if failure_boundary == "admission_ack" else BudgetExceededError
            )
            with pytest.raises(expected):
                await initial.request_compaction(request_fixture(), request_id)
            # Reconstruct the executor; no process-local attempt identity authorizes a resend.
            recovered = replace(executor)
            resume_error = (
                PriorCompactionAttemptError
                if failure_boundary == "admission_ack"
                else BudgetExceededError
            )
            with pytest.raises(resume_error):
                await recovered.request_compaction(request_fixture(), request_id)
            expected_attempts = 1 if failure_boundary == "admission_ack" else 3
            assert len(http_requests) == (0 if failure_boundary == "admission_ack" else 3)
            async with executor.sessions.begin() as session:
                attempts = await budgets.read_request_attempts(
                    session, executor.writer.scope, request_id
                )
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert len(attempts) == usage.outbound_attempts == expected_attempts
            assert usage.compactions == 1
            assert usage.model_steps == 0
            assert all(attempt.reported_cost_usd is None for attempt in attempts)
            assert usage.accounted_cost_usd == Decimal("0.2") * expected_attempts

    runner.run(scenario())


@pytest.mark.parametrize("commit_cost", [False, True])
def test_cancelled_execution_can_settle_original_after_accounting_failure(
    database_settings: DatabaseSettings, file_id: UUID, runner: asyncio.Runner, commit_cost: bool
) -> None:
    async def scenario() -> None:
        http_requests = []

        async def respond(request: httpx2.Request) -> httpx2.Response:
            http_requests.append(request)
            # Cancellation wins while compact is in flight; returning/accounting C stays legal.
            async with executor.sessions.begin() as session:
                await service.finish_execution(session, executor.writer, ExecutionStatus.CANCELLED)
            return httpx2.Response(200, json=compaction_fixture())

        async with admitted_executor(
            database_settings, file_id, respond, accounting_fixture(lambda _: Decimal("0.03"))
        ) as executor:
            received = await executor.request_compaction(request_fixture(), uuid4())

            class AccountingFault:
                @asynccontextmanager
                async def begin(self):
                    async with executor.sessions.begin() as session:
                        yield session
                        if not commit_cost:
                            raise ConnectionError("synthetic accounting failure")
                    raise ConnectionError("synthetic accounting acknowledgement lost")

            with pytest.raises(ConnectionError):
                await replace(executor, sessions=AccountingFault()).account_compaction(received)
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.accounted_cost_usd == (Decimal("0.03") if commit_cost else Decimal("0.2"))
            assert snapshot_compaction(received.response) == compaction_fixture()
            recovered = replace(executor)
            await recovered.account_compaction(received)
            await recovered.account_compaction(received)
            with pytest.raises(ExecutionStateError):
                await recovered.request_compaction(request_fixture(), uuid4())
            conflicting = replace(
                executor, accounting=accounting_fixture(lambda _: Decimal("0.04"))
            )
            with pytest.raises(BudgetConflictError):
                await conflicting.account_compaction(received)
            async with executor.sessions.begin() as session:
                execution = await service.read_execution(session, executor.writer.scope)
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert execution.status == ExecutionStatus.CANCELLED
            assert usage.accounted_cost_usd == Decimal("0.03")
            assert usage.outbound_attempts == usage.compactions == len(http_requests) == 1

    runner.run(scenario())


@pytest.mark.parametrize("changed_field", ["model", "input", "instructions"])
def test_same_logical_request_checks_only_exact_compact_payload_and_never_resends(
    database_settings: DatabaseSettings, file_id: UUID, runner: asyncio.Runner, changed_field: str
) -> None:
    async def scenario() -> None:
        http_requests = []

        def respond(request: httpx2.Request) -> httpx2.Response:
            http_requests.append(request)
            return httpx2.Response(200, json=compaction_fixture())

        async with admitted_executor(
            database_settings, file_id, respond, accounting_fixture(lambda _: Decimal("0.03"))
        ) as executor:
            request_id = uuid4()
            await executor.request_compaction(request_fixture(), request_id)
            snapshot = request_fixture().create_payload()
            snapshot[changed_field] = {
                "model": "gpt-6-sol",
                "input": [{"role": "user", "content": "changed synthetic input"}],
                "instructions": "changed, but not sent to compact",
            }[changed_field]
            expected = (
                PriorCompactionAttemptError
                if changed_field == "instructions"
                else BudgetConflictError
            )
            with pytest.raises(expected):
                await executor.request_compaction(
                    ResponseRequest.from_snapshot(snapshot), request_id
                )
            assert len(http_requests) == 1
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.outbound_attempts == usage.compactions == 1

    runner.run(scenario())


@pytest.mark.parametrize("kind", [None, OutboundKind.MODEL, OutboundKind.TOKEN_COUNT])
def test_accounting_requires_matching_compaction_admission(
    database_settings: DatabaseSettings,
    file_id: UUID,
    runner: asyncio.Runner,
    kind: OutboundKind | None,
) -> None:
    async def scenario() -> None:
        def respond(request: httpx2.Request) -> httpx2.Response:
            pytest.fail("Accounting must never issue HTTP")

        async with admitted_executor(
            database_settings, file_id, respond, accounting_fixture(lambda _: Decimal("0.03"))
        ) as executor:
            attempt_id = uuid4()
            if kind is not None:
                async with executor.sessions.begin() as session:
                    await budgets.reserve_outbound_attempt(
                        session,
                        executor.writer,
                        request=OutboundRequest(uuid4(), kind, "a" * 64),
                        attempt_id=attempt_id,
                        reserved_cost_usd=Decimal("0.2"),
                    )
            received = ReceivedCompaction(
                CompactedResponse.model_construct(**compaction_fixture()), attempt_id
            )
            with pytest.raises(BudgetConflictError):
                await executor.account_compaction(received)
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.accounted_cost_usd == (
                Decimal("0.2") if kind is not None else Decimal("0")
            )

    runner.run(scenario())


@pytest.mark.parametrize("cost", [Decimal("0.03"), Decimal("1.2")])
def test_compaction_limits_and_observed_overrun_stop_next_http(
    database_settings: DatabaseSettings, file_id: UUID, runner: asyncio.Runner, cost: Decimal
) -> None:
    async def scenario() -> None:
        http_requests = []

        def respond(request: httpx2.Request) -> httpx2.Response:
            http_requests.append(request)
            return httpx2.Response(200, json=compaction_fixture())

        async with admitted_executor(
            database_settings,
            file_id,
            respond,
            accounting_fixture(lambda _: cost),
            max_compactions=1 if cost < 1 else 4,
        ) as executor:
            received = await executor.request_compaction(request_fixture(), uuid4())
            await executor.account_compaction(received)
            with pytest.raises(BudgetExceededError) as stopped:
                await executor.request_compaction(request_fixture(), uuid4())
            assert stopped.value.limit == (
                BudgetLimit.COMPACTIONS if cost < 1 else BudgetLimit.COST
            )
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.accounted_cost_usd == cost
            assert usage.outbound_attempts == usage.compactions == len(http_requests) == 1

    runner.run(scenario())
