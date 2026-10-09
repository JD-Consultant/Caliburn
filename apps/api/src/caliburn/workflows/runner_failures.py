"""Retain an invocation's safe disposition and explicit originals, never its stack."""

import logging
from asyncio import CancelledError
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.agent_execution.context_compaction import (
    CompactionSaveError,
    HeldCompaction,
    HeldPreparationCount,
    PreparationCountSaveError,
)
from caliburn.agent_execution.result_save_retries import ResultSaveCancelledError
from caliburn.agent_execution.tool_steps import (
    HeldInputCount,
    HeldModelResponse,
    InputCountSaveError,
    ReceivedModelResponse,
    ReceivedModelResponseCancelledError,
    ReceivedModelResponseError,
    ResponseStepSaveError,
)
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionScope, ExecutionStatus

_LOG = logging.getLogger(__name__)

type RecoveryHandoff = (
    HeldModelResponse
    | HeldInputCount
    | HeldCompaction
    | HeldPreparationCount
    | ReceivedModelResponse
)


@dataclass(frozen=True, slots=True)
class RunnerFailure:
    error_type: str
    interrupted: bool
    recovery: RecoveryHandoff | None = field(default=None, repr=False)


def capture_runner_failure(error: BaseException) -> RunnerFailure:
    """Extract only known handoffs, including an original masked by failed settlement.

    Exception context is inspected for retained data, never to authorize a retry or
    infer a product outcome. No exception, cause, traceback or task is kept alive.
    """
    original = error
    visited: set[int] = set()
    recovery: RecoveryHandoff | None = None
    pending = [error]
    while pending:
        error = pending.pop()
        if id(error) in visited:
            continue
        visited.add(id(error))
        if isinstance(
            error,
            (
                ResponseStepSaveError,
                InputCountSaveError,
                CompactionSaveError,
                PreparationCountSaveError,
            ),
        ):
            recovery = error.recovery
            break
        if isinstance(error, (ReceivedModelResponseError, ReceivedModelResponseCancelledError)):
            recovery = error.received
            break
        if error.__context__ is not None:
            pending.append(error.__context__)
        if error.__cause__ is not None:
            pending.append(error.__cause__)
        if isinstance(error, ResultSaveCancelledError):
            pending.append(error.save_error)
    return RunnerFailure(type(original).__name__, isinstance(original, CancelledError), recovery)


async def has_terminal_outcome(
    sessions: async_sessionmaker[AsyncSession], scope: ExecutionScope
) -> bool:
    """Only a successful owner read permits releasing a stopped invocation's originals.

    A cleanup failure can follow a committed completion. Conversely, a failed read
    cannot establish any outcome: keep the handoff and local reentry barrier intact.
    """
    try:
        async with sessions() as session:
            info = await executions.read_execution(session, scope)
        return info.status in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.FAILED,
        )
    except Exception as error:
        _LOG.warning(
            "supervisor.outcome_unconfirmed",
            extra={
                "job_file_id": scope.job_file_id,
                "execution_id": scope.execution_id,
                "failure_kind": type(error).__name__,
            },
        )
        return False
