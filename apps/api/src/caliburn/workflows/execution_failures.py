"""Last-resort settlement after normal workflow recovery is exhausted."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from caliburn.adapters.logging import bind_log_context
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
    with bind_log_context(
        job_file_id=writer.scope.job_file_id,
        execution_id=writer.scope.execution_id,
        execution_kind=writer.scope.kind.value,
        writer_id=writer.writer_id,
    ):
        _LOG.info("execution.runner_started")
        try:
            result = await run(writer)
            # Runner 返回不等於正式完成；正式結果仍由原 owner 判定。
            _LOG.info("execution.runner_returned")
            return result
        except asyncio.CancelledError as error:
            await await_native_cleanup(error)
            _LOG.info("execution.runner_interrupted")
            raise
        except Exception as error:
            await await_native_cleanup(error)
            _LOG.warning("execution.reconciling", extra={"failure_kind": type(error).__name__})
            try:
                return await settle_failure(writer, error)
            except Exception as settlement_error:
                _LOG.error(
                    "execution.settlement_failed",
                    extra={"failure_kind": type(settlement_error).__name__},
                )
                raise
