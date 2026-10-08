"""Last-resort settlement after normal workflow recovery is exhausted."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from caliburn.agent_execution.native_cleanup import await_native_cleanup
from caliburn.features.executions.models import ExecutionWriter

_LOG = logging.getLogger(__name__)


async def run_with_failure_boundary(
    writer: ExecutionWriter,
    *,
    run: Callable[[ExecutionWriter], Awaitable[object]],
    settle_failure: Callable[[ExecutionWriter, Exception], Awaitable[object]],
) -> object:
    """Settle through the original owner, which preserves any committed completion.

    No retry or independent outcome store. CancelledError deliberately propagates:
    stopping a process task is not a product cancellation. If settlement itself fails,
    the supervisor retains that failure; we must not claim a successful rollback.
    """
    try:
        return await run(writer)
    except asyncio.CancelledError as error:
        await await_native_cleanup(error)
        raise
    except Exception as error:
        await await_native_cleanup(error)
        _LOG.warning(
            "Execution stopped; reconciling its terminal outcome",
            extra={
                "execution_id": str(writer.scope.execution_id),
                "execution_kind": writer.scope.kind.value,
                "failure_kind": type(error).__name__,
            },
        )
        return await settle_failure(writer, error)
