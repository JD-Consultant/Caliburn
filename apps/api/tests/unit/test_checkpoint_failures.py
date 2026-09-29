"""Only direct saver-driver failures can qualify for bounded original-result resaving."""

import asyncio
from concurrent.futures import CancelledError

import psycopg
import pytest
from psycopg import errors
from psycopg_pool import PoolTimeout

from caliburn.adapters.checkpoint_failures import is_transient_checkpoint_failure


@pytest.mark.parametrize(
    "sqlstate",
    [
        "08000",
        "08001",
        "08003",
        "08004",
        "08006",
        "08007",
        "57P01",
        "57P02",
        "57P03",
        "53300",
        "40001",
        "40P01",
    ],
)
def test_known_transport_shutdown_capacity_and_transaction_failures_qualify(
    sqlstate: str,
) -> None:
    error = errors.lookup(sqlstate)()

    assert is_transient_checkpoint_failure(error) is True


@pytest.mark.parametrize(
    "sqlstate",
    [
        "08P01",
        "28000",
        "28P01",
        "42000",
        "42501",
        "42601",
        "42P01",
        "23000",
        "23502",
        "23503",
        "23505",
        "23514",
        "57014",
        "57P04",
        "57P05",
        "40000",
        "40002",
        "40003",
        "53000",
        "53100",
        "53200",
        "53400",
        "55P03",
        "XX000",
    ],
)
def test_protocol_auth_programming_integrity_cancellation_and_unlisted_states_do_not_qualify(
    sqlstate: str,
) -> None:
    error = errors.lookup(sqlstate)()

    assert is_transient_checkpoint_failure(error) is False


@pytest.mark.parametrize(
    "error_type", [psycopg.OperationalError, errors.ConnectionTimeout, PoolTimeout]
)
def test_no_sqlstate_operational_failure_qualifies_for_bounded_resaving(
    error_type: type[psycopg.OperationalError],
) -> None:
    assert is_transient_checkpoint_failure(error_type()) is True


@pytest.mark.parametrize("sqlstate", ["08ZZZ", "ZZ999", ""])
def test_unrecognized_sqlstate_does_not_get_the_no_sqlstate_allowance(sqlstate: str) -> None:
    error = psycopg.OperationalError()
    error.sqlstate = sqlstate

    assert is_transient_checkpoint_failure(error) is False


@pytest.mark.parametrize(
    "error",
    [
        None,
        psycopg.Error(),
        psycopg.DatabaseError(),
        psycopg.InterfaceError(),
        psycopg.DataError(),
        psycopg.IntegrityError(),
        psycopg.ProgrammingError(),
        psycopg.InternalError(),
        psycopg.NotSupportedError(),
        ValueError(),
        TypeError(),
        ConnectionError(),
        TimeoutError(),
        asyncio.CancelledError(),
        CancelledError(),
        ExceptionGroup("checkpoint failures", [errors.ConnectionFailure()]),
        BaseExceptionGroup("cancelled checkpoint", [asyncio.CancelledError(), PoolTimeout()]),
    ],
)
def test_absent_non_operational_foreign_and_grouped_errors_do_not_qualify(
    error: BaseException | None,
) -> None:
    assert is_transient_checkpoint_failure(error) is False


@pytest.mark.parametrize("chain_attribute", ["__cause__", "__context__"])
@pytest.mark.parametrize(
    "outer_type", [RuntimeError, ValueError, errors.ProtocolViolation, errors.InvalidPassword]
)
def test_transient_nested_error_does_not_override_the_direct_failure(
    chain_attribute: str, outer_type: type[Exception]
) -> None:
    outer = outer_type()
    setattr(outer, chain_attribute, errors.ConnectionFailure())

    assert is_transient_checkpoint_failure(outer) is False


def test_foreign_error_with_matching_sqlstate_does_not_qualify() -> None:
    class ForeignConnectionError(ConnectionError):
        sqlstate = "08006"

    assert is_transient_checkpoint_failure(ForeignConnectionError()) is False


@pytest.mark.parametrize(
    ("sqlstate", "expected"), [(None, True), ("08006", True), ("28P01", False)]
)
def test_classification_does_not_read_exception_message(
    sqlstate: str | None, expected: bool
) -> None:
    class UnreadableMessageError(psycopg.OperationalError):
        def __str__(self) -> str:
            raise AssertionError("Exception text must not be inspected")

    error = UnreadableMessageError()
    error.sqlstate = sqlstate

    assert is_transient_checkpoint_failure(error) is expected
