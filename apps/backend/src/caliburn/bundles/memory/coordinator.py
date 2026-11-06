"""顧問完成後准入，沿目前分析階段交接與發布。"""

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, aclosing, asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import StateSnapshot
from openai import AsyncOpenAI
from openai.types.responses.response_create_params import ResponseCreateParamsBase

from caliburn.bundles.context.services import COMPACTION_CLIENT
from caliburn.bundles.interview.services import MODEL_REFERENCES
from caliburn.bundles.memory.completion import (
    InvalidMemoryCompletion,
    completed_memory_request,
    final_text,
    require_complete,
)
from caliburn.bundles.memory.services import MEMORY_QUERIES, MEMORY_SERVICE
from caliburn.modules.agent.agent import Agent, completed_turn_id, has_pending_work
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.plugins.contracts import AgentBundle
from caliburn.modules.agent.state import AgentLimitError
from caliburn.modules.interview.application.persistence import InterviewQueries
from caliburn.modules.memory.application.errors import MemoryFailureBlockedError
from caliburn.modules.memory.application.inputs import MemoryWriteContext
from caliburn.modules.memory.application.persistence import (
    MemoryQueries,
    MemoryUnitOfWork,
)
from caliburn.modules.memory.application.service import MemoryService
from caliburn.modules.memory.domain.analysis import MemoryFailureReason
from caliburn.modules.memory.domain.errors import InvalidMemorySourceError
from caliburn.modules.memory.domain.items import MemoryKind
from caliburn.modules.memory.domain.snapshot import MemorySnapshot
from caliburn.modules.memory.domain.work_memory import WorkMemory
from caliburn.modules.model_references import ModelReferences

_TERMINAL_ANALYSIS_ERRORS = (
    InvalidMemoryCompletion,
    InvalidMemorySourceError,
    AgentLimitError,
)


class OpenRoleAgent(Protocol):
    def __call__(
        self, *, role: MemoryKind, analysis_id: UUID, memory_service: MemoryService
    ) -> AbstractAsyncContextManager[Agent]: ...


@asynccontextmanager
async def open_memory_role_agent(
    *,
    agent_id: str,
    resume_version: str,
    client: AsyncOpenAI,
    model_settings: ResponseCreateParamsBase,
    checkpointer: BaseCheckpointSaver[Any],
    queries: MemoryQueries,
    references: ModelReferences,
    role: MemoryKind,
    analysis_id: UUID,
    memory_service: MemoryService,
    bundles: Sequence[BundleConfig | AgentBundle] | None = None,
    max_tool_result_characters: int = 1_000_000,
    max_context_characters: int = 1_000_000,
) -> AsyncIterator[Agent]:
    """每個角色沿明示組裝使用獨立原生 thread；省略時採內建角色。"""
    async with open_agent(
        agent_id=f"{agent_id}:memory:{analysis_id}:{role}",
        resume_version=resume_version,
        client=client,
        model_settings=model_settings,
        bundles=tuple(bundles)
        if bundles is not None
        else (
            BundleConfig(
                "caliburn.bundles.memory",
                {
                    "role": role,
                    "max_tool_result_characters": max_tool_result_characters,
                    "max_context_characters": max_context_characters,
                },
            ),
        ),
        checkpointer=checkpointer,
        external_services=(
            COMPACTION_CLIENT.bind(client),
            MODEL_REFERENCES.bind(references),
            MEMORY_QUERIES.bind(queries),
            MEMORY_SERVICE.bind(memory_service),
        ),
    ) as agent:
        yield agent


async def completed_consultant_turns(
    consultant: Agent, *, workspace_id: UUID
) -> frozenset[UUID]:
    """每輪只採最新的原生保存點，不能用已保存訪談正文推定輪次完成。"""
    seen: set[str] = set()
    completed: set[UUID] = set()
    async for snapshot in consultant.aget_state_history(workspace_id=workspace_id):
        turn = snapshot.metadata.get("turn_id") if snapshot.metadata else None
        if not isinstance(turn, str) or turn in seen:
            continue
        seen.add(turn)
        if turn_id := completed_turn_id(snapshot):
            completed.add(turn_id)
    return frozenset(completed)


@dataclass(frozen=True, slots=True)
class _CompletedTurns:
    workspace_id: UUID
    turns: frozenset[UUID]

    def completed_turn_ids(self, *, workspace_id: UUID) -> frozenset[UUID]:
        if workspace_id != self.workspace_id:
            raise ValueError("Memory completion evidence belongs to another Workspace")
        return self.turns


async def _run_role(
    agent: Agent, *, workspace_id: UUID, analysis_id: UUID
) -> StateSnapshot:
    saved = await agent.aget_state(workspace_id=workspace_id)
    invocation = None
    if saved.created_at is None:
        invocation = agent.astream(
            workspace_id=workspace_id, turn_id=analysis_id, input="工作記憶分析"
        )
    elif has_pending_work(saved):
        if (
            not saved.metadata
            or saved.metadata.get("resume_version") != agent.resume_version
        ):
            raise ValueError("分析輪的恢復版本不相容")
        invocation = agent.aresume(workspace_id=workspace_id, turn_id=analysis_id)
    if invocation is not None:
        async with aclosing(invocation) as stream:
            async for _ in stream:
                pass
        saved = await agent.aget_state(workspace_id=workspace_id)
    return saved


