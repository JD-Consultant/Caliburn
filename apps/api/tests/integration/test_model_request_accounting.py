"""One admission per logical request; a saved R survives billing faults without requery."""

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4, uuid5

import httpx2
import psycopg
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest, create_responses_client
from caliburn.agent_execution.response_retries import ResponseRetryPolicy
from caliburn.agent_execution.tool_steps import (
    _build_response_step,
    run_response_step,
)
from caliburn.features.executions import budgets, service
from caliburn.features.executions.budget_models import BudgetExceededError, ExecutionBudget
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
    PriorInputCountAttemptError,
    PriorModelAttemptError,
)
from tests.fixtures.response_capacity import synthetic_response_runtime

pytestmark = pytest.mark.postgres


def request_fixture() -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic fixed role",
        input_items=[],
        tools=[],
        reasoning_effort="low",
        max_output_tokens=512,
    )


@pytest.mark.parametrize("cancel_after_fault", [False, True])
@pytest.mark.parametrize("commit_cost", [False, True])
def test_saved_response_is_settled_after_ack_loss_without_querying_model_again(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    cancel_after_fault: bool,
    commit_cost: bool,
) -> None:
    file_id = uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,creation_command_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,%s,'計量','計量','合成人員')",
        (file_id, uuid4()),
    )

    async def scenario() -> None:
        database = Database(database_settings)
        http_requests = []
        response_json = json.loads(
            (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(
                encoding="utf-8"
            )
        )

        async def respond(request):
            # An independent transaction must observe committed admission during HTTP.
            async with asyncio.timeout(3), database.sessions.begin() as session:
                await service.lock_active_writer(session, writer)
                usage = await budgets.read_budget_usage(session, scope)
            assert usage.outbound_attempts == 1, "Commit admission before sending the model request"
            http_requests.append(json.loads(request.content))
            return httpx2.Response(200, json=response_json)

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
                        4,
                        32,
                        3,
                        datetime.now(UTC) + timedelta(hours=1),
                        Decimal("1"),
                        "synthetic-v1",
                    ),
                )
            async with create_responses_client(
                api_key="synthetic-only",
                timeout_seconds=5,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
            ) as client:
                executor = ModelRequestExecutor(
                    database.sessions,
                    writer,
                    client,
                    ModelRequestAccounting(
                        "synthetic-v1",
                        lambda input_tokens, max_output_tokens: Decimal("0.1"),
                        lambda _: Decimal("0.01"),
                    ),
                )
                observations = []

                async def ensure_active():
                    async with database.sessions.begin() as session:
                        await service.lock_active_writer(session, writer)

                async def prepare(call, operation_id):
                    observations.append(call.call_id)
                    return "synthetic original result"

                async def execute(prepared):
                    pytest.fail("Read-only synthetic fixture")

                async def account_then_lose_ack(received):
                    if commit_cost:
                        await executor.account_response(received)
                    raise ConnectionError("synthetic accounting acknowledgement lost")

                runtime = synthetic_response_runtime(
                    executor.request_model, prepare, execute, ensure_active, account_then_lose_ack
                )
                connection_string = make_conninfo(
                    database_settings.url,
                    options=f"-c search_path={database_settings.schema}",
                )
                async with AsyncPostgresSaver.from_conn_string(
                    connection_string, serde=create_graph_serializer()
                ) as saver:
                    await saver.setup()
                    options = {"thread_id": str(uuid4()), "max_tool_calls": 16}
                    with pytest.raises(ConnectionError, match="accounting acknowledgement"):
                        await run_response_step(
                            saver, request=request_fixture(), runtime=runtime, **options
                        )
                    assert len(http_requests) == 1
                    assert observations == []
                    async with database.sessions.begin() as session:
                        usage = await budgets.read_budget_usage(session, scope)
                        expected_cost = Decimal("0.01") if commit_cost else Decimal("0.1")
                        assert usage.accounted_cost_usd == expected_cost
                        if cancel_after_fault:
                            await service.finish_execution(
                                session, writer, ExecutionStatus.CANCELLED
                            )
                    resumed_runtime = replace(runtime, account_response=executor.account_response)
                    if cancel_after_fault:
                        with pytest.raises(ExecutionStateError):
                            await run_response_step(
                                saver, request=None, runtime=resumed_runtime, **options
                            )
                        assert observations == []
                    else:
                        result = await run_response_step(
                            saver, request=None, runtime=resumed_runtime, **options
                        )
                        assert result["response_snapshot"] == response_json
                        assert len(observations) == 1
                    assert len(http_requests) == 1
                    async with database.sessions.begin() as session:
                        usage = await budgets.read_budget_usage(session, scope)
                        assert usage.outbound_attempts == usage.model_steps == 1
                        assert usage.accounted_cost_usd == Decimal("0.01")
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


