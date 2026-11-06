"""以單一 Session 保存獨立的 Workspace 領域快照。"""

from uuid import UUID

from psycopg.errors import DeadlockDetected, LockNotAvailable
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from caliburn.modules.workspace.application.errors import WorkspaceConcurrencyError
from caliburn.modules.workspace.domain.interviewee_name import (
    IntervieweeName,
)
from caliburn.modules.workspace.domain.workspace import Workspace
from caliburn.modules.workspace.infrastructure.persistence.orm_models import (
    WorkspaceRow,
)


class SqlAlchemyWorkspaceRepository:
    def __init__(self, session: Session, *, lock_timeout_ms: int = 5000) -> None:
        self._session = session
        self._lock_timeout_ms = lock_timeout_ms

    def add(self, workspace: Workspace) -> None:
        self._session.add(
            WorkspaceRow(
                id=workspace.id,
                interviewee_name=workspace.interviewee_name.value,
            )
        )

    def get(self, workspace_id: UUID) -> Workspace | None:
        row = self._session.get(WorkspaceRow, workspace_id)
        return self._to_domain(row) if row is not None else None

    def list_page(self, *, limit: int, after: UUID | None) -> list[Workspace]:
        statement = select(WorkspaceRow).order_by(WorkspaceRow.id.desc()).limit(limit)
        if after is not None:
            statement = statement.where(WorkspaceRow.id < after)
        return [self._to_domain(row) for row in self._session.scalars(statement)]

    def save(self, workspace: Workspace) -> bool:
        statement = (
            update(WorkspaceRow)
            .where(WorkspaceRow.id == workspace.id)
            .values(interviewee_name=workspace.interviewee_name.value)
            .returning(WorkspaceRow.id)
        )
        return self._session.execute(statement).scalar_one_or_none() is not None

    def delete(self, workspace_id: UUID) -> bool:
        self._session.execute(
            text("SELECT set_config('lock_timeout', :timeout, true)"),
            {"timeout": f"{self._lock_timeout_ms}ms"},
        )
        statement = (
            delete(WorkspaceRow)
            .where(WorkspaceRow.id == workspace_id)
            .returning(WorkspaceRow.id)
        )
        try:
            return self._session.execute(statement).scalar_one_or_none() is not None
        except OperationalError as error:
            # 僅轉譯 DELETE 的拒絕，不從 commit 或回覆故障推斷未刪除。
            if isinstance(error.orig, LockNotAvailable):
                raise WorkspaceConcurrencyError(reason="lock_timeout") from error
            if isinstance(error.orig, DeadlockDetected):
                raise WorkspaceConcurrencyError(reason="deadlock") from error
            raise

    @staticmethod
    def _to_domain(row: WorkspaceRow) -> Workspace:
        return Workspace(
            id=row.id,
            interviewee_name=IntervieweeName(value=row.interviewee_name),
        )
