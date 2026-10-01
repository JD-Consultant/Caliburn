"""Retry confirmed transient failures, preserving the original work's durable limits."""

import asyncio
import json
import traceback
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx2
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest, create_responses_client
from caliburn.agent_execution.response_retries import ResponseRetryPolicy
from caliburn.agent_execution.tool_steps import _build_response_step, run_response_step
from caliburn.features.executions import budgets, service
from caliburn.features.executions.budget_models import (
    BudgetExceededError,
    BudgetLimit,
    ExecutionBudget,
)
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.workflows import model_requests
from caliburn.workflows.model_requests import (
    ModelRequestAccounting,
    ModelRequestExecutor,
    ModelRequestFailedError,
    PriorModelAttemptError,
)
from tests.fixtures.response_capacity import synthetic_response_runtime
from tests.fixtures.response_transport import response_http_reply

pytestmark = pytest.mark.postgres


@pytest.fixture
def retry_file_id(database_connection):
    file_id = uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,creation_command_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,%s,'重試','重試','合成人員')",
        (file_id, uuid4()),
    )
    return file_id


def request_fixture():
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic role",
        input_items=[],
        tools=[],
        reasoning_effort="low",
        max_output_tokens=512,
    )


def success_fixture():
    return json.loads(
        (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(encoding="utf-8")
    )


def rejection(status=429, code="rate_limit_exceeded", *, delay="0"):
    return httpx2.Response(
        status,
        headers={"retry-after": delay},
        json={"error": {"message": "sensitive synthetic detail", "code": code}},
    )


@asynccontextmanager
async def retry_executor(
    settings, file_id, respond, *, attempts=3, outbound_attempts=32, cost="1", deadline_seconds=60
):
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
                    4,
                    outbound_attempts,
                    attempts,
                    datetime.now(UTC) + timedelta(seconds=deadline_seconds),
                    Decimal(cost),
                    "synthetic-v1",
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
                ModelRequestAccounting(
                    "synthetic-v1",
                    lambda input_tokens, max_output_tokens: Decimal("0.1"),
                    lambda _: Decimal("0.01"),
                    token_count_reservation_usd=Decimal("0.001"),
                    compaction_reservation_usd=Decimal("0.2"),
                    observed_compaction_cost=lambda _: Decimal("0.02"),
                ),
                retry_policy=ResponseRetryPolicy(0.001, 0.001, 0.001, 0.001),
            )
    finally:
        await database.close()


def test_transient_rejection_retries_same_payload_with_new_budgeted_attempt(
    database_settings,
    database_connection,
):
    file_id = uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,creation_command_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,%s,'重试','重试','合成人員')",
        (file_id, uuid4()),
    )

    async def scenario():
        database = Database(database_settings)
        requests = []
        response_json = json.loads(
            (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(
                encoding="utf-8"
            )
        )

        async def respond(request):
            requests.append(json.loads(request.content))
            # Admission is committed and no transaction remains open across HTTP.
            async with asyncio.timeout(3), database.sessions.begin() as session:
                await service.lock_active_writer(session, writer)
                usage = await budgets.read_budget_usage(session, scope)
                assert usage.outbound_attempts == len(requests)
            if len(requests) == 1:
                return httpx2.Response(
                    429,
                    headers={"retry-after": "0"},
                    json={"error": {"message": "synthetic limit", "code": "rate_limit_exceeded"}},
                )
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
                request = ResponseRequest(
                    model="gpt-6-luna",
                    instructions="synthetic role",
                    input_items=[],
                    tools=[],
                    reasoning_effort="low",
                    max_output_tokens=512,
                )
                request_id = uuid4()
                result = await executor.request_model(request, request_id, 100)
                assert result.response.id == response_json["id"]
                assert len(requests) == 2
                assert requests[0] == requests[1] == request.create_payload()
                async with database.sessions.begin() as session:
                    attempts = await budgets.read_request_attempts(session, scope, request_id)
                    usage = await budgets.read_budget_usage(session, scope)
                assert len({attempt.attempt_id for attempt in attempts}) == 2
                assert result.attempt_id in {attempt.attempt_id for attempt in attempts}
                assert usage.model_steps == 1
                assert usage.accounted_cost_usd == Decimal("0.2")
                assert all(attempt.reported_cost_usd is None for attempt in attempts)
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


@pytest.mark.parametrize("operation", ["count_input", "request_compaction"])
def test_count_and_compaction_share_one_retry_owner(
    database_settings, retry_file_id, operation, caplog
):
    calls = []
    success = (
        {"object": "response.input_tokens", "input_tokens": 123}
        if operation == "count_input"
        else {
            "object": "response.compaction",
            "id": "cmp_synthetic",
            "created_at": 1790000000,
            "output": [{"type": "compaction", "id": "ci_synthetic", "encrypted_content": "opaque"}],
            "usage": {
                "input_tokens": 120,
                "output_tokens": 30,
                "total_tokens": 150,
                "input_tokens_details": {"cached_tokens": 20},
                "output_tokens_details": {"reasoning_tokens": 10},
            },
        }
    )

    def respond(request):
        calls.append((request.url.path, json.loads(request.content)))
        return rejection(503) if len(calls) == 1 else httpx2.Response(200, json=success)

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond) as executor:
            result = await getattr(executor, operation)(request_fixture(), uuid4())
            if operation == "count_input":
                assert result["input_tokens"] == 123
            else:
                assert result.response.id == "cmp_synthetic"
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.outbound_attempts == 2
            assert usage.model_steps == 0
            assert usage.compactions == (1 if operation == "request_compaction" else 0)
            assert calls[0] == calls[1]
            diagnostics = [r for r in caplog.records if r.name == model_requests.__name__]
            assert len(diagnostics) == 1
            message = diagnostics[0].getMessage()
            assert "http_status=503" in message
            assert "provider_code=rate_limit_exceeded" in message
            assert "sensitive synthetic detail" not in caplog.text

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


