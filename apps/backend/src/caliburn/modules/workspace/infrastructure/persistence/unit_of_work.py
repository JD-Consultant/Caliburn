"""Workspace 單次 Session 與顯式提交的交易邊界。"""

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session

from caliburn.modules.workspace.infrastructure.persistence.repository import (
    SqlAlchemyWorkspaceRepository,
)


class SqlAlchemyWorkspaceUnitOfWork:
    def __init__(
        self, session_factory: Callable[[], Session], *, lock_timeout_ms: int = 5000
    ) -> None:
        if (
            isinstance(lock_timeout_ms, bool)
            or not isinstance(lock_timeout_ms, int)
            or not 1 <= lock_timeout_ms <= 2_147_483_647
        ):
            raise ValueError("lock_timeout_ms 必須是有限的正整數毫秒")
        self._session_factory = session_factory
        self._lock_timeout_ms = lock_timeout_ms
        self._session: Session | None = None
        self._repository: SqlAlchemyWorkspaceRepository | None = None

    @property
    def workspaces(self) -> SqlAlchemyWorkspaceRepository:
        if self._repository is None:
            raise RuntimeError("Workspace UoW 目前未啟用")
        return self._repository

    def __enter__(self) -> Self:
        if self._session is not None:
            raise RuntimeError("Workspace UoW 已啟用，不可重複進入")
        session = self._session_factory()
        try:
            repository = SqlAlchemyWorkspaceRepository(
                session, lock_timeout_ms=self._lock_timeout_ms
            )
        except BaseException:
            session.close()
            raise
        self._session = session
        self._repository = repository
        return self

    def commit(self) -> None:
        self._active_session().commit()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._active_session()
        self._session = None
        self._repository = None
        try:
            # 已提交交易不受影響；提交後若另有寫入，仍不能隱式保存。
            session.rollback()
        finally:
            session.close()

    def _active_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("Workspace UoW 目前未啟用")
        return self._session
