"""為 Workspace 用例接上資料庫交易、背景工作與 Checkpoint。"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver

from caliburn.bundles.consultant import OPENING_TEXT
from caliburn.host.memory import MemoryHost
from caliburn.modules.agent.application.agent_service import AgentService
from caliburn.modules.interview.infrastructure.persistence.opening import stage_opening
from caliburn.modules.job_description.application.job_descriptions import (
    initialize_job_description,
)
from caliburn.modules.job_description.infrastructure.persistence import (
    job_description_repository,
)
from caliburn.modules.workspace.application.lifecycle import delete_workspace
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)

logger = logging.getLogger(__name__)


class SqlAlchemyWorkspaceInitialization(SqlAlchemyWorkspaceUnitOfWork):
    def initialize_job_description(self, workspace_id: UUID) -> None:
        session = self._active_session()
        session.flush()
        initialize_job_description(
            workspace_id=workspace_id,
            repository=job_description_repository.SqlAlchemyJobDescriptionRepository(
                session
            ),
        )

    def record_interview_opening(self, workspace_id: UUID) -> None:
        stage_opening(
            session=self._active_session(),
            workspace_id=workspace_id,
            text=OPENING_TEXT,
        )


class WorkspaceDeletion:
    """單 worker 的刪除工作所有者；HTTP 斷線不會提前釋放停止範圍。"""

    def __init__(
        self,
        *,
        workspaces: WorkspaceService,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
        agent: AgentService | None = None,
        memory: MemoryHost | None = None,
    ) -> None:
        self._workspaces = workspaces
        self._checkpointer = checkpointer
        self._agent = agent
        self._memory = memory
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    async def delete(self, workspace_id: UUID) -> None:
        task = self._tasks.get(workspace_id)
        if task is None:
            task = asyncio.create_task(
                delete_workspace(
                    workspace_id,
                    workspaces=self._workspaces,
                    suspend_workspace=self._suspend_workspace,
                    delete_checkpoints=self._delete_checkpoints,
                )
            )
            self._tasks[workspace_id] = task
            task.add_done_callback(lambda done: self._finished(workspace_id, done))
        await asyncio.shield(task)

    def _finished(self, workspace_id: UUID, task: asyncio.Task[None]) -> None:
        self._tasks.pop(workspace_id, None)
        if not task.cancelled() and (error := task.exception()) is not None:
            logger.error(
                "Workspace 刪除未確認完成",
                extra={
                    "event": "workspace.deletion.failed",
                    "workspace_id": str(workspace_id),
                    "error_type": type(error).__name__,
                },
            )

    @asynccontextmanager
    async def _suspend_workspace(self, workspace_id: UUID) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            if self._agent is not None:
                await stack.enter_async_context(
                    self._agent.suspend_workspace(workspace_id)
                )
            if self._memory is not None:
                await stack.enter_async_context(
                    self._memory.suspend_workspace(workspace_id)
                )
            yield

    async def _delete_checkpoints(self, workspace_id: UUID) -> None:
        if self._checkpointer is not None:
            threads = {
                entry.config["configurable"]["thread_id"]
                async for entry in self._checkpointer.alist(
                    None, filter={"workspace_id": str(workspace_id)}
                )
            }
            for thread_id in threads:
                await self._checkpointer.adelete_thread(thread_id)

    async def aclose(self) -> None:
        await asyncio.gather(*tuple(self._tasks.values()), return_exceptions=True)
