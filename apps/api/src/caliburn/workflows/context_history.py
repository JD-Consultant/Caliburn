"""Connect role history eligibility to existing native checkpoint windows, not a copy."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from langchain_core.runnables import RunnableConfig
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

    async def request_compaction(self) -> None:
        async with self.sessions.begin() as session:
            await history.request_context_compaction(session, self.writer, self.role)

    async def resolve_template(
        self,
        template: ResponseRequest,
        recovery: HeldCompaction | HeldPreparationCount | None = None,
    ) -> ResponseRequest:
        """Keep this role's original preparation settings across process/code reentry.

        The original request remains in the native saver. Clearing its historical input
        yields a role template; preparation and context capture still own their inputs.
        A held result requires the original saved request boundary: only the result may
        still be unsaved. This lookup neither adopts a window nor authorizes replay.
        """
        if template.create_payload()["input"]:
            raise ValueError("The role template must not include history or new-work input")
        thread_id = context_thread_id(
            self.writer.scope, self.role, HistoryWindowKind.PREPARED_HISTORY
        )
        if recovery is not None and (
            not isinstance(recovery, (HeldCompaction, HeldPreparationCount))
            or recovery.thread_id != thread_id
        ):
            raise ValueError("The held preparation belongs to another role or execution")
        await self.ensure_active()
        config: RunnableConfig = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        saved = await self.checkpointer.aget_tuple(config)
        snapshot: object
        if saved is None:
            if recovery is not None:
                raise ValueError("The held result has no saved preparation boundary")
            return template
        else:
            values = saved.checkpoint["channel_values"]
            # Before the first expanded state, the native input checkpoint owns the
            # same request. Pending result writes never replace that original input.
            if "request_snapshot" not in values:
                values = values.get("__start__", {})
            if not isinstance(values, dict) or values.get("preparation_policy") is None:
                raise ValueError("The saved boundary is not a history preparation")
            snapshot = values.get("request_snapshot")
            if recovery is not None and (
                values.get("request_id") != recovery.request_id
                or snapshot != recovery.request_snapshot
            ):
                raise ValueError("The held preparation does not match its saved request")
        if not isinstance(snapshot, dict):
            raise ValueError("The saved preparation request is unavailable")
        original = ResponseRequest.from_snapshot(snapshot).create_payload()
        return ResponseRequest.from_snapshot({**original, "input": []})

    async def prepare_history(
        self,
        *,
        template: ResponseRequest,
        threshold_tokens: int,
        compact_requested: bool = False,
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
            if binding.prepared is None and binding.base is not None:
                compact_requested = (
                    compact_requested
                    or await history.read_completed_compaction_request(
                        session, self.writer.scope.job_file_id, self.role, binding.base
                    )
                )
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
