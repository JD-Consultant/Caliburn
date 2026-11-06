"""真 PostgreSQL 列鎖證據：初建收斂、同題回覆與撤回競爭。"""

from concurrent.futures import ThreadPoolExecutor
from functools import partial
from queue import Queue
from threading import Event
from time import monotonic
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Connection, Engine, event, text
from sqlalchemy.orm import Session

from caliburn.modules.interview.application.errors import (
    InterviewConcurrencyError,
    InterviewTurnNotFoundError,
    WorkspaceNotFoundError,
)
from caliburn.modules.interview.application.recording import (
    record_answers,
    record_consultant_message,
    record_opening,
    record_questions,
    record_turn_input,
)
from caliburn.modules.interview.application.results import MessageView
from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.domain.errors import (
    InterviewAnswerConflictError,
    InterviewInputConflictError,
    InterviewTurnWithdrawnError,
)
from caliburn.modules.interview.domain.models.message_content import (
    AnswerInput,
    Question,
)
from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def _wait_for_block(engine: Engine, *, waiting: int, blocking: int) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        with engine.connect() as connection:
            blockers = connection.scalar(
                text("SELECT pg_blocking_pids(:pid)"), {"pid": waiting}
            )
        if blocking in blockers:
            return
    raise AssertionError("未觀察到預期的 PostgreSQL 鎖等待")


def _report_on_begin(session: Session, reported: Queue[int]) -> None:
    def report(session: Session, transaction: object, connection: Connection) -> None:
        pid = connection.scalar(text("SELECT pg_backend_pid()"))
        assert isinstance(pid, int)
        reported.put(pid)

    event.listen(session, "after_begin", report)


@pytest.mark.parametrize("opening", [False, True])
@pytest.mark.parametrize("same_input", [False, True])
def test_same_turn_initialization_waits_and_returns_one_original_message(
    pg_engine: Engine, jd_workspace_id: UUID, opening: bool, same_input: bool
) -> None:
    sessions = create_session_factory(pg_engine)
    turn_id = uuid4()
    first_pid: Queue[int] = Queue()
    second_pid: Queue[int] = Queue()
    release = Event()

    def hold(session: Session) -> None:
        pid = session.scalar(text("SELECT pg_backend_pid()"))
        assert isinstance(pid, int)
        first_pid.put(pid)
        assert release.wait(8), "第一個訪談建立未獲釋放"

    def create(*, first: bool) -> MessageView:
        session = sessions()
        if first:
            event.listen(session, "before_commit", hold)
        else:
            _report_on_begin(session, second_pid)
        factory = partial(SqlAlchemyInterviewUnitOfWork, lambda: session)
        original = "原始輸入" if first or same_input else "不同原文"
        if opening:
            return record_opening(
                workspace_id=jd_workspace_id, text=original, uow_factory=factory
            )
        return record_turn_input(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            text=original,
            uow_factory=factory,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(create, first=True)
        try:
            blocking = first_pid.get(timeout=5)
            second = executor.submit(create, first=False)
            _wait_for_block(
                pg_engine, waiting=second_pid.get(timeout=5), blocking=blocking
            )
        finally:
            release.set()
        initial = first.result(timeout=5)
        if same_input:
            assert second.result(timeout=5) == initial
        else:
            with pytest.raises(InterviewInputConflictError):
                second.result(timeout=5)
    messages = SqlAlchemyInterviewQueries(pg_engine).list_messages(
        workspace_id=jd_workspace_id
    )
    assert [message.message_id for message in messages] == [initial.message_id]


@pytest.mark.parametrize("same_answer", [False, True])
def test_concurrent_answers_reuse_one_message_or_reject_different_answer(
    pg_engine: Engine, jd_workspace_id: UUID, same_answer: bool
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyInterviewUnitOfWork, sessions)
    turn_id = uuid4()
    record_turn_input(
        workspace_id=jd_workspace_id, turn_id=turn_id, text="原文", uow_factory=factory
    )
    (question,) = record_questions(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        questions=(Question(question="問題"),),
        uow_factory=factory,
    )
    first_pid: Queue[int] = Queue()
    second_pid: Queue[int] = Queue()
    release = Event()

    def hold(session: Session) -> None:
        pid = session.scalar(text("SELECT pg_backend_pid()"))
        assert isinstance(pid, int)
        first_pid.put(pid)
        assert release.wait(8), "第一筆回答未獲釋放"

    def answer(*, first: bool) -> tuple[MessageView, ...]:
        session = sessions()
        if first:
            event.listen(session, "before_commit", hold)
        else:
            _report_on_begin(session, second_pid)
        return record_answers(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            answers=(
                AnswerInput(
                    question_message_id=question.message_id,
                    custom="原答案" if first or same_answer else "不同答案",
                ),
            ),
            uow_factory=partial(SqlAlchemyInterviewUnitOfWork, lambda: session),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(answer, first=True)
        try:
            blocking = first_pid.get(timeout=5)
            second = executor.submit(answer, first=False)
            _wait_for_block(
                pg_engine, waiting=second_pid.get(timeout=5), blocking=blocking
            )
        finally:
            release.set()
        saved = first.result(timeout=5)
        if same_answer:
            assert second.result(timeout=5) == saved
        else:
            with pytest.raises(InterviewAnswerConflictError):
                second.result(timeout=5)
    answers = [
        message
        for message in SqlAlchemyInterviewQueries(pg_engine).list_messages(
            workspace_id=jd_workspace_id
        )
        if message.kind == "answer"
    ]
    assert [message.message_id for message in answers] == [saved[0].message_id]


@pytest.mark.parametrize("withdraw_first", [False, True])
def test_withdrawal_and_late_append_share_one_lock_and_leave_no_visible_messages(
    pg_engine: Engine, jd_workspace_id: UUID, withdraw_first: bool
) -> None:
    sessions = create_session_factory(pg_engine)
    turn_id = uuid4()
    record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="原文",
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, sessions),
    )
    first_pid: Queue[int] = Queue()
    second_pid: Queue[int] = Queue()
    release = Event()

    def hold(session: Session) -> None:
        pid = session.scalar(text("SELECT pg_backend_pid()"))
        assert isinstance(pid, int)
        first_pid.put(pid)
        assert release.wait(8), "第一個訪談修改未獲釋放"

    def operate(*, first: bool) -> None:
        session = sessions()
        if first:
            event.listen(session, "before_commit", hold)
        else:
            _report_on_begin(session, second_pid)
        factory = partial(SqlAlchemyInterviewUnitOfWork, lambda: session)
        if first == withdraw_first:
            withdraw_turn(
                workspace_id=jd_workspace_id, turn_id=turn_id, uow_factory=factory
            )
        else:
            record_consultant_message(
                workspace_id=jd_workspace_id,
                turn_id=turn_id,
                text="遲到的顧問文字",
                uow_factory=factory,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(operate, first=True)
        try:
            blocking = first_pid.get(timeout=5)
            second = executor.submit(operate, first=False)
            _wait_for_block(
                pg_engine, waiting=second_pid.get(timeout=5), blocking=blocking
            )
        finally:
            release.set()
        first.result(timeout=5)
        if withdraw_first:
            with pytest.raises(InterviewTurnWithdrawnError):
                second.result(timeout=5)
        else:
            second.result(timeout=5)
    assert (
        SqlAlchemyInterviewQueries(pg_engine).list_messages(
            workspace_id=jd_workspace_id
        )
        == ()
    )


def test_same_turn_lock_timeout_is_reported_without_automatic_retry(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    turn_id = uuid4()
    record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="原文",
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, sessions),
    )
    with SqlAlchemyInterviewUnitOfWork(sessions) as held:
        assert (
            held.turns.get_for_update(workspace_id=jd_workspace_id, turn_id=turn_id)
            is not None
        )
        with pytest.raises(InterviewConcurrencyError) as rejected:
            record_consultant_message(
                workspace_id=jd_workspace_id,
                turn_id=turn_id,
                text="無法取得鎖",
                uow_factory=partial(
                    SqlAlchemyInterviewUnitOfWork, sessions, lock_timeout_ms=50
                ),
            )
    assert rejected.value.reason == "lock_timeout"
    assert (
        len(
            SqlAlchemyInterviewQueries(pg_engine).list_messages(
                workspace_id=jd_workspace_id
            )
        )
        == 1
    )


