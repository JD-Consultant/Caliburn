"""Memory Bundle 使用的應用服務，由可信 Host／協調器注入。"""

from collections.abc import Awaitable, Callable
from typing import Any, Protocol
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from openai import AsyncOpenAI
from openai.types.responses.response_create_params import ResponseCreateParamsBase

from caliburn.modules.agent.agent import Agent
from caliburn.modules.agent.plugins.services import ServiceKey
from caliburn.modules.interview.application.persistence import InterviewQueries
from caliburn.modules.memory.application.persistence import (
    MemoryQueries,
    MemoryUnitOfWork,
)
from caliburn.modules.memory.application.service import MemoryService
from caliburn.modules.memory.domain.snapshot import MemorySnapshot
from caliburn.modules.model_references import ModelReferences


class MemoryCoordinator(Protocol):
    async def run(
        self, *, workspace_id: UUID, turn_id: UUID
    ) -> MemorySnapshot | None: ...


class MemoryCoordinatorFactory(Protocol):
    """建立背景協調器；呼叫方管理 client、checkpointer 與執行任務。"""

    def __call__(
        self,
        *,
        consultant: Agent,
        client: AsyncOpenAI,
        model_settings: ResponseCreateParamsBase,
        checkpointer: BaseCheckpointSaver[Any],
        agent_id: str,
        resume_version: str,
        queries: MemoryQueries,
        interview_queries: InterviewQueries,
        uow_factory: Callable[[], MemoryUnitOfWork],
        references: ModelReferences,
    ) -> MemoryCoordinator: ...


MEMORY_QUERIES = ServiceKey[MemoryQueries]("memory_queries")
MEMORY_COMPLETED_TURNS = ServiceKey[Callable[[UUID], Awaitable[frozenset[UUID]]]](
    "memory_completed_turns"
)
MEMORY_SERVICE = ServiceKey[MemoryService]("memory_service")
MEMORY_COORDINATOR_FACTORY = ServiceKey[MemoryCoordinatorFactory](
    "memory_coordinator_factory"
)
