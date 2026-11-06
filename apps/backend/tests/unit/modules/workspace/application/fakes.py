"""Workspace 用例的交易替身；真資料庫保證另由整合測試驗證。"""

from types import TracebackType
from typing import Self
from uuid import UUID

from caliburn.modules.workspace.domain.workspace import Workspace


class FakeWorkspaceRepository:
    def __init__(
        self,
        working: dict[UUID, Workspace],
        add_error: Exception | None,
    ) -> None:
        self._working = working
        self.add_error = add_error
        self.read_error: Exception | None = None
        self.write_error: Exception | None = None
        self.add_attempts = 0
        self.save_attempts = 0
        self.delete_attempts = 0
        self.page_requests: list[tuple[int, UUID | None]] = []

    def add(self, workspace: Workspace) -> None:
        self.add_attempts += 1
        if self.add_error is not None:
            raise self.add_error
        if self.get(workspace.id) is not None:
            raise ValueError("duplicate workspace identity")
        self._working[workspace.id] = workspace

    def get(self, workspace_id: UUID) -> Workspace | None:
        if self.read_error is not None:
            raise self.read_error
        return self._working.get(workspace_id)

    def list_page(self, *, limit: int, after: UUID | None) -> list[Workspace]:
        self.page_requests.append((limit, after))
        if self.read_error is not None:
            raise self.read_error
        return [
            self._working[identity]
            for identity in sorted(self._working, reverse=True)
            if after is None or identity < after
        ][:limit]

    def save(self, workspace: Workspace) -> bool:
        self.save_attempts += 1
        if self.write_error is not None:
            raise self.write_error
        if self.get(workspace.id) is None:
            return False
        self._working[workspace.id] = workspace
        return True

    def delete(self, workspace_id: UUID) -> bool:
        self.delete_attempts += 1
        if self.write_error is not None:
            raise self.write_error
        if self.get(workspace_id) is None:
            return False
        del self._working[workspace_id]
        return True


class FakeUnitOfWork:
    """以工作副本模擬提交邊界與故障，不模擬資料庫並行。"""

    def __init__(
        self,
        saved: dict[UUID, Workspace],
        *,
        add_error: Exception | None = None,
        commit_error: Exception | None = None,
        enter_error: Exception | None = None,
        exit_error: Exception | None = None,
        commit_before_error: bool = False,
    ) -> None:
        self.saved = saved
        self._working = saved.copy()
        self.workspaces = FakeWorkspaceRepository(self._working, add_error)
        self.commit_error = commit_error
        self.enter_error = enter_error
        self.exit_error = exit_error
        self.commit_before_error = commit_before_error
        self.commit_attempts = 0
        self.committed = False
        self.closed = False

    def __enter__(self) -> Self:
        if self.enter_error is not None:
            self.closed = True
            raise self.enter_error
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.closed = True
        if self.exit_error is not None:
            raise self.exit_error

    def commit(self) -> None:
        self.commit_attempts += 1
        if self.commit_error is not None and not self.commit_before_error:
            raise self.commit_error
        self.saved.clear()
        self.saved.update(self._working)
        self.committed = True
        if self.commit_error is not None:
            raise self.commit_error


class FakeUnitOfWorkFactory:
    def __init__(self, saved: dict[UUID, Workspace] | None = None) -> None:
        self.saved = {} if saved is None else saved
        self.units: list[FakeUnitOfWork] = []

    def __call__(self) -> FakeUnitOfWork:
        unit = FakeUnitOfWork(self.saved)
        self.units.append(unit)
        return unit
