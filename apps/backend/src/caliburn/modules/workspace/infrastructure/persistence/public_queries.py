"""公開 Workspace 身分查詢，供同庫交易鎖定與唯讀投影組合。"""

from uuid import UUID

from sqlalchemy import Select, select

from caliburn.modules.workspace.infrastructure.persistence.orm_models import (
    WorkspaceRow,
)


def select_workspace_id(*, workspace_id: UUID) -> Select[UUID]:
    """只選指定 Workspace 的身分；執行與交易由呼叫端管理。"""
    return select(WorkspaceRow.id).where(WorkspaceRow.id == workspace_id)
