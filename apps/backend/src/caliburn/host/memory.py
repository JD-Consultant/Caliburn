"""Host 擁有整理工作；通知可合併，完成證據可由原生保存點重新發現。"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import monotonic
from uuid import UUID

from caliburn.bundles.memory.completion import completed_memory_request
from caliburn.bundles.memory.services import MemoryCoordinator
from caliburn.modules.agent.agent import Agent
from caliburn.modules.interview.application.persistence import InterviewQueries
from caliburn.modules.workspace.application.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)


def _record(level: int, event: str, **fields: object) -> None:
    try:
        logger.log(level, event, extra={"event": event, **fields})
    except Exception:
        # 日誌 handler 的故障不得改變業務完成結果或阻止後續工作。
        pass


class MemoryHost:
    def __init__(
        self,
        *,
        consultant: Agent,
        coordinator: MemoryCoordinator,
        interview_queries: InterviewQueries,
        max_active: int,
    ) -> None:
        self._consultant = consultant
        self._coordinator = coordinator
        self._interview = interview_queries
        self._capacity = asyncio.Semaphore(max_active)
        self._pending: set[UUID] = set()
        self._workers: dict[UUID, asyncio.Task[None]] = {}
        self._suspended_workspaces: set[UUID] = set()
        self._closed = False

    def notify(self, workspace_id: UUID, turn_id: UUID) -> None:
        """通知不是資格；每次都重查最後一個有意圖且完成的原生輪。"""
        if self._closed or workspace_id in self._suspended_workspaces:
            return
        self._pending.add(workspace_id)
        if workspace_id not in self._workers:
            self._workers[workspace_id] = asyncio.create_task(self._drain(workspace_id))

    @asynccontextmanager
    async def suspend_workspace(self, workspace_id: UUID) -> AsyncIterator[None]:
        """停止接受整理通知，等既有分析與發布收束後才交回刪除者。"""
        self._suspended_workspaces.add(workspace_id)
        self._pending.discard(workspace_id)
        try:
            if worker := self._workers.get(workspace_id):
                await worker
            yield
        except BaseException:
            # 刪除未確認成功時，恢復從完成證據發現工作的既有能力。
            self._suspended_workspaces.discard(workspace_id)
            self.notify(workspace_id, workspace_id)
            raise
        finally:
            self._suspended_workspaces.discard(workspace_id)

    async def recover(self, workspaces: WorkspaceService) -> None:
        """重啟補回完成保存與通知之間的空窗，不保存第二份待辦。"""
        after = None
        count = 0
        _record(logging.INFO, "memory.recovery.started")
        while True:
            page = await asyncio.to_thread(workspaces.list, limit=100, after=after)
            for workspace in page.items:
                self.notify(workspace.workspace_id, workspace.workspace_id)
                count += 1
            after = page.next_cursor
            if after is None:
                _record(
                    logging.INFO, "memory.recovery.scheduled", workspace_count=count
                )
                return

    async def _latest_request(self, workspace_id: UUID) -> UUID | None:
        seen: set[str] = set()
        async for snapshot in self._consultant.aget_state_history(
            workspace_id=workspace_id
        ):
            turn = snapshot.metadata.get("turn_id") if snapshot.metadata else None
            if not isinstance(turn, str) or turn in seen:
                continue
            seen.add(turn)
            requested_turn = completed_memory_request(snapshot)
            if requested_turn is None:
                continue
            messages = await asyncio.to_thread(
                self._interview.list_messages,
                workspace_id=workspace_id,
                turn_id=requested_turn,
            )
            if messages:
                return requested_turn
        return None

    async def _drain(self, workspace_id: UUID) -> None:
        try:
            while workspace_id in self._pending:
                self._pending.discard(workspace_id)
                turn_id = None
                started = monotonic()
                try:
                    async with self._capacity:
                        if turn_id := await self._latest_request(workspace_id):
                            _record(
                                logging.INFO,
                                "memory.consolidation.started",
                                workspace_id=str(workspace_id),
                                turn_id=str(turn_id),
                            )
                            result = await self._coordinator.run(
                                workspace_id=workspace_id, turn_id=turn_id
                            )
                            _record(
                                logging.INFO,
                                "memory.consolidation.finished",
                                workspace_id=str(workspace_id),
                                turn_id=str(turn_id),
                                outcome="publication" if result else "no_work",
                                published_version=result.version if result else None,
                                elapsed_ms=round((monotonic() - started) * 1000),
                            )
                except Exception as error:
                    _record(
                        logging.ERROR,
                        "memory.consolidation.failed",
                        workspace_id=str(workspace_id),
                        turn_id=str(turn_id) if turn_id else None,
                        error_type=type(error).__name__,
                        elapsed_ms=round((monotonic() - started) * 1000),
                    )
        finally:
            self._workers.pop(workspace_id, None)

    async def aclose(self) -> None:
        self._closed = True
        if tasks := tuple(self._workers.values()):
            await asyncio.gather(*tasks)
