"""Bind consultant-only Graph controls to the existing execution owner."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.agent_execution.tool_steps import ResponseLoopControls
from caliburn.features.executions import service
from caliburn.features.executions.models import ExecutionKind, ExecutionWriter


@dataclass(frozen=True, slots=True)
class ConsultantExecutionControls:
    sessions: async_sessionmaker[AsyncSession]
    writer: ExecutionWriter

    def __post_init__(self) -> None:
        if self.writer.scope.kind != ExecutionKind.CONSULTANT_TURN:
            raise ValueError("Only consultant Turns have user pause controls")

    async def ensure_active(self) -> None:
        async with self.sessions.begin() as session:
            await service.lock_active_writer(session, self.writer)

    async def read_pause_requested(self) -> bool:
        async with self.sessions.begin() as session:
            await service.lock_active_writer(session, self.writer)
            info = await service.read_execution(session, self.writer.scope)
            return info.pause_requested

    async def mark_paused(self) -> None:
        # Called only after a durable native interrupt, including recovery of a
        # lost acknowledgement. No transaction spans the saver or provider I/O.
        async with self.sessions.begin() as session:
            await service.pause_execution(session, self.writer)

    def loop_controls(self) -> ResponseLoopControls:
        return ResponseLoopControls(self.read_pause_requested, self.mark_paused)