@pytest.mark.parametrize(
    ("status", "code"),
    [(401, "invalid_api_key"), (429, "insufficient_quota"), (400, "context_length_exceeded")],
)
def test_blocked_provider_failure_does_not_retry_on_reentry(
    database_settings,
    retry_file_id,
    caplog,
    status,
    code,
):
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return rejection(status, code)

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond) as executor:
            request_id = uuid4()
            with pytest.raises(ModelRequestFailedError):
                await executor.request_model(request_fixture(), request_id, 100)
            with pytest.raises(PriorModelAttemptError):
                await replace(executor).request_model(request_fixture(), request_id, 100)
            async with executor.sessions.begin() as session:
                attempts = await budgets.read_request_attempts(
                    session, executor.writer.scope, request_id
                )
            assert len(attempts) == len(calls) == 1
            assert attempts[0].failure.retry_not_before is None
            assert "sensitive" not in repr(attempts)
            diagnostics = [r for r in caplog.records if r.name == model_requests.__name__]
            assert len(diagnostics) == 1
            message = diagnostics[0].getMessage()
            assert f"http_status={status}" in message
            assert f"provider_code={code}" in message
            assert f"request_id={request_id}" in message
            assert f"attempt_id={attempts[0].attempt_id}" in message
            assert f"execution_id={executor.writer.scope.execution_id}" in message
            assert diagnostics[0].exc_info is None
            assert "sensitive synthetic detail" not in caplog.text

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


@pytest.mark.parametrize(
    ("status", "code", "max_attempts", "cost", "delay", "expected_limit", "expected_calls"),
    [
        (503, "server_error", 2, "1", "0", BudgetLimit.REQUEST_ATTEMPTS, 2),
        (429, "rate_limit_exceeded", 5, "0.25", "0", BudgetLimit.COST, 2),
        (429, "rate_limit_exceeded", 5, "1", "86400", BudgetLimit.DEADLINE, 1),
    ],
)
def test_retry_uses_original_limits_across_executor_reentry(
    database_settings,
    retry_file_id,
    status,
    code,
    max_attempts,
    cost,
    delay,
    expected_limit,
    expected_calls,
):
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return rejection(status, code, delay=delay)

    async def scenario():
        async with retry_executor(
            database_settings,
            retry_file_id,
            respond,
            attempts=max_attempts,
            cost=cost,
        ) as executor:
            request_id = uuid4()
            for active_executor in (executor, replace(executor)):
                with pytest.raises(BudgetExceededError) as caught:
                    await active_executor.request_model(request_fixture(), request_id, 100)
                assert caught.value.limit == expected_limit
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.outbound_attempts == len(calls) == expected_calls
            assert usage.accounted_cost_usd == Decimal("0.1") * expected_calls

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


