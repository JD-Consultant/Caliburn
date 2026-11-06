"""Workspace 用例需要的保存與交易契約。"""

from abc import abstractmethod
from typing import Protocol
from uuid import UUID

from caliburn.modules.workspace.domain.workspace import Workspace
from caliburn.shared.application.base_repository import BaseRepository
from caliburn.shared.application.base_unit_of_work import BaseUnitOfWork


class WorkspaceRepository(BaseRepository[Workspace], Protocol):
    @abstractmethod
    def add(self, workspace: Workspace) -> None:
        """保留完整身分新增 Workspace 聚合，不自行提交或覆寫既有 ID。"""
        ...

    @abstractmethod
    def get(self, workspace_id: UUID) -> Workspace | None:
        """取得指定身分的有效聚合快照；不存在時回傳 None。"""
        ...

    @abstractmethod
    def list_page(self, *, limit: int, after: UUID | None) -> list[Workspace]:
        """按 UUID 降冪取至多 limit 筆；after 是不含自身的 ID 邊界。"""
        ...

    @abstractmethod
    def save(self, workspace: Workspace) -> bool:
        """原子更新既有 ID、不插入；目標已不存在回 False，不自行提交。"""
        ...

    @abstractmethod
    def delete(self, workspace_id: UUID) -> bool:
        """刪除 Workspace 及同生命週期內容；不存在回 False，不自行提交。"""
        ...


class WorkspaceUnitOfWork(BaseUnitOfWork, Protocol):
    @property
    @abstractmethod
    def workspaces(self) -> WorkspaceRepository:
        """取得本工作單元所屬交易的 Repository。"""
        ...


class WorkspaceInitializationUnitOfWork(WorkspaceUnitOfWork, Protocol):
    def initialize_job_description(self, workspace_id: UUID) -> None: ...

    def record_interview_opening(self, workspace_id: UUID) -> None: ...