@pytest.mark.parametrize("failure_boundary", ["admission_ack", "http_timeout"])
@pytest.mark.parametrize("outbound_kind", ["model", "count"])
def test_resume_keeps_unknown_admission_blocked_and_confirmed_timeouts_bounded(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    failure_boundary: str,
    outbound_kind: str,
) -> None:
    file_id = uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,creation_command_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,%s,'准入','准入','合成人員')",
        (file_id, uuid4()),
    )

    async def scenario():
        database = Database(database_settings)
        http_requests = []

        def timeout(request):
            http_requests.append(json.loads(request.content))
            raise httpx2.ReadTimeout("synthetic timeout", request=request)

        class CommitAcknowledgementLoss:
            @asynccontextmanager
            async def begin(self):
                async with database.sessions.begin() as session:
                    yield session
                raise ConnectionError("synthetic admission acknowledgement lost")

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
                        4,
                        32,
                        3,
                        datetime.now(UTC) + timedelta(hours=1),
                        Decimal("1"),
                        "synthetic-v1",
                    ),
                )
            async with create_responses_client(
                api_key="synthetic-only",
                timeout_seconds=5,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(timeout)),
            ) as client:
                executor = ModelRequestExecutor(
                    database.sessions,
                    writer,
                    client,
                    ModelRequestAccounting(
                        "synthetic-v1",
                        lambda input_tokens, max_output_tokens: Decimal("0.1"),
                        lambda _: Decimal("0.01"),
                        token_count_reservation_usd=Decimal("0.001"),
                    ),
                    retry_policy=ResponseRetryPolicy(0.001, 0.001),
                )
                initial_executor = (
                    replace(executor, sessions=CommitAcknowledgementLoss())
                    if failure_boundary == "admission_ack"
                    else executor
                )

                async def ensure_active():
                    async with database.sessions.begin() as session:
                        await service.lock_active_writer(session, writer)

                async def prepare(call, operation_id):
                    pytest.fail("No result permits tool preparation")

                async def execute(prepared):
                    pytest.fail("No tool is prepared")

                runtime = synthetic_response_runtime(
                    initial_executor.request_model,
                    prepare,
                    execute,
                    ensure_active,
                    executor.account_response,
                )
                if outbound_kind == "count":
                    runtime = replace(runtime, count_input=initial_executor.count_input)
                dsn = make_conninfo(
                    database_settings.url, options=f"-c search_path={database_settings.schema}"
                )
                thread_id = str(uuid4())
                options = {"thread_id": thread_id, "max_tool_calls": 16}
                expected = (
                    ConnectionError if failure_boundary == "admission_ack" else BudgetExceededError
                )
                async with AsyncPostgresSaver.from_conn_string(
                    dsn, serde=create_graph_serializer()
                ) as saver:
                    await saver.setup()
                    with pytest.raises(expected):
                        await run_response_step(
                            saver, request=request_fixture(), runtime=runtime, **options
                        )
                    config = {"configurable": {"thread_id": thread_id}}
                    saved = await _build_response_step(saver, max_tool_calls=16).aget_state(config)
                    assert saved.values["request_snapshot"] == request_fixture().create_payload()
                    request_id = saved.values["request_id"]
                    outbound_id = (
                        uuid5(request_id, "input_tokens")
                        if outbound_kind == "count"
                        else request_id
                    )
                    assert "response_snapshot" not in saved.values
                # A new saver and executor have no in-memory attempt identity to rely on.
                async with AsyncPostgresSaver.from_conn_string(
                    dsn, serde=create_graph_serializer()
                ) as saver:
                    prior_error = (
                        PriorInputCountAttemptError
                        if outbound_kind == "count"
                        else PriorModelAttemptError
                    )
                    if failure_boundary == "http_timeout":
                        prior_error = BudgetExceededError
                    resumed_runtime = replace(runtime, request_model=executor.request_model)
                    if outbound_kind == "count":
                        resumed_runtime = replace(resumed_runtime, count_input=executor.count_input)
                    with pytest.raises(prior_error):
                        await run_response_step(
                            saver,
                            request=None,
                            runtime=resumed_runtime,
                            **options,
                        )
                    saved = await _build_response_step(saver, max_tool_calls=16).aget_state(config)
                    assert saved.values["request_id"] == request_id
                expected_attempts = 1 if failure_boundary == "admission_ack" else 3
                assert len(http_requests) == (0 if failure_boundary == "admission_ack" else 3)
                async with database.sessions.begin() as session:
                    attempts = await budgets.read_request_attempts(session, scope, outbound_id)
                    usage = await budgets.read_budget_usage(session, scope)
                assert len(attempts) == usage.outbound_attempts == expected_attempts
                assert usage.model_steps == (1 if outbound_kind == "model" else 0)
                assert all(attempt.reported_cost_usd is None for attempt in attempts)
                assert (
                    usage.accounted_cost_usd
                    == (Decimal("0.1") if outbound_kind == "model" else Decimal("0.001"))
                    * expected_attempts
                )
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