@pytest.mark.parametrize("cancel_during_wait", [False, True])
def test_retry_delay_survives_restart_and_cancellation_is_checked_before_resend(
    database_settings,
    retry_file_id,
    monkeypatch,
    cancel_during_wait,
):
    calls = []
    failure_before_restart = None

    async def scenario():
        async def respond(request):
            calls.append(request.url.path)
            if len(calls) == 1:
                return rejection(delay="0.15")
            async with executor.sessions.begin() as session:
                now = await budgets.read_execution_time(session, executor.writer.scope)
                assert now >= failure_before_restart.retry_not_before
            return httpx2.Response(200, json=success_fixture())

        async with retry_executor(database_settings, retry_file_id, respond) as executor:
            request_id = uuid4()

            async def interrupt_wait(seconds):
                # An independent short transaction succeeds while the workflow is waiting.
                async with asyncio.timeout(3), executor.sessions.begin() as session:
                    await service.lock_active_writer(session, executor.writer)
                    if cancel_during_wait:
                        await service.finish_execution(
                            session, executor.writer, ExecutionStatus.CANCELLED
                        )
                raise ConnectionError("synthetic process interrupted while backing off")

            with monkeypatch.context() as patch:
                patch.setattr(model_requests, "sleep", interrupt_wait)
                with pytest.raises(ConnectionError, match="interrupted while backing off"):
                    await executor.request_model(request_fixture(), request_id, 100)
            assert len(calls) == 1
            async with executor.sessions.begin() as session:
                attempts = await budgets.read_request_attempts(
                    session, executor.writer.scope, request_id
                )
            nonlocal failure_before_restart
            failure_before_restart = attempts[0].failure
            # New coordinator, no in-process response/attempt needed. Saved delay wins.
            resumed = replace(
                executor, retry_policy=ResponseRetryPolicy(0.0001, 0.0001, 0.0001, 0.0001)
            )
            if cancel_during_wait:
                with pytest.raises(ExecutionStateError):
                    await resumed.request_model(request_fixture(), request_id, 100)
                assert len(calls) == 1
            else:
                await resumed.request_model(request_fixture(), request_id, 100)
                assert len(calls) == 2
            async with executor.sessions.begin() as session:
                original = await budgets.read_outbound_attempt(
                    session, executor.writer.scope, attempts[0].attempt_id
                )
            assert original.failure == failure_before_restart

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


@pytest.mark.parametrize(
    ("cost", "outbound_attempts", "expected_limit"),
    [("0.1", 32, BudgetLimit.COST), ("1", 1, BudgetLimit.OUTBOUND_ATTEMPTS)],
)
def test_exhausted_work_budget_stops_before_retry_wait(
    database_settings, retry_file_id, monkeypatch, cost, outbound_attempts, expected_limit
):
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return rejection(delay="30")

    async def forbidden_wait(seconds):
        pytest.fail("Known exhausted work budget must stop before retry waiting")

    async def scenario():
        async with retry_executor(
            database_settings,
            retry_file_id,
            respond,
            cost=cost,
            outbound_attempts=outbound_attempts,
        ) as executor:
            monkeypatch.setattr(model_requests, "sleep", forbidden_wait)
            with pytest.raises(BudgetExceededError) as caught:
                await executor.request_model(request_fixture(), uuid4(), 100)
            assert caught.value.limit == expected_limit
            assert len(calls) == 1
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.outbound_attempts == 1

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


@pytest.mark.parametrize("failure_was_committed", [False, True])
def test_failure_save_must_be_confirmed_or_reconciled_before_resend(
    database_settings,
    retry_file_id,
    failure_was_committed,
):
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return rejection() if len(calls) == 1 else httpx2.Response(200, json=success_fixture())

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond) as executor:

            class FaultedFailureSave:
                @asynccontextmanager
                async def begin(self):
                    async with executor.sessions.begin() as session:
                        yield session
                        if calls and not failure_was_committed:
                            raise ConnectionError("synthetic failure record not committed")
                    if calls:
                        raise ConnectionError("synthetic failure record acknowledgement lost")

            request_id = uuid4()
            with pytest.raises(ConnectionError, match="synthetic failure record") as caught:
                await replace(executor, sessions=FaultedFailureSave()).request_model(
                    request_fixture(),
                    request_id,
                    100,
                )
            assert "sensitive synthetic detail" not in "".join(
                traceback.format_exception(caught.value)
            )
            assert len(calls) == 1
            if failure_was_committed:
                await replace(executor).request_model(request_fixture(), request_id, 100)
                assert len(calls) == 2
            else:
                with pytest.raises(PriorModelAttemptError):
                    await replace(executor).request_model(request_fixture(), request_id, 100)
                assert len(calls) == 1

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


