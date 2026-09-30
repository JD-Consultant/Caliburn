"""App-authorized consultant controls; native pause and product terminal state stay distinct."""

from collections.abc import Awaitable
from typing import Protocol
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.agent_execution.tool_steps import read_completed_response_history, read_response_pause
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import (
    AgentRole,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import (
    ExecutionInfo,
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor


class ConsultantControlWorkflow:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        checkpointer: BaseCheckpointSaver[str],
        supervisor: ConsultantSupervisor,
    ) -> None:
        self.sessions = sessions
        self.checkpointer = checkpointer
        self.supervisor = supervisor

    async def pause(self, scope: ExecutionScope) -> ExecutionInfo:
        """Persist intent, including before a writer exists. Only the runner acknowledges it."""
        _require_consultant(scope)
        async with self.supervisor.hold_dispatch(), self.sessions.begin() as session:
            await executions.request_pause(session, scope)
            result = await executions.read_execution(session, scope)
        self.supervisor.notify(scope)
        return result

    async def cancel(self, scope: ExecutionScope) -> ExecutionInfo:
        """Fence/discard in the existing completion owner before cancelling any local task."""
        _require_consultant(scope)
        async with self.supervisor.hold_dispatch():
            async with self.sessions.begin() as session:
                info = await executions.read_execution(session, scope)
                if info.status in (
                    ExecutionStatus.COMPLETED,
                    ExecutionStatus.CANCELLED,
                    ExecutionStatus.FAILED,
                ):
                    result = info
                    writer = None
                elif info.writer_id is None:
                    # This identity authorizes stop, never starts a model/Graph. The
                    # dispatch gate excludes the supervisor's competing first claim.
                    writer = await executions.claim_writer(session, scope, writer_id=uuid4())
                else:
                    writer = ExecutionWriter(scope, info.writer_id)
            if writer is not None:
                result = await ConsultantCompletionWorkflow(self.sessions).stop(
                    writer, ExecutionStatus.CANCELLED
                )
        if result.status == ExecutionStatus.CANCELLED:
            await self.supervisor.stop_runner(scope)
        return result

    async def resume(self, scope: ExecutionScope) -> ExecutionInfo:
        """Authorize the original native interrupt, then explicitly reenter this same Turn.

        The active/no-pause-intent transition is durable authorization. A crash before
        notify is recovered by startup discovery plus run_consultant_with_controls;
        no checkpoint/interrupt identity or one-shot authorization lives only in memory.
        """
        _require_consultant(scope)
        async with self.supervisor.hold_dispatch():
            async with self.sessions() as session:
                info = await executions.read_execution(session, scope)
            if info.status not in (ExecutionStatus.ACTIVE, ExecutionStatus.PAUSED):
                return info
            if not self.supervisor.running:
                raise ExecutionStateError("Consultant supervision is not available")
            if info.status == ExecutionStatus.ACTIVE:
                if info.pause_requested:
                    raise ExecutionStateError("Wait for the current Step to acknowledge pause")
                if self.supervisor.has_runner(scope):
                    return info  # Duplicate resume while the authorized runner is active.
            # The DB ack precedes run() returning PausedResponseLoop. Do not clear
            # intent/reenter while the old invocation can still acknowledge the pause.
            await self.supervisor.wait_for_runner(scope)
            paused = await read_response_pause(self.checkpointer, thread_id=_thread_id(scope))
            if paused is None or info.writer_id is None:
                raise ExecutionStateError("There is no original native Step pause to resume")
            writer = ExecutionWriter(scope, info.writer_id)
            async with self.sessions.begin() as session:
                await executions.resume_execution(session, writer)
                result = await executions.read_execution(session, scope)
            self.supervisor.allow_reentry(scope)
            return result


class ConsultantRun(Protocol):
    def __call__(
        self, writer: ExecutionWriter, *, resume_interrupt_id: str | None = None
    ) -> Awaitable[object]: ...


async def run_consultant_with_controls(
    writer: ExecutionWriter,
    *,
    sessions: async_sessionmaker[AsyncSession],
    checkpointer: BaseCheckpointSaver[str],
    run: ConsultantRun,
) -> object:
    """Resolve authorized resume from persistent facts, then use the original runner.

    Only a proven final/pause arbitration failure gets one control-only reentry.
    Recovery handoffs and other errors remain owned by the runner; fixed context,
    native continuation and original budgets are never replaced here.
    """
    _require_consultant(writer.scope)
    async with sessions.begin() as session:
        await executions.lock_active_writer(session, writer)
        info = await executions.read_execution(session, writer.scope)
    resume_id = None
    if not info.pause_requested:
        paused = await read_response_pause(checkpointer, thread_id=_thread_id(writer.scope))
        if paused is not None:
            resume_id = paused.interrupt_id
        del paused
    try:
        return await run(writer, resume_interrupt_id=resume_id)
    except ExecutionStateError:
        # A pause can win AFTER Graph final returns but BEFORE the product completion
        # transaction. Only this proven final/control boundary permits one reentry;
        # arbitrary errors, held results and unknown outbound attempts propagate.
        async with sessions() as session:
            current = await executions.read_execution(session, writer.scope)
        if (
            current.writer_id != writer.writer_id
            or current.status != ExecutionStatus.ACTIVE
            or not current.pause_requested
        ):
            raise
        await read_completed_response_history(checkpointer, thread_id=_thread_id(writer.scope))
        # Existing None recovery rechecks the pure Step control successor before
        # delivery; it neither rebuilds context nor requests another model response.
        return await run(writer)


def _thread_id(scope: ExecutionScope) -> str:
    return context_thread_id(scope, AgentRole.JOB_CONSULTANT, HistoryWindowKind.COMPLETED_WORK)


def _require_consultant(scope: ExecutionScope) -> None:
    if scope.kind != ExecutionKind.CONSULTANT_TURN:
        raise ExecutionStateError("Only consultant Turns have user controls")
