"""用例擁有的聚合、已完成訪談資格與獨立查讀介面。"""

from typing import Protocol
from uuid import UUID

from caliburn.modules.memory.application.results import MemoryInterviewMessage
from caliburn.modules.memory.domain.analysis import MemorySourceWindow
from caliburn.modules.memory.domain.snapshot import MemorySnapshot
from caliburn.modules.memory.domain.work_memory import WorkMemory
from caliburn.shared.application.base_unit_of_work import BaseUnitOfWork


class CompletedInterviewTurns(Protocol):
    def completed_turn_ids(self, *, workspace_id: UUID) -> frozenset[UUID]:
        """從執行端保存的完成證據取得 A 輪次。"""
        ...


class InterviewSourceReader(Protocol):
    def formal_message_ids(
        self, *, workspace_id: UUID, completed_turn_ids: frozenset[UUID]
    ) -> tuple[UUID, ...]:
        """鎖定已完成有效輪次，取得含問題、回答、略過的全部正式訊息 ID。"""
        ...

    def bind_window(
        self,
        *,
        workspace_id: UUID,
        through_message_id: UUID,
        covered_through_message_id: UUID | None,
        completed_turn_ids: frozenset[UUID],
    ) -> MemorySourceWindow | None:
        """鎖定所選有效輪次並組成窗口；已涵蓋時回 None。"""
        ...

    def require_sources(
        self, *, window: MemorySourceWindow, message_ids: frozenset[UUID]
    ) -> None:
        """核對固定窗口身分及有效性，並持有訪談輪次鎖直到交易結束。"""
        ...


class MemoryRepository(Protocol):
    def get_for_update(self, *, workspace_id: UUID) -> WorkMemory | None: ...

    def get_snapshot(self, *, workspace_id: UUID, version: int) -> MemorySnapshot: ...

    def save(self, memory: WorkMemory, *, snapshot: MemorySnapshot | None) -> None: ...


class MemoryUnitOfWork(BaseUnitOfWork, Protocol):
    @property
    def memories(self) -> MemoryRepository: ...

    @property
    def sources(self) -> InterviewSourceReader: ...


class MemoryQueries(Protocol):
    def get_current(self, *, workspace_id: UUID) -> WorkMemory: ...

    def get_published(
        self, *, workspace_id: UUID, published_version: int | None
    ) -> MemorySnapshot | None: ...

    def list_analysis_sources(
        self, *, workspace_id: UUID, analysis_id: UUID
    ) -> tuple[MemoryInterviewMessage, ...]: ...