@pytest.mark.parametrize(
    ("status", "code", "delay"),
    [
        (401, "invalid_api_key", "0"),
        (429, "insufficient_quota", "0"),
        (429, "rate_limit_exceeded", "1e999"),
    ],
)
def test_provider_body_does_not_escape_into_graph_error_or_traceback(
    database_settings, retry_file_id, status, code, delay
):
    def respond(request):
        return rejection(status, code, delay=delay)

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond) as executor:

            async def ensure_active():
                async with executor.sessions.begin() as session:
                    await service.lock_active_writer(session, executor.writer)

            async def no_tool(*args):
                pytest.fail("A rejected model request cannot produce tool work")

            runtime = synthetic_response_runtime(
                executor.request_model, no_tool, no_tool, ensure_active, executor.account_response
            )
            dsn = make_conninfo(
                database_settings.url, options=f"-c search_path={database_settings.schema}"
            )
            thread_id = str(uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer()
            ) as saver:
                await saver.setup()
                with pytest.raises(ModelRequestFailedError) as caught:
                    await run_response_step(
                        saver,
                        thread_id=thread_id,
                        request=request_fixture(),
                        runtime=runtime,
                        max_tool_calls=16,
                    )
                saved = await _build_response_step(saver, max_tool_calls=16).aget_state(config)
                assert any(task.error for task in saved.tasks)
                assert "sensitive synthetic detail" not in repr(saved.tasks)
                assert "sensitive synthetic detail" not in "".join(
                    traceback.format_exception(caught.value)
                )

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


@pytest.mark.parametrize("cancel_boundary", ["connection", "commit"])
def test_cancelled_failure_save_stops_without_leaking_provider_body(
    database_settings, retry_file_id, cancel_boundary
):
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return rejection()

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond) as executor:
            request_id = uuid4()
            with pytest.raises(TimeoutError) as caught:
                async with asyncio.timeout(None) as timeout:

                    class CancelledFailureSave:
                        @asynccontextmanager
                        async def begin(self):
                            if calls and cancel_boundary == "connection":
                                timeout.reschedule(asyncio.get_running_loop().time())
                                await asyncio.Event().wait()
                            async with executor.sessions.begin() as session:
                                yield session
                                if calls and cancel_boundary == "commit":
                                    timeout.reschedule(asyncio.get_running_loop().time())
                                    await asyncio.Event().wait()

                    await replace(executor, sessions=CancelledFailureSave()).request_model(
                        request_fixture(), request_id, 100
                    )
            assert "sensitive synthetic detail" not in "".join(
                traceback.format_exception(caught.value)
            )
            with pytest.raises(PriorModelAttemptError):
                await executor.request_model(request_fixture(), request_id, 100)
            assert len(calls) == 1

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


def test_two_retry_runners_cannot_both_send_after_one_recorded_failure(
    database_settings,
    retry_file_id,
    monkeypatch,
):
    async def scenario():
        calls = []
        entered = asyncio.Event()
        release = asyncio.Event()

        async def respond(request):
            calls.append(request.url.path)
            if len(calls) == 1:
                return rejection(delay="0.1")
            entered.set()
            await release.wait()
            return httpx2.Response(200, json=success_fixture())

        async def interrupted_wait(seconds):
            raise ConnectionError("synthetic stop before retry")

        async with retry_executor(database_settings, retry_file_id, respond) as executor:
            request_id = uuid4()
            with monkeypatch.context() as patch:
                patch.setattr(model_requests, "sleep", interrupted_wait)
                with pytest.raises(ConnectionError, match="synthetic stop"):
                    await executor.request_model(request_fixture(), request_id, 100)
            async with asyncio.timeout(5), asyncio.TaskGroup() as group:
                first = group.create_task(
                    executor.request_model(request_fixture(), request_id, 100)
                )
                await entered.wait()
                try:
                    with pytest.raises(PriorModelAttemptError):
                        await replace(executor).request_model(request_fixture(), request_id, 100)
                finally:
                    release.set()
            assert first.result().response.id == success_fixture()["id"]
            assert len(calls) == 2
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.outbound_attempts == 2

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


def stream_error_reply(code="rate_limit_exceeded", error_type="tokens"):
    """A provider error delivered as an event inside an already open HTTP 200 stream."""
    frame = {
        "error": {
            "message": "sensitive synthetic detail",
            "type": error_type,
            "param": None,
            "code": code,
        }
    }
    return httpx2.Response(
        200, headers={"Content-Type": "text/event-stream"}, content=f"data: {json.dumps(frame)}\n\n"
    )


