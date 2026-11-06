"""已完成輪次的正式來源包含完整題答；同交易資格鎖由呼叫端選擇。"""

from functools import partial
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine

from caliburn.modules.interview.application.errors import InterviewConcurrencyError
from caliburn.modules.interview.application.recording import (
    record_answers,
    record_consultant_message,
    record_opening,
    record_questions,
    record_turn_input,
)
from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.domain.models.message_content import (
    AnswerInput,
    Question,
)
from caliburn.modules.interview.infrastructure.persistence.public_queries import (
    read_completed_interview_message_ids,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


@pytest.mark.parametrize("lock_turns", [False, True])
def test_completed_turn_includes_questions_answers_and_explicit_skip(
    pg_engine: Engine, jd_workspace_id: UUID, lock_turns: bool
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyInterviewUnitOfWork, sessions)
    turn_id = uuid4()
    original = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="工作原文",
        uow_factory=factory,
    )
    first, second = record_questions(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        questions=(Question(question="第一題？"), Question(question="第二題？")),
        uow_factory=factory,
    )
    answer, skipped = record_answers(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        answers=(
            AnswerInput(question_message_id=first.message_id, custom="第一題原始回答"),
            AnswerInput(question_message_id=second.message_id),
        ),
        uow_factory=factory,
    )
    final = record_consultant_message(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="正式收尾",
        uow_factory=factory,
    )

    with sessions.begin() as session:
        selected = read_completed_interview_message_ids(
            session,
            workspace_id=jd_workspace_id,
            completed_turn_ids=frozenset({turn_id}),
            lock_turns=lock_turns,
        )

    assert selected == (
        original.message_id,
        first.message_id,
        second.message_id,
        answer.message_id,
        skipped.message_id,
        final.message_id,
    )


@pytest.mark.parametrize("lock_turns", [False, True])
def test_completed_sources_keep_formal_order_and_exclude_other_scopes(
    pg_engine: Engine, jd_workspace_id: UUID, lock_turns: bool
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyInterviewUnitOfWork, sessions)
    other_workspace = (
        WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions))
        .create(interviewee_name="其他來源範圍")
        .workspace_id
    )
    opening = record_opening(
        workspace_id=jd_workspace_id, text="App 開場", uow_factory=factory
    )
    first_turn, last_turn = UUID(int=900), UUID(int=100)
    first = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=first_turn,
        text="正式第一輪",
        uow_factory=factory,
    )
    first_final = record_consultant_message(
        workspace_id=jd_workspace_id,
        turn_id=first_turn,
        text="第一輪收尾",
        uow_factory=factory,
    )
    unfinished = uuid4()
    record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=unfinished,
        text="未完成原話",
        uow_factory=factory,
    )
    record_consultant_message(
        workspace_id=jd_workspace_id,
        turn_id=unfinished,
        text="有顧問發話也不能自行推定完成",
        uow_factory=factory,
    )
    withdrawn = uuid4()
    for workspace_id, turn_id in (
        (jd_workspace_id, withdrawn),
        (other_workspace, first_turn),
    ):
        record_turn_input(
            workspace_id=workspace_id,
            turn_id=turn_id,
            text="不可納入的原話",
            uow_factory=factory,
        )
        record_consultant_message(
            workspace_id=workspace_id,
            turn_id=turn_id,
            text="不可納入的收尾",
            uow_factory=factory,
        )
    withdraw_turn(workspace_id=jd_workspace_id, turn_id=withdrawn, uow_factory=factory)
    last = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=last_turn,
        text="正式第二輪",
        uow_factory=factory,
    )
    last_final = record_consultant_message(
        workspace_id=jd_workspace_id,
        turn_id=last_turn,
        text="第二輪收尾",
        uow_factory=factory,
    )
    with sessions.begin() as session:
        selected = read_completed_interview_message_ids(
            session,
            workspace_id=jd_workspace_id,
            completed_turn_ids=frozenset(
                {last_turn, first_turn, withdrawn, opening.turn_id, uuid4()}
            ),
            lock_turns=lock_turns,
        )
        assert selected == (
            first.message_id,
            first_final.message_id,
            last.message_id,
            last_final.message_id,
        )
        assert (
            read_completed_interview_message_ids(
                session,
                workspace_id=jd_workspace_id,
                completed_turn_ids=frozenset(),
                lock_turns=lock_turns,
            )
            == ()
        )


def test_completed_scope_is_not_reinferred_from_employee_and_final_pairs(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    turn_id = uuid4()
    original = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="由呼叫端提供完成資格",
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, sessions),
    )
    with sessions.begin() as session:
        assert read_completed_interview_message_ids(
            session,
            workspace_id=jd_workspace_id,
            completed_turn_ids=frozenset({turn_id}),
            lock_turns=False,
        ) == (original.message_id,)


@pytest.mark.parametrize("lock_turns", [False, True])
def test_source_lock_prevents_withdrawal_only_until_the_callers_transaction_ends(
    pg_engine: Engine, jd_workspace_id: UUID, lock_turns: bool
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyInterviewUnitOfWork, sessions, lock_timeout_ms=100)
    turn_id = uuid4()
    original = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="同交易鎖定來源",
        uow_factory=factory,
    )
    with sessions.begin() as session:
        assert read_completed_interview_message_ids(
            session,
            workspace_id=jd_workspace_id,
            completed_turn_ids=frozenset({turn_id}),
            lock_turns=lock_turns,
        ) == (original.message_id,)
        if lock_turns:
            with pytest.raises(InterviewConcurrencyError) as failure:
                withdraw_turn(
                    workspace_id=jd_workspace_id,
                    turn_id=turn_id,
                    uow_factory=factory,
                )
            assert failure.value.reason == "lock_timeout"
        else:
            withdraw_turn(
                workspace_id=jd_workspace_id, turn_id=turn_id, uow_factory=factory
            )
        assert session.in_transaction()

    withdraw_turn(workspace_id=jd_workspace_id, turn_id=turn_id, uow_factory=factory)
    with sessions.begin() as session:
        assert (
            read_completed_interview_message_ids(
                session,
                workspace_id=jd_workspace_id,
                completed_turn_ids=frozenset({turn_id}),
                lock_turns=lock_turns,
            )
            == ()
        )
