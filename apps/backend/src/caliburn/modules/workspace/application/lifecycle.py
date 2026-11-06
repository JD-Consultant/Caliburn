"""Workspace 用例協調正式內容的建立與清理。"""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from caliburn.modules.workspace.application.persistence import (
    WorkspaceInitializationUnitOfWork,
)
from caliburn.modules.workspace.application.results import CreateWorkspaceResult
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.domain.workspace import Workspace


def create_workspace(
    interviewee_name: str,
    *,
    uow_factory: Callable[[], WorkspaceInitializationUnitOfWork],
) -> CreateWorkspaceResult:
    """工作區、空 JD 與訪談開場在同一交易提交。"""
    workspace = Workspace.create(interviewee_name=interviewee_name)
    with uow_factory() as uow:
        uow.workspaces.add(workspace)
        uow.initialize_job_description(workspace.id)
        uow.record_interview_opening(workspace.id)
        uow.commit()
    return CreateWorkspaceResult.from_workspace(workspace)


async def delete_workspace(
    workspace_id: UUID,
    *,
    workspaces: WorkspaceService,
    suspend_workspace: Callable[[UUID], AbstractAsyncContextManager[None]],
    delete_checkpoints: Callable[[UUID], Awaitable[None]],
) -> None:
    """業務資料提交後才清除 Checkpoint，清理失敗可用同一 ID 重試。"""
    async with suspend_workspace(workspace_id):
        await asyncio.to_thread(workspaces.delete, workspace_id=workspace_id)
        await delete_checkpoints(workspace_id)