def streaming_request():
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic role",
        input_items=[],
        tools=[],
        reasoning_effort="low",
        max_output_tokens=512,
        stream=True,
    )


def test_rate_limit_inside_a_stream_is_retried_and_recorded_as_a_rate_limit(
    database_settings, retry_file_id, caplog
):
    calls = []

    def respond(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            return stream_error_reply()
        return response_http_reply(request, success_fixture())

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond) as executor:
            request, request_id = streaming_request(), uuid4()
            result = await executor.request_model(request, request_id, 100)
            assert result.response.id == success_fixture()["id"]
            # The same payload is sent again under a new, budgeted attempt.
            assert len(calls) == 2
            assert calls[0] == calls[1] == request.create_payload()
            async with executor.sessions.begin() as session:
                attempts = await budgets.read_request_attempts(
                    session, executor.writer.scope, request_id
                )
            failures = [a.failure for a in attempts if a.failure is not None]
            assert [f.failure_code for f in failures] == ["rate_limited"]
            assert failures[0].retry_not_before is not None
            diagnostics = [r for r in caplog.records if r.name == model_requests.__name__]
            assert len(diagnostics) == 1
            message = diagnostics[0].getMessage()
            assert "provider_code=rate_limit_exceeded" in message
            assert "http_status=None" in message
            assert f"request_id={request_id}" in message
            assert diagnostics[0].exc_info is None

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


def test_unknown_error_inside_a_stream_stops_without_retry(
    database_settings, retry_file_id, caplog
):
    calls = []

    def respond(request):
        calls.append(request)
        return stream_error_reply("private employee text echoed as code", "invalid_request_error")

    async def scenario():
        async with retry_executor(database_settings, retry_file_id, respond) as executor:
            with pytest.raises(ModelRequestFailedError) as stopped:
                await executor.request_model(streaming_request(), uuid4(), 100)
            assert stopped.value.failure.kind.value == "response_protocol"
            assert len(calls) == 1
            diagnostics = [r for r in caplog.records if r.name == model_requests.__name__]
            assert len(diagnostics) == 1
            assert "provider_code=None" in diagnostics[0].getMessage()
            assert "private employee text" not in caplog.text
            assert diagnostics[0].exc_info is None

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


def test_a_rate_limit_waits_instead_of_spending_the_attempt_budget(
    database_settings, retry_file_id
):
    """The provider asked us to slow down; that is not a failure of the work. Five rejections
    outlast a budget of two tries, and the sixth send still succeeds."""
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) <= 5:
            return rejection()
        return response_http_reply(request, success_fixture())

    async def scenario():
        async with retry_executor(
            database_settings, retry_file_id, respond, attempts=2, outbound_attempts=32
        ) as executor:
            request_id = uuid4()
            result = await executor.request_model(request_fixture(), request_id, 100)
            assert result.response.id == success_fixture()["id"]
            assert len(calls) == 6
            async with executor.sessions.begin() as session:
                attempts = await budgets.read_request_attempts(
                    session, executor.writer.scope, request_id
                )
            codes = [a.failure.failure_code for a in attempts if a.failure is not None]
            assert codes == ["rate_limited"] * 5

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


def test_a_service_fault_still_stops_at_the_attempt_budget_even_after_rate_limits(
    database_settings, retry_file_id
):
    calls = []

    def respond(request):
        calls.append(request)
        return rejection() if len(calls) <= 3 else rejection(503, "server_error")

    async def scenario():
        async with retry_executor(
            database_settings, retry_file_id, respond, attempts=2, outbound_attempts=32
        ) as executor:
            with pytest.raises(BudgetExceededError) as caught:
                await executor.request_model(request_fixture(), uuid4(), 100)
            assert caught.value.limit == BudgetLimit.REQUEST_ATTEMPTS
            # Three rate limits did not count; the two service faults that followed did.
            assert len(calls) == 5

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


def test_endless_rate_limits_still_end_at_the_executions_overall_attempt_limit(
    database_settings, retry_file_id
):
    calls = []

    def respond(request):
        calls.append(request)
        return rejection()

    async def scenario():
        async with retry_executor(
            database_settings, retry_file_id, respond, attempts=2, outbound_attempts=6
        ) as executor:
            with pytest.raises(BudgetExceededError) as caught:
                await executor.request_model(request_fixture(), uuid4(), 100)
            assert caught.value.limit == BudgetLimit.OUTBOUND_ATTEMPTS
            assert len(calls) == 6

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
