"""Connect role history eligibility to existing native checkpoint windows, not a copy."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import NativeItems
from caliburn.agent_execution.context_compaction import (
    CompactionRuntime,
    HeldCompaction,
    HeldPreparationCount,
    prepare_context_history,
    read_prepared_history,
)
from caliburn.agent_execution.request_capacity import ReceivedInputCount
from caliburn.agent_execution.tool_steps import read_completed_response_history
from caliburn.features.executions import history, service
from caliburn.features.executions.history_models import (
    AgentRole,
    ContextPosition,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import ExecutionWriter


@dataclass(frozen=True, slots=True)
class RoleContextHistory:
    sessions: async_sessionmaker[AsyncSession]
    writer: ExecutionWriter
    role: AgentRole
    checkpointer: BaseCheckpointSaver[str]

    @property
    def response_thread_id(self) -> str:
        return context_thread_id(self.writer.scope, self.role, HistoryWindowKind.COMPLETED_WORK)

    async def ensure_active(self) -> None:
        async with self.sessions.begin() as session:
            await service.lock_active_writer(session, self.writer)

    async def prepare_history(
        self,
        *,
        template: ResponseRequest,
        threshold_tokens: int,
        compact_requested: bool,
        count_input: Callable[[ResponseRequest, UUID], Awaitable[ReceivedInputCount]],
        runtime: CompactionRuntime,
        recovery: HeldCompaction | HeldPreparationCount | None = None,
    ) -> NativeItems:
        """Prepare only adopted history; caller adds fixed role data and input afterwards.

        Resume with original policy while preparation is incomplete. An already adopted
        pre-work base survives cancellation, so a new Turn does not compact it again.
        One writer per role is required; this is not a scheduler or a new history store.
        """
        if template.create_payload()["input"]:
            raise ValueError("The history template must not include new-work input or maps")
        if self.role == AgentRole.JOB_CONSULTANT and threshold_tokens != 128_000:
            raise ValueError("Consultant history preparation uses the confirmed 128K threshold")
        async with self.sessions.begin() as session:
            binding = await history.bind_context_history(session, self.writer, self.role)
        if binding.prepared is not None:
            items = await self._read_position(binding.prepared)
            await self.ensure_active()
            return items
        if binding.base is not None and binding.base.kind == HistoryWindowKind.PREPARED_HISTORY:
            # No completed work has extended this base. Reuse even if the retained C
            # is still above the threshold, instead of repeatedly compacting it.
            items = await self._read_position(binding.base)
            position = binding.base
        else:
            items = [] if binding.base is None else await self._read_position(binding.base)
            request = ResponseRequest.from_snapshot({**template.create_payload(), "input": items})
            thread_id = context_thread_id(
                self.writer.scope, self.role, HistoryWindowKind.PREPARED_HISTORY
            )
            await prepare_context_history(
                self.checkpointer,
                thread_id=thread_id,
                history_request=request,
                threshold_tokens=threshold_tokens,
                compact_requested=compact_requested,
                count_input=count_input,
                runtime=runtime,
                recovery=recovery,
            )
            saved = await read_prepared_history(self.checkpointer, thread_id=thread_id)
            items = saved.items
            position = ContextPosition(
                thread_id, saved.checkpoint_id, HistoryWindowKind.PREPARED_HISTORY
            )
        # Saver I/O is finished. Only references cross this short business transaction.
        # If acknowledgement is lost, the original binding decides the next entry.
        async with self.sessions.begin() as session:
            await history.adopt_prepared_context(session, self.writer, self.role, position)
        return items

    async def read_completed_position(self) -> ContextPosition:
        await self.ensure_active()
        async with self.sessions.begin() as session:
            binding = await history.read_context_history(session, self.writer.scope, self.role)
            if binding is None or binding.prepared is None:
                raise ValueError("Completed work requires its adopted preparation boundary")
        window = await read_completed_response_history(
            self.checkpointer, thread_id=self.response_thread_id
        )
        return ContextPosition(
            self.response_thread_id, window.checkpoint_id, HistoryWindowKind.COMPLETED_WORK
        )

    async def _read_position(self, position: ContextPosition) -> NativeItems:
        reader = (
            read_prepared_history
            if position.kind == HistoryWindowKind.PREPARED_HISTORY
            else read_completed_response_history
        )
        saved = await reader(
            self.checkpointer,
            thread_id=position.thread_id,
            checkpoint_id=position.checkpoint_id,
        )
        return saved.items
