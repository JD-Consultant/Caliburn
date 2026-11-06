"""Interview 單次 Session、顯式提交與提交證據。"""

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy import Connection, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from caliburn.modules.interview.application.errors import InterviewPersistenceError
from caliburn.modules.interview.infrastructure.persistence.errors import (
    FAILURE_EVIDENCE_OPTION,
    CommitStatus,
    DatabaseFailureEvidence,
    translate_persistence_error,
)
from caliburn.modules.interview.infrastructure.persistence.repository import (
    SqlAlchemyInterviewRepository,
)


class SqlAlchemyInterviewUnitOfWork:
    """factory 提供全新 Session；用例正常返回前完成提交與資源釋放。"""

    def __init__(
        self, session_factory: Callable[[], Session], *, lock_timeout_ms: int = 5000
    ) -> None:
        if (
            type(lock_timeout_ms) is not int
            or not 1 <= lock_timeout_ms <= 2_147_483_647
        ):
            raise ValueError("lock_timeout_ms 必須是有限的正整數毫秒")
        self._session_factory = session_factory
        self._lock_timeout_ms = lock_timeout_ms
        self._session: Session | None = None
        self._repository: SqlAlchemyInterviewRepository | None = None
        self._commit_status: CommitStatus = "not_committed"
        self._failure_evidence = DatabaseFailureEvidence()

    @property
    def turns(self) -> SqlAlchemyInterviewRepository:
        if self._repository is None:
            raise RuntimeError("Interview UoW 目前未啟用")
        return self._repository

    def __enter__(self) -> Self:
        if self._session is not None:
            raise RuntimeError("Interview UoW 已啟用")
        self._commit_status = "not_committed"
        self._failure_evidence.error = None
        try:
            session = self._session_factory()
        except Exception as error:
            raise InterviewPersistenceError(commit_status="not_committed") from error
        try:
            session.autobegin = False
            session.begin()
            connection = session.connection(
                execution_options={
                    "isolation_level": "READ COMMITTED",
                    FAILURE_EVIDENCE_OPTION: self._failure_evidence,
                }
            )
            event.listen(connection, "commit", self._commit_may_be_sent)
            event.listen(session, "after_commit", self._commit_confirmed, insert=True)
            session.execute(
                text("SELECT set_config('lock_timeout', :timeout, true)"),
                {"timeout": f"{self._lock_timeout_ms}ms"},
            )
        except BaseException as error:
            self._release(session, error)
            if isinstance(error, Exception):
                raise translate_persistence_error(
                    error, commit_status=self._commit_status
                ) from error
            raise
        self._session = session
        self._repository = SqlAlchemyInterviewRepository(session)
        return self

    def commit(self) -> None:
        session = self._active_session()
        try:
            session.commit()
            self._commit_status = "committed"
        except Exception as error:
            raise translate_persistence_error(
                error,
                commit_status=self._commit_status,
                database_error=self._failure_evidence.error,
            ) from error
        finally:
            self._failure_evidence.error = None

    def _commit_may_be_sent(self, connection: Connection) -> None:
        self._commit_status = "unknown"

    def _commit_confirmed(self, session: Session) -> None:
        self._commit_status = "committed"

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._active_session()
        self._session = None
        self._repository = None
        self._release(session, exc_value)
        if isinstance(exc_value, SQLAlchemyError):
            raise translate_persistence_error(
                exc_value,
                commit_status=self._commit_status,
                database_error=self._failure_evidence.error,
            ) from exc_value

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
                    continue
                if preserved is not None:
                    preserved.add_note(
                        f"Interview {cleanup.__name__} 亦失敗（{type(error).__name__}）"
                    )
                else:
                    cleanup_error = error
        if cleanup_error is not None:
            if isinstance(cleanup_error, Exception):
                raise InterviewPersistenceError(
                    commit_status=self._commit_status
                ) from cleanup_error
            raise cleanup_error

    def _active_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("Interview UoW 目前未啟用")
        return self._session
