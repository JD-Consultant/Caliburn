"""短交易與明確的提交證據。"""

from collections.abc import Callable
from types import TracebackType
from typing import Self

from psycopg import Error as PostgresError
from sqlalchemy import Connection, event, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from caliburn.modules.memory.application.errors import (
    CommitStatus,
    MemoryConcurrencyError,
    MemoryPersistenceError,
)
from caliburn.modules.memory.infrastructure.persistence.interview_sources import (
    SqlAlchemyInterviewSourceReader,
)
from caliburn.modules.memory.infrastructure.persistence.repository import (
    SqlAlchemyMemoryRepository,
)


class SqlAlchemyMemoryUnitOfWork:
    def __init__(
        self, session_factory: Callable[[], Session], *, lock_timeout_ms: int = 5000
    ) -> None:
        if (
            type(lock_timeout_ms) is not int
            or not 1 <= lock_timeout_ms <= 2_147_483_647
        ):
            raise ValueError("lock_timeout_ms 必須為有效正整數毫秒")
        self._session_factory = session_factory
        self._lock_timeout_ms = lock_timeout_ms
        self._session: Session | None = None
        self._repository: SqlAlchemyMemoryRepository | None = None
        self._sources: SqlAlchemyInterviewSourceReader | None = None
        self._commit_status: CommitStatus = "not_committed"

    @property
    def memories(self) -> SqlAlchemyMemoryRepository:
        if self._repository is None:
            raise RuntimeError("Memory UoW 尚未啟用")
        return self._repository

    @property
    def sources(self) -> SqlAlchemyInterviewSourceReader:
        if self._sources is None:
            raise RuntimeError("Memory UoW 尚未啟用")
        return self._sources

    def __enter__(self) -> Self:
        if self._session is not None:
            raise RuntimeError("Memory UoW 已啟用")
        self._commit_status = "not_committed"
        try:
            session = self._session_factory()
        except Exception as error:
            raise MemoryPersistenceError(commit_status="not_committed") from error
        try:
            session.autobegin = False
            session.begin()
            connection = session.connection(
                execution_options={"isolation_level": "READ COMMITTED"}
            )
            event.listen(connection, "commit", self._commit_sent)
            event.listen(session, "after_commit", self._commit_confirmed, insert=True)
            session.execute(
                text("SELECT set_config('lock_timeout', :timeout, true)"),
                {"timeout": f"{self._lock_timeout_ms}ms"},
            )
        except BaseException as error:
            self._release(session, error)
            if isinstance(error, Exception):
                raise self._translate(error) from error
            raise
        self._session = session
        self._repository = SqlAlchemyMemoryRepository(session)
        self._sources = SqlAlchemyInterviewSourceReader(session)
        return self

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Memory UoW 尚未啟用")
        try:
            self._session.flush()
            self._session.commit()
        except Exception as error:
            raise self._translate(error) from error

    def _commit_sent(self, connection: Connection) -> None:
        self._commit_status = "unknown"

    def _commit_confirmed(self, session: Session) -> None:
        self._commit_status = "committed"

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._session
        if session is None:
            raise RuntimeError("Memory UoW 尚未啟用")
        self._session = None
        self._repository = None
        self._sources = None
        self._release(session, exc_value)
        if isinstance(exc_value, SQLAlchemyError):
            raise self._translate(exc_value) from exc_value

    def _translate(self, error: Exception) -> Exception:
        if (
            self._commit_status == "not_committed"
            and isinstance(error, DBAPIError)
            and isinstance(error.orig, PostgresError)
        ):
            match error.orig.sqlstate:
                case "40001":
                    return MemoryConcurrencyError(reason="serialization")
                case "40P01":
                    return MemoryConcurrencyError(reason="deadlock")
                case "55P03":
                    return MemoryConcurrencyError(reason="lock_timeout")
        # 保留提交證據；未觀察到確認時不推測成功，也不保證原結果回放。
        return MemoryPersistenceError(commit_status=self._commit_status)

    def _release(self, session: Session, primary_error: BaseException | None) -> None:
        cleanup_error: BaseException | None = None
        for cleanup in (session.rollback, session.close):
            try:
                cleanup()
            except BaseException as error:
                preserved = primary_error or cleanup_error
                if not isinstance(error, Exception) and (
                    preserved is None or isinstance(preserved, Exception)
                ):
                    cleanup_error = error
                elif preserved is not None:
                    preserved.add_note(
                        f"Memory {cleanup.__name__} 亦失敗（{type(error).__name__}）"
                    )
                else:
                    cleanup_error = error
        if cleanup_error is not None:
            if isinstance(cleanup_error, Exception):
                raise MemoryPersistenceError(
                    commit_status=self._commit_status
                ) from cleanup_error
            raise cleanup_error
