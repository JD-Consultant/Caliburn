"""真交易保存搭配完成邊界故障注入；不宣稱重演網路故障。"""

from asyncio import CancelledError
from uuid import UUID

import pytest
from psycopg import errors as pg_errors
from sqlalchemy import Connection, Engine, event, text
from sqlalchemy.exc import DBAPIError, InvalidRequestError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import PoolProxiedConnection

from caliburn.modules.job_description.application.errors import (
    JobDescriptionConcurrencyError,
    JobDescriptionPersistenceError,
    JobDescriptionRetryableTransactionError,
)
from caliburn.modules.job_description.application.job_descriptions import (
    create_job_description,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def test_failure_after_flush_before_commit_rolls_back(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """已 flush 後在提交前失敗，回確定未提交且新交易看不到殘留 JD。"""
    session = create_session_factory(pg_engine)()
    failure = OSError("合成提交前故障")

    def fail_before_commit(session: Session) -> None:
        assert session.scalar(text("SELECT count(*) FROM job_descriptions")) == 1
        raise failure

    event.listen(session, "before_commit", fail_before_commit)
    with pytest.raises(JobDescriptionPersistenceError) as error:
        create_job_description(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(lambda: session),
        )
    assert error.value.commit_status == "not_committed"
    assert error.value.__cause__ is failure
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 0


@pytest.mark.parametrize(
    ("commit_reached_database", "sqlstate"),
    [(False, "08007"), (True, "40003")],
)
def test_unconfirmed_commit_keeps_unknown_despite_actual_database_outcome(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
    commit_reached_database: bool,
    sqlstate: str,
) -> None:
    """進入提交區段但沒有確認，保存與未保存兩種實況都只能回 unknown。"""
    original_commit = pg_engine.dialect.do_commit
    attempts = 0

    def factory() -> SqlAlchemyJobDescriptionUnitOfWork:
        nonlocal attempts
        attempts += 1
        return SqlAlchemyJobDescriptionUnitOfWork(create_session_factory(pg_engine))

    def lose_commit_reply(connection: PoolProxiedConnection) -> None:
        if commit_reached_database:
            original_commit(connection)
        raise pg_errors.lookup(sqlstate)("合成提交回覆未知")

    with monkeypatch.context() as injection:
        injection.setattr(pg_engine.dialect, "do_commit", lose_commit_reply)
        with pytest.raises(JobDescriptionPersistenceError) as error:
            create_job_description(
                workspace_id=jd_workspace_id,
                uow_factory=factory,
            )
    assert attempts == 1
    assert error.value.commit_status == "unknown"
    assert error.value.__cause__ is not None
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == (
            1 if commit_reached_database else 0
        )


def test_confirmed_commit_survives_close_failure(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """commit 已確認後 close 失敗，仍回 committed 並保留已保存根。"""
    failure = OSError("合成 close 故障")
    attempts = 0

    class CloseFailureSession(Session):
        def close(self) -> None:
            super().close()
            raise failure

    def factory() -> SqlAlchemyJobDescriptionUnitOfWork:
        nonlocal attempts
        attempts += 1
        session = CloseFailureSession(pg_engine, close_resets_only=False)
        return SqlAlchemyJobDescriptionUnitOfWork(lambda: session)

    with pytest.raises(JobDescriptionPersistenceError) as error:
        create_job_description(
            workspace_id=jd_workspace_id,
            uow_factory=factory,
        )
    assert attempts == 1
    assert error.value.commit_status == "committed"
    assert error.value.__cause__ is failure
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 1


def test_cleanup_failures_do_not_replace_the_original_failure(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """rollback 與 close 皆故障時，原始提交前失敗仍是主要原因。"""
    failure = OSError("合成主要故障")

    class CleanupFailureSession(Session):
        def rollback(self) -> None:
            super().rollback()
            raise OSError("合成 rollback 故障")

        def close(self) -> None:
            super().close()
            raise OSError("合成 close 故障")

    session = CleanupFailureSession(pg_engine, close_resets_only=False)

    def fail_before_commit(session: Session) -> None:
        raise failure

    event.listen(session, "before_commit", fail_before_commit)
    with pytest.raises(JobDescriptionPersistenceError) as error:
        create_job_description(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(lambda: session),
        )
    assert error.value.commit_status == "not_committed"
    assert error.value.__cause__ is failure
    assert len(error.value.__notes__) == 2
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 0


def test_observed_commit_is_not_downgraded_by_later_session_failure(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """已觀察提交確認後 Session 收尾失敗，錯誤代碼也不能抹除 committed。"""
    session = create_session_factory(pg_engine)()
    failure = OperationalError(
        "COMMIT",
        None,
        pg_errors.SerializationFailure("合成確認後故障，非資料庫拒絕"),
    )

    def fail_after_commit(session: Session) -> None:
        raise failure

    event.listen(session, "after_commit", fail_after_commit)
    with pytest.raises(JobDescriptionPersistenceError) as error:
        create_job_description(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(lambda: session),
        )
    assert error.value.commit_status == "committed"
    assert error.value.__cause__ is failure
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 1


def test_failed_transaction_setup_releases_its_session(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """取得連線後、用例開始前的設定故障仍關閉 Session 且不保存。"""
    session = create_session_factory(pg_engine)()
    failure = OSError("合成交易設定故障")

    def fail_after_begin(
        session: Session, transaction: object, connection: Connection
    ) -> None:
        raise failure

    event.listen(session, "after_begin", fail_after_begin)
    with pytest.raises(JobDescriptionPersistenceError) as error:
        create_job_description(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(lambda: session),
        )
    assert error.value.commit_status == "not_committed"
    assert error.value.__cause__ is failure
    with pytest.raises(InvalidRequestError):
        session.begin()
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 0


def test_class_after_commit_failure_cannot_trigger_replay(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """先於 UoW instance hook 的 class hook 失敗不能冒充伺服器序列化拒絕。"""
    attempted_sessions: list[Session] = []
    failure = OperationalError(
        "COMMIT", None, pg_errors.SerializationFailure("合成 hook")
    )

    class HookSession(Session):
        pass

    def fail_after_commit(session: Session) -> None:
        raise failure

    event.listen(HookSession, "after_commit", fail_after_commit)

    def factory() -> SqlAlchemyJobDescriptionUnitOfWork:
        session = HookSession(pg_engine, close_resets_only=False)
        attempted_sessions.append(session)
        return SqlAlchemyJobDescriptionUnitOfWork(lambda: session)

    with pytest.raises(JobDescriptionPersistenceError) as error:
        create_job_description(workspace_id=jd_workspace_id, uow_factory=factory)
    assert len(attempted_sessions) == 1
    assert error.value.commit_status == "unknown"
    assert error.value.__cause__ is failure
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 1


@pytest.mark.parametrize("cleanup_phase", ["rollback", "close"])
def test_cleanup_cancellation_overrides_serialization_failure_and_closes_session(
    pg_engine: Engine, jd_workspace_id: UUID, cleanup_phase: str
) -> None:
    """序列化拒絕清理期間取消時，仍完成 close 並停止重試。"""
    cancellation = CancelledError("清理時取消")
    attempted_sessions: list[Session] = []
    closed: list[Session] = []

    class CancellingSession(Session):
        def rollback(self) -> None:
            super().rollback()
            if cleanup_phase == "rollback":
                raise cancellation

        def close(self) -> None:
            super().close()
            closed.append(self)
            if cleanup_phase == "close":
                raise cancellation

    def reject_before_commit(session: Session) -> None:
        # 真 PG 產生 40001；這個 fixture 只控制失敗時點。
        session.execute(text("DO $$ BEGIN RAISE serialization_failure; END $$"))

    def factory() -> SqlAlchemyJobDescriptionUnitOfWork:
        session = CancellingSession(pg_engine, close_resets_only=False)
        attempted_sessions.append(session)
        event.listen(session, "before_commit", reject_before_commit)
        return SqlAlchemyJobDescriptionUnitOfWork(lambda: session)

    with pytest.raises(CancelledError) as error:
        create_job_description(workspace_id=jd_workspace_id, uow_factory=factory)
    assert error.value is cancellation
    assert isinstance(error.value.__context__, JobDescriptionConcurrencyError)
    assert len(attempted_sessions) == 1
    assert closed == attempted_sessions
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 0


@pytest.mark.parametrize(
    ("sqlstate", "attempt_count", "error_type", "reason"),
    [
        ("40001", 3, JobDescriptionRetryableTransactionError, "serialization"),
        ("40P01", 1, JobDescriptionConcurrencyError, "deadlock"),
        ("55P03", 1, JobDescriptionConcurrencyError, "lock_timeout"),
        ("23505", 1, JobDescriptionPersistenceError, None),
    ],
)
def test_only_serialization_rejection_replays_and_exhaustion_keeps_database_cause(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    sqlstate: str,
    attempt_count: int,
    error_type: type[Exception],
    reason: str | None,
) -> None:
    """伺服器明確拒絕的分類沿公開用例驗證，失敗輪次都沒有留下根。"""
    sessions = create_session_factory(pg_engine)
    attempted_sessions: list[Session] = []

    def reject_before_commit(session: Session) -> None:
        session.execute(
            text(
                "DO $$ BEGIN RAISE EXCEPTION 'synthetic rejection' "
                f"USING ERRCODE = '{sqlstate}'; END $$"
            )
        )

    def factory() -> SqlAlchemyJobDescriptionUnitOfWork:
        session = sessions()
        attempted_sessions.append(session)
        event.listen(session, "before_commit", reject_before_commit)
        return SqlAlchemyJobDescriptionUnitOfWork(lambda: session)

    with pytest.raises(error_type) as error:
        create_job_description(workspace_id=jd_workspace_id, uow_factory=factory)
    assert type(error.value) is error_type
    assert getattr(error.value, "reason", None) == reason
    assert len(attempted_sessions) == attempt_count
    assert len({id(session) for session in attempted_sessions}) == attempt_count
    assert isinstance(error.value.__cause__, DBAPIError)
    assert isinstance(error.value.__cause__.orig, pg_errors.lookup(sqlstate))
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 0
