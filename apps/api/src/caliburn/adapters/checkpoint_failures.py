"""Classify direct Psycopg failures for bounded recovery of fixed DB operations."""

from psycopg import OperationalError

_TRANSIENT_CHECKPOINT_SQLSTATES = frozenset(
    {
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
    }
)


def is_transient_checkpoint_failure(error: BaseException | None) -> bool:
    """Qualify a direct Psycopg failure after the caller fixes its recovery operation.

    The caller owns the original operation and its idempotent reconciliation;
    classification alone never authorizes transaction or provider replay.
    A no-SQLSTATE OperationalError can mean lost
    connectivity or pool timeout, but also connection/authentication configuration
    failure; the caller must bound attempts. Never inspect messages (which may
    contain sensitive DSNs) or walk exception causes, contexts or groups.
    """
    if not isinstance(error, OperationalError):
        return False
    return error.sqlstate is None or error.sqlstate in _TRANSIENT_CHECKPOINT_SQLSTATES
