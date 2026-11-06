"""真交易搭配具體 DB／Session 故障，驗證原子性與提交證據。"""

from asyncio import CancelledError
from functools import partial
from uuid import UUID

import pytest
from psycopg import errors as pg_errors
from sqlalchemy import Engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import PoolProxiedConnection

from caliburn.modules.plan.application.errors import (
    PlanPersistenceError,
    PlanQueryError,
    PlanVersionNotFoundError,
)
from caliburn.modules.plan.application.plans import (
    initialize_plan,
    patch_plan,
    restore_plan,
)
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def test_snapshot_failure_rolls_back_the_current_body(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyPlanUnitOfWork, sessions)
    initial = initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    with pg_engine.begin() as connection:
        connection.execute(
            text("""
            CREATE FUNCTION reject_plan_version() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'synthetic version rejection' USING ERRCODE='23514';
            END $$
        """)
        )
        connection.execute(
            text("""
            CREATE TRIGGER reject_plan_version BEFORE INSERT ON plan_versions
            FOR EACH ROW EXECUTE FUNCTION reject_plan_version()
        """)
        )

    with pytest.raises(PlanPersistenceError) as error:
        patch_plan(
            workspace_id=jd_workspace_id,
            expected_version=1,
            diff="@@\n+不得留下半筆\n*** End of File",
            uow_factory=factory,
        )

    assert error.value.commit_status == "not_committed"
    assert (
        SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=jd_workspace_id)
        == initial
    )
    with pytest.raises(PlanVersionNotFoundError):
        restore_plan(
            workspace_id=jd_workspace_id,
            expected_version=1,
            target_version=2,
            uow_factory=factory,
        )


@pytest.mark.parametrize(
    ("phase", "expected_status", "saved_version"),
    [
        ("before_commit", "not_committed", None),
        ("after_commit", "committed", 1),
    ],
)
def test_commit_event_failure_preserves_observed_outcome(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    phase: str,
    expected_status: str,
    saved_version: int | None,
) -> None:
    session = create_session_factory(pg_engine)()

    def fail(session: Session) -> None:
        raise OSError("synthetic session failure")

    event.listen(session, phase, fail)
    with pytest.raises(PlanPersistenceError) as error:
        initialize_plan(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyPlanUnitOfWork(lambda: session),
        )
    assert error.value.commit_status == expected_status
    assert (
        SqlAlchemyPlanQueries(pg_engine)
        .get_current(workspace_id=jd_workspace_id)
        .version
        == saved_version
    )


@pytest.mark.parametrize("commit_reached_database", [False, True])
def test_unconfirmed_commit_is_unknown_without_automatic_replay(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
    commit_reached_database: bool,
) -> None:
    native_commit = pg_engine.dialect.do_commit
    attempts = 0

    def lose_reply(connection: PoolProxiedConnection) -> None:
        if commit_reached_database:
            native_commit(connection)
        raise pg_errors.TransactionResolutionUnknown("synthetic lost reply")

    def factory() -> SqlAlchemyPlanUnitOfWork:
        nonlocal attempts
        attempts += 1
        return SqlAlchemyPlanUnitOfWork(create_session_factory(pg_engine))

    with monkeypatch.context() as injection:
        injection.setattr(pg_engine.dialect, "do_commit", lose_reply)
        with pytest.raises(PlanPersistenceError) as error:
            initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    assert error.value.commit_status == "unknown"
    assert attempts == 1
    assert SqlAlchemyPlanQueries(pg_engine).get_current(
        workspace_id=jd_workspace_id
    ).version == (1 if commit_reached_database else None)


def test_close_failure_does_not_erase_confirmed_commit(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    class CloseFailureSession(Session):
        def close(self) -> None:
            super().close()
            raise OSError("synthetic close failure")

    with pytest.raises(PlanPersistenceError) as error:
        initialize_plan(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyPlanUnitOfWork(
                lambda: CloseFailureSession(pg_engine, close_resets_only=False)
            ),
        )
    assert error.value.commit_status == "committed"
    assert (
        SqlAlchemyPlanQueries(pg_engine)
        .get_current(workspace_id=jd_workspace_id)
        .version
        == 1
    )


def test_native_deferred_constraint_rejection_is_known_not_committed(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    with pg_engine.begin() as connection:
        connection.execute(
            text("""
            CREATE FUNCTION reject_plan_commit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'synthetic deferred rejection' USING ERRCODE='23514';
            END $$
        """)
        )
        connection.execute(
            text("""
            CREATE CONSTRAINT TRIGGER reject_plan_commit AFTER INSERT ON plan_versions
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION reject_plan_commit()
        """)
        )
    with pytest.raises(PlanPersistenceError) as error:
        initialize_plan(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyPlanUnitOfWork(
                create_session_factory(pg_engine)
            ),
        )
    assert error.value.commit_status == "not_committed"
    assert (
        SqlAlchemyPlanQueries(pg_engine)
        .get_current(workspace_id=jd_workspace_id)
        .version
        is None
    )


def test_unobserved_class_hook_failure_is_not_mistaken_for_database_rejection(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    class HookSession(Session):
        pass

    def fail_after_commit(session: Session) -> None:
        raise OperationalError(
            "COMMIT", None, pg_errors.SerializationFailure("synthetic hook")
        )

    event.listen(HookSession, "after_commit", fail_after_commit)
    with pytest.raises(PlanPersistenceError) as error:
        initialize_plan(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyPlanUnitOfWork(
                lambda: HookSession(pg_engine, close_resets_only=False)
            ),
        )
    assert error.value.commit_status == "unknown"
    assert (
        SqlAlchemyPlanQueries(pg_engine)
        .get_current(workspace_id=jd_workspace_id)
        .version
        == 1
    )


def test_cleanup_cancellation_propagates_after_releasing_resources(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    class CancellingSession(Session):
        def close(self) -> None:
            super().close()
            raise CancelledError("synthetic cancellation")

    session = CancellingSession(pg_engine, close_resets_only=False)

    def reject(session: Session) -> None:
        raise OSError("synthetic original failure")

    event.listen(session, "before_commit", reject)
    with pytest.raises(CancelledError):
        initialize_plan(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyPlanUnitOfWork(lambda: session),
        )
    assert (
        SqlAlchemyPlanQueries(pg_engine)
        .get_current(workspace_id=jd_workspace_id)
        .version
        is None
    )


def test_query_close_failure_cannot_return_empty_success(
    pg_engine: Engine, jd_workspace_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_close = Session.close

    def fail_close(session: Session) -> None:
        original_close(session)
        raise OSError("synthetic query cleanup failure")

    with monkeypatch.context() as injection:
        injection.setattr(Session, "close", fail_close)
        with pytest.raises(PlanQueryError):
            SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=jd_workspace_id)