class MemoryAnalysisCoordinator:
    """Host 持有執行任務；同一程序的 Workspace 整理由此循序協調。"""

    def __init__(
        self,
        *,
        consultant: Agent,
        interview_queries: InterviewQueries,
        queries: MemoryQueries,
        uow_factory: Callable[[], MemoryUnitOfWork],
        open_role_agent: OpenRoleAgent,
    ) -> None:
        self._consultant = consultant
        self._interview = interview_queries
        self._queries = queries
        self._uow_factory = uow_factory
        self._open_role_agent = open_role_agent
        self._locks: WeakValueDictionary[UUID, asyncio.Lock] = WeakValueDictionary()

    async def run(self, *, workspace_id: UUID, turn_id: UUID) -> MemorySnapshot | None:
        """只處理有意圖的已完成 A 輪。已涵蓋的訪談不再整理。"""
        lock = self._locks.setdefault(workspace_id, asyncio.Lock())
        async with lock:
            latest = [
                snapshot
                async for snapshot in self._consultant.aget_state_history(
                    workspace_id=workspace_id, turn_id=turn_id, limit=1
                )
            ]
            requested_turn = completed_memory_request(latest[0]) if latest else None
            if requested_turn is None:
                return None
            messages = await asyncio.to_thread(
                self._interview.list_messages,
                workspace_id=workspace_id,
                turn_id=requested_turn,
            )
            if not messages:
                # 已准入的工作仍沿保存窗口接續／結算，不另選來源重開。
                current = await self._current(workspace_id)
                if current.analysis is None:
                    return None
                return await self._continue(
                    self._service(workspace_id, frozenset()),
                    workspace_id,
                    current.analysis.analysis_id,
                    current.analysis.phase,
                )
            return await self._process(workspace_id, messages[-1].message_id)

    def _service(self, workspace_id: UUID, completed: frozenset[UUID]) -> MemoryService:
        return MemoryService(
            self._uow_factory,
            completed_turns=_CompletedTurns(workspace_id, completed),
        )

    async def _current(self, workspace_id: UUID) -> WorkMemory:
        return await asyncio.to_thread(
            self._queries.get_current, workspace_id=workspace_id
        )

    async def _process(
        self, workspace_id: UUID, through: UUID
    ) -> MemorySnapshot | None:
        root = await self._current(workspace_id)
        if active := root.analysis:
            service = self._service(workspace_id, frozenset())
            if active.source_window.through_message_id == through:
                return await self._continue(
                    service, workspace_id, active.analysis_id, active.phase
                )
            try:
                await self._continue(
                    service, workspace_id, active.analysis_id, active.phase
                )
            except _TERMINAL_ANALYSIS_ERRORS:
                # 已知無法完成的舊分析已結算；新要求仍須核對重試資格。
                pass
            root = await self._current(workspace_id)

        completed = await completed_consultant_turns(
            self._consultant, workspace_id=workspace_id
        )
        service = self._service(workspace_id, completed)
        analysis_id = uuid4()
        try:
            started = await asyncio.to_thread(
                service.start,
                MemoryWriteContext(workspace_id, root.version, analysis_id),
                through_message_id=through,
            )
        except MemoryFailureBlockedError:
            return None
        if not started.changed:
            return None
        return await self._continue(service, workspace_id, analysis_id, "situation")

    async def _continue(
        self,
        service: MemoryService,
        workspace_id: UUID,
        analysis_id: UUID,
        phase: MemoryKind,
    ) -> MemorySnapshot | None:
        try:
            if phase == "situation":
                handoff = await self._complete_role(
                    service, workspace_id, analysis_id, "situation"
                )
                await asyncio.to_thread(service.handoff, handoff)
            publish = await self._complete_role(
                service, workspace_id, analysis_id, "understanding"
            )
            return (await asyncio.to_thread(service.publish, publish)).snapshot
        except _TERMINAL_ANALYSIS_ERRORS as error:
            reason: MemoryFailureReason
            if isinstance(error, AgentLimitError):
                reason = "analysis_limit"
            elif isinstance(error, InvalidMemorySourceError):
                reason = "invalid_source_window"
            else:
                reason = "invalid_completion"
            root = await self._current(workspace_id)
            # 分析期間可能已有其他 A 輪完成；以失敗時的正式歷史為準。
            completed = await completed_consultant_turns(
                self._consultant, workspace_id=workspace_id
            )
            latest_service = self._service(workspace_id, completed)
            await asyncio.to_thread(
                latest_service.discard,
                MemoryWriteContext(workspace_id, root.version, analysis_id),
                reason=reason,
            )
            raise

    async def _complete_role(
        self,
        service: MemoryService,
        workspace_id: UUID,
        analysis_id: UUID,
        role: MemoryKind,
    ) -> MemoryWriteContext:
        async with self._open_role_agent(
            role=role, analysis_id=analysis_id, memory_service=service
        ) as agent:
            saved = await _run_role(
                agent, workspace_id=workspace_id, analysis_id=analysis_id
            )
        if completed_turn_id(saved) != analysis_id:
            raise InvalidMemoryCompletion("分析輪沒有完成")
        require_complete(final_text(saved.values.get("model_response")) or "")
        root = await self._current(workspace_id)
        return MemoryWriteContext(workspace_id, root.version, analysis_id)
