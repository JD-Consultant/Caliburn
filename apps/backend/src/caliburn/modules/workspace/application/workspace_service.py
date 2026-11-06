"""Workspace 的 Application Service，協調用例與交易。"""

from collections.abc import Callable
from uuid import UUID

from caliburn.modules.workspace.application.errors import (
    InvalidWorkspacePaginationError,
    WorkspaceNotFoundError,
)
from caliburn.modules.workspace.application.persistence import WorkspaceUnitOfWork
from caliburn.modules.workspace.application.results import (
    CreateWorkspaceResult,
    WorkspacePage,
    WorkspaceResult,
)
from caliburn.modules.workspace.domain.interviewee_name import (
    IntervieweeName,
)
from caliburn.modules.workspace.domain.workspace import Workspace


class WorkspaceService:
    """協調 Workspace CRUD；各次呼叫獨立取得 UoW，不保存交易狀態。"""

    def __init__(self, uow_factory: Callable[[], WorkspaceUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def create(self, *, interviewee_name: str) -> CreateWorkspaceResult:
        """建立聚合，確認提交並釋放資源後回傳結果。"""
        workspace = Workspace.create(interviewee_name=interviewee_name)
        result = CreateWorkspaceResult.from_workspace(workspace)
        with self._uow_factory() as uow:
            uow.workspaces.add(workspace)
            uow.commit()

        return result

    def get(self, *, workspace_id: UUID) -> WorkspaceResult:
        """讀取單筆；查無資料拋出 WorkspaceNotFoundError，不提交寫入。"""
        with self._uow_factory() as uow:
            workspace = uow.workspaces.get(workspace_id)
            if workspace is None:
                raise WorkspaceNotFoundError(workspace_id)
            result = WorkspaceResult.from_workspace(workspace)

        return result

    def list(self, *, limit: int = 20, after: UUID | None = None) -> WorkspacePage:
        """依 UUID 倒序分頁；無效參數拋出 InvalidWorkspacePaginationError。"""
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 100
        ):
            raise InvalidWorkspacePaginationError("limit 必須是 1 到 100 之間的整數")
        if after is not None and not isinstance(after, UUID):
            raise InvalidWorkspacePaginationError("after 必須是 UUID")

        with self._uow_factory() as uow:
            workspaces = uow.workspaces.list_page(limit=limit + 1, after=after)
            items = tuple(
                WorkspaceResult.from_workspace(workspace)
                for workspace in workspaces[:limit]
            )
            result = WorkspacePage(
                items=items,
                next_cursor=items[-1].workspace_id if len(workspaces) > limit else None,
            )

        return result

    def rename(self, *, workspace_id: UUID, interviewee_name: str) -> WorkspaceResult:
        """經 Domain 改名並提交；目標不存在時不建立替代資料。"""
        name = IntervieweeName(value=interviewee_name)

        with self._uow_factory() as uow:
            workspace = uow.workspaces.get(workspace_id)
            if workspace is None:
                raise WorkspaceNotFoundError(workspace_id)
            renamed = workspace.rename(interviewee_name=name)
            result = WorkspaceResult.from_workspace(renamed)
            if not uow.workspaces.save(renamed):
                raise WorkspaceNotFoundError(workspace_id)
            uow.commit()

        return result

    def delete(self, *, workspace_id: UUID) -> None:
        """永久刪除整份 Workspace 與所屬內容；已不存在也視為成功。"""
        with self._uow_factory() as uow:
            uow.workspaces.delete(workspace_id)
            uow.commit()
