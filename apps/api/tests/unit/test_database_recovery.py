"""Pure DB recovery rejects permanent driver states and propagates cancellation."""

import asyncio
import json
import logging

import psycopg
import pytest
from psycopg import errors
from sqlalchemy.exc import DBAPIError

from caliburn.adapters.database import is_transient_database_failure, retry_database_operation
from caliburn.adapters.logging import SafeJsonFormatter, bind_log_context


@pytest.mark.parametrize("sqlstate", ["40001", "40P01", "08006", "08007", "57P01", "53300"])
def test_direct_transient_driver_state_qualifies(sqlstate: str) -> None:
    error = DBAPIError.instance(None, None, errors.lookup(sqlstate)(), psycopg.Error)
    assert is_transient_database_failure(error)


@pytest.mark.parametrize("sqlstate", ["23505", "42P01", "28P01", "57014", "08P01"])
def test_invalidated_connection_cannot_override_permanent_state(sqlstate: str) -> None:
    error = DBAPIError.instance(
        None, None, errors.lookup(sqlstate)(), psycopg.Error, connection_invalidated=True
    )
    assert not is_transient_database_failure(error)


def test_bounded_recovery_rethrows_original_error() -> None:
    error = DBAPIError.instance(None, None, errors.SerializationFailure(), psycopg.Error)
    calls = []

    @retry_database_operation
    async def operation() -> None:
        calls.append(None)
        raise error

    with pytest.raises(type(error)) as failed:
        asyncio.run(operation())
    assert failed.value is error
    assert len(calls) == 3


def test_task_cancellation_during_database_await_propagates_once() -> None:
    calls = []

    async def scenario() -> None:
        entered = asyncio.Event()

        @retry_database_operation
        async def operation() -> None:
            calls.append(None)
            entered.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(operation())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert len(calls) == 1


def test_retry_events_identify_attempts_without_sensitive_error_text(caplog) -> None:
    error = DBAPIError.instance(
        "SELECT private_sql",
        {"secret_param": "private_parameter"},
        errors.SerializationFailure("postgresql://private_dsn private_driver_message"),
        psycopg.Error,
    )
    calls = 0

    @retry_database_operation
    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise error
        return "saved"

    with caplog.at_level(logging.WARNING, logger="caliburn.adapters.database"):
        with bind_log_context(execution_id="execution-1", response_id="response-1"):
            assert asyncio.run(operation()) == "saved"
            payloads = [json.loads(SafeJsonFormatter().format(record)) for record in caplog.records]
    assert [value["retry_attempt"] for value in payloads] == [1, 2]
    for value in payloads:
        assert value["event"] == "database.operation_retry"
        assert value["level"] == "WARNING"
        assert value["operation"] == operation.__qualname__
        assert value["failure_kind"] == "SerializationFailure"
        assert value["execution_id"] == "execution-1"
        assert value["response_id"] == "response-1"
    assert "private_" not in json.dumps(payloads)
    assert "secret_param" not in json.dumps(payloads)


@pytest.mark.parametrize("outcome", ["success", "permanent", "cancelled"])
def test_nonretry_outcomes_do_not_emit_retry_events(caplog, outcome: str) -> None:
    permanent = DBAPIError.instance(None, None, errors.InvalidPassword(), psycopg.Error)

    @retry_database_operation
    async def operation() -> None:
        if outcome == "permanent":
            raise permanent
        if outcome == "cancelled":
            raise asyncio.CancelledError

    with caplog.at_level(logging.WARNING, logger="caliburn.adapters.database"):
        if outcome == "success":
            asyncio.run(operation())
        else:
            with pytest.raises(
                asyncio.CancelledError if outcome == "cancelled" else type(permanent)
            ):
                asyncio.run(operation())
    assert not caplog.records
