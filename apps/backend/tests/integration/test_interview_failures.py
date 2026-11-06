"""以真交易和邊界故障驗證原子性、提交證據與資源釋放。"""

from functools import partial
from uuid import UUID, uuid4

import pytest
from psycopg import errors as pg_errors
from sqlalchemy import Engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import PoolProxiedConnection

from caliburn.modules.interview.application.errors import (
    InterviewPersistenceError,
    InterviewQueryError,
)
from caliburn.modules.interview.application.recording import (
    record_questions,
    record_turn_input,
)
from caliburn.modules.interview.domain.models.message_content import Question
from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def test_database_rejection_of_last_question_rolls_back_entire_call(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))
    turn_id = uuid4()
    record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="保留原輸入",
        uow_factory=factory,
    )
    queries = SqlAlchemyInterviewQueries(pg_engine)
    before = queries.list_messages(workspace_id=jd_workspace_id)
    with pg_engine.begin() as connection:
        connection.execute(
            text("""
            CREATE FUNCTION reject_last_question() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.position = 2 THEN
                    RAISE EXCEPTION 'synthetic last message rejection'
                        USING ERRCODE='23514';
                END IF;
                RETURN NEW;
            END $$
        """)
        )
        connection.execute(
            text("""
            CREATE TRIGGER reject_last_question BEFORE INSERT ON interview_messages
            FOR EACH ROW EXECUTE FUNCTION reject_last_question()
        """)
        )
    with pytest.raises(InterviewPersistenceError) as rejected:
        record_questions(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            questions=(Question(question="第一題"), Question(question="第二題")),
            uow_factory=factory,
        )
    assert rejected.value.commit_status == "not_committed"
    assert queries.list_messages(workspace_id=jd_workspace_id) == before


@pytest.mark.parametrize(
    ("phase", "expected_status", "saved"),
    [("before_commit", "not_committed", False), ("after_commit", "committed", True)],
)
def test_commit_event_failure_preserves_observed_outcome(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    phase: str,
    expected_status: str,
    saved: bool,
) -> None:
    session = create_session_factory(pg_engine)()

    def fail(session: Session) -> None:
        raise OSError("synthetic commit hook failure")

    event.listen(session, phase, fail)
    with pytest.raises(InterviewPersistenceError) as rejected:
        record_turn_input(
            workspace_id=jd_workspace_id,
            turn_id=uuid4(),
            text="提交證據",
            uow_factory=lambda: SqlAlchemyInterviewUnitOfWork(lambda: session),
        )
    assert rejected.value.commit_status == expected_status
    assert len(
        SqlAlchemyInterviewQueries(pg_engine).list_messages(
            workspace_id=jd_workspace_id
        )
    ) == int(saved)


@pytest.mark.parametrize("commit_reached_database", [False, True])
def test_lost_commit_acknowledgement_is_unknown_without_automatic_replay(
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

    def factory() -> SqlAlchemyInterviewUnitOfWork:
        nonlocal attempts
        attempts += 1
        return SqlAlchemyInterviewUnitOfWork(create_session_factory(pg_engine))

    with monkeypatch.context() as injection:
        injection.setattr(pg_engine.dialect, "do_commit", lose_reply)
        with pytest.raises(InterviewPersistenceError) as rejected:
            record_turn_input(
                workspace_id=jd_workspace_id,
                turn_id=uuid4(),
                text="未知提交",
                uow_factory=factory,
            )
    assert rejected.value.commit_status == "unknown"
    assert attempts == 1
    assert len(
        SqlAlchemyInterviewQueries(pg_engine).list_messages(
            workspace_id=jd_workspace_id
        )
    ) == int(commit_reached_database)


def test_close_failure_keeps_confirmed_commit_evidence(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    class CloseFailureSession(Session):
        def close(self) -> None:
            super().close()
            raise OSError("synthetic close failure")

    with pytest.raises(InterviewPersistenceError) as rejected:
        record_turn_input(
            workspace_id=jd_workspace_id,
            turn_id=uuid4(),
            text="保存後收尾失敗",
            uow_factory=lambda: SqlAlchemyInterviewUnitOfWork(
                lambda: CloseFailureSession(pg_engine, close_resets_only=False)
            ),
        )
    assert rejected.value.commit_status == "committed"
    assert (
        len(
            SqlAlchemyInterviewQueries(pg_engine).list_messages(
                workspace_id=jd_workspace_id
            )
        )
        == 1
    )


def test_deferred_database_constraint_rejection_is_known_not_committed(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    with pg_engine.begin() as connection:
        connection.execute(
            text("""
            CREATE FUNCTION reject_interview_commit() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'synthetic deferred rejection' USING ERRCODE='23514';
            END $$
        """)
        )
        connection.execute(
            text("""
            CREATE CONSTRAINT TRIGGER reject_interview_commit
            AFTER INSERT ON interview_messages
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION reject_interview_commit()
        """)
        )
    with pytest.raises(InterviewPersistenceError) as rejected:
        record_turn_input(
            workspace_id=jd_workspace_id,
            turn_id=uuid4(),
            text="延遲約束",
            uow_factory=partial(
                SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
            ),
        )
    assert rejected.value.commit_status == "not_committed"
    assert (
        SqlAlchemyInterviewQueries(pg_engine).list_messages(
            workspace_id=jd_workspace_id
        )
        == ()
    )


def test_query_cleanup_failure_is_not_returned_as_empty_interview(
    pg_engine: Engine, jd_workspace_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    native_close = Session.close

    def fail_close(session: Session) -> None:
        native_close(session)
        raise OSError("synthetic query cleanup failure")

    with monkeypatch.context() as injection:
        injection.setattr(Session, "close", fail_close)
        with pytest.raises(InterviewQueryError):
            SqlAlchemyInterviewQueries(pg_engine).list_messages(
                workspace_id=jd_workspace_id
            )
