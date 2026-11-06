"""JD 專用交易邊界。"""

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy import Connection, event, text
from sqlalchemy.orm import Session

from caliburn.modules.job_description.application.errors import (
    CommitStatus,
    JobDescriptionPersistenceError,
)
from caliburn.modules.job_description.infrastructure.persistence.errors import (
    translate_persistence_error,
)

from .citation_sources import SqlAlchemyCitationSources
from .history_reader import SqlAlchemyJobDescriptionHistoryReader
from .job_description_repository import (
    SqlAlchemyJobDescriptionRepository,
)
from .transaction_outcome import (
    FAILURE_EVIDENCE_OPTION,
    DatabaseFailureEvidence,
)


class SqlAlchemyJobDescriptionUnitOfWork:
    """擁有單一新 Session／交易；factory 不提供已啟動或自行提交的 Session。"""

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
        self._repository: SqlAlchemyJobDescriptionRepository | None = None
        self._history: SqlAlchemyJobDescriptionHistoryReader | None = None
        self._commit_status: CommitStatus = "not_committed"
        self._failure_evidence = DatabaseFailureEvidence()

    @property
    def job_descriptions(self) -> SqlAlchemyJobDescriptionRepository:
        if self._repository is None:
            raise RuntimeError("JD UoW 目前未啟用")
        return self._repository

    @property
    def history(self) -> SqlAlchemyJobDescriptionHistoryReader:
        if self._history is None:
            raise RuntimeError("JD UoW 目前未啟用")
        return self._history

    @property
    def citation_sources(self) -> SqlAlchemyCitationSources:
        return SqlAlchemyCitationSources(self._active_session())

    def __enter__(self) -> Self:
        if self._session is not None:
            raise RuntimeError("JD UoW 已啟用，不可重複進入")
        self._commit_status = "not_committed"
        self._failure_evidence.error = None
        try:
            session = self._session_factory()
        except Exception as error:
            raise JobDescriptionPersistenceError(
                commit_status="not_committed"
            ) from error
        try:
            # 關閉自動重開交易；commit 後不能偷偷開始另一筆未設隔離的工作。
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
            self._release_session(session, error)
            if isinstance(error, Exception):
                raise translate_persistence_error(
                    error, commit_status=self._commit_status
                ) from error
            raise
        self._session = session
        self._repository = SqlAlchemyJobDescriptionRepository(session)
        self._history = SqlAlchemyJobDescriptionHistoryReader(session)
        return self

    def commit(self) -> None:
        session = self._active_session()
        try:
            session.flush()
            session.commit()
            self._commit_status = "committed"
        except Exception as error:
            # 已進入 COMMIT 後，只有原生錯誤事件觀察到的同一個 wrapper 能
            # 證明 40001 是伺服器拒絕；after_commit hook 可拋相同型別的錯誤。
            if (
                self._commit_status == "unknown"
                and error is not self._failure_evidence.error
            ):
                raise JobDescriptionPersistenceError(commit_status="unknown") from error
            raise translate_persistence_error(
                error, commit_status=self._commit_status
            ) from error
        finally:
            self._failure_evidence.error = None

    def _commit_may_be_sent(self, connection: Connection) -> None:
        # 事件發生於 DBAPI commit 前；只表示進入可能送出的區段。
        self._commit_status = "unknown"

    def _commit_confirmed(self, session: Session) -> None:
        # 若更早的外部 class hook 中斷，未觀察到確認時仍保守保留 unknown。
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
        self._history = None
        self._release_session(session, exc_value)

    def _release_session(
        self, session: Session, primary_error: BaseException | None
    ) -> None:
        cleanup_error: BaseException | None = None
        interruption: BaseException | None = None
        for cleanup in (session.rollback, session.close):
            try:
                cleanup()
            except BaseException as error:
                if not isinstance(error, Exception) and (
                    primary_error is None or isinstance(primary_error, Exception)
                ):
                    if interruption is None:
                        interruption = error
                        continue
                preserved_error = interruption or primary_error or cleanup_error
                if preserved_error is not None:
                    preserved_error.add_note(
                        f"JD {cleanup.__name__} 亦失敗（{type(error).__name__}）"
                    )
                else:
                    cleanup_error = error
        self._failure_evidence.error = None
        if interruption is not None:
            raise interruption
        if cleanup_error is not None:
            if isinstance(cleanup_error, Exception):
                raise JobDescriptionPersistenceError(
                    commit_status=self._commit_status
                ) from cleanup_error
            raise cleanup_error

    def _active_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("JD UoW 目前未啟用")
        return self._session