@pytest.mark.parametrize("initialized", [False, True])
def test_workspace_deletion_wins_without_late_interview_recreation(
    pg_engine: Engine, jd_workspace_id: UUID, initialized: bool
) -> None:
    sessions = create_session_factory(pg_engine)
    turn_id = uuid4()
    if initialized:
        record_turn_input(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            text="原文",
            uow_factory=partial(SqlAlchemyInterviewUnitOfWork, sessions),
        )
    waiting_pid: Queue[int] = Queue()

    def write() -> None:
        session = sessions()
        _report_on_begin(session, waiting_pid)
        factory = partial(SqlAlchemyInterviewUnitOfWork, lambda: session)
        if initialized:
            with pytest.raises(InterviewTurnNotFoundError):
                record_consultant_message(
                    workspace_id=jd_workspace_id,
                    turn_id=turn_id,
                    text="不得復生",
                    uow_factory=factory,
                )
        else:
            with pytest.raises(WorkspaceNotFoundError):
                record_turn_input(
                    workspace_id=jd_workspace_id,
                    turn_id=turn_id,
                    text="不得復生",
                    uow_factory=factory,
                )

    with ThreadPoolExecutor(max_workers=1) as executor:
        deleting_session = sessions()
        with SqlAlchemyWorkspaceUnitOfWork(lambda: deleting_session) as deleting:
            deleting.workspaces.delete(jd_workspace_id)
            blocking = deleting_session.scalar(text("SELECT pg_backend_pid()"))
            assert isinstance(blocking, int)
            pending = executor.submit(write)
            _wait_for_block(
                pg_engine, waiting=waiting_pid.get(timeout=5), blocking=blocking
            )
            deleting.commit()
        pending.result(timeout=5)
    with pytest.raises(WorkspaceNotFoundError):
        SqlAlchemyInterviewQueries(pg_engine).list_messages(
            workspace_id=jd_workspace_id
        )
