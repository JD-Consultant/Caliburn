"""訪談儲存公開契約以獨立交易重新讀取，保留原文與訊息身分。"""

from functools import partial
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text

from caliburn.modules.interview.application.errors import (
    InterviewMessageNotFoundError,
    WorkspaceNotFoundError,
)
from caliburn.modules.interview.application.recording import (
    record_answers,
    record_consultant_message,
    record_opening,
    record_questions,
    record_turn_input,
)
from caliburn.modules.interview.application.results import message_view
from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.domain.errors import (
    InterviewQuestionNotFoundError,
    InvalidAnswerError,
)
from caliburn.modules.interview.domain.models.interview_turn import InterviewTurn
from caliburn.modules.interview.domain.models.message_content import (
    AnswerInput,
    Question,
    QuestionOption,
)
from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)
from caliburn.modules.interview.infrastructure.persistence.repository import (
    SqlAlchemyInterviewRepository,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def test_existing_turn_is_locked_and_reloaded_with_its_original_message(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    turn_id = uuid4()
    first = InterviewTurn.create_conversation(
        workspace_id=jd_workspace_id, turn_id=turn_id, text="  客戶\n諮詢  "
    )
    with sessions.begin() as session:
        saved = SqlAlchemyInterviewRepository(session).get_or_create_for_update(first)
    retry = InterviewTurn.create_conversation(
        workspace_id=jd_workspace_id, turn_id=turn_id, text="  客戶\n諮詢  "
    )
    with sessions.begin() as session:
        loaded = SqlAlchemyInterviewRepository(session).get_or_create_for_update(retry)
    assert loaded.messages == saved.messages
    assert loaded.messages[0].model_dump() == first.messages[0].model_dump()
    assert loaded.messages[0].id != retry.messages[0].id


def test_saved_original_text_can_be_read_without_agent_or_write_transaction(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    turn = InterviewTurn.create_conversation(
        workspace_id=jd_workspace_id, turn_id=uuid4(), text="  單純原文\n  "
    )
    with create_session_factory(pg_engine).begin() as session:
        SqlAlchemyInterviewRepository(session).get_or_create_for_update(turn)
    assert SqlAlchemyInterviewQueries(pg_engine).get_message(
        workspace_id=jd_workspace_id, message_id=turn.messages[0].id
    ) == message_view(turn.turn_id, turn.messages[0])


def test_empty_interview_is_distinct_from_missing_workspace(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    queries = SqlAlchemyInterviewQueries(pg_engine)
    assert queries.list_messages(workspace_id=jd_workspace_id) == ()
    with pytest.raises(WorkspaceNotFoundError):
        queries.list_messages(workspace_id=uuid4())


def test_unit_of_work_requires_explicit_commit_and_rolls_back_otherwise(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    discarded = InterviewTurn.create_conversation(
        workspace_id=jd_workspace_id, turn_id=uuid4(), text="未提交"
    )
    with SqlAlchemyInterviewUnitOfWork(sessions) as uow:
        uow.turns.get_or_create_for_update(discarded)
    queries = SqlAlchemyInterviewQueries(pg_engine)
    with pytest.raises(InterviewMessageNotFoundError):
        queries.get_message(
            workspace_id=jd_workspace_id, message_id=discarded.messages[0].id
        )
    saved = InterviewTurn.create_conversation(
        workspace_id=jd_workspace_id, turn_id=uuid4(), text="明示提交"
    )
    with SqlAlchemyInterviewUnitOfWork(sessions) as uow:
        uow.turns.get_or_create_for_update(saved)
        uow.commit()
    assert queries.get_message(
        workspace_id=jd_workspace_id, message_id=saved.messages[0].id
    ) == message_view(saved.turn_id, saved.messages[0])


def test_public_recording_preserves_dialogue_order_and_withdrawal_visibility(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))
    opening = record_opening(
        workspace_id=jd_workspace_id, text="開場", uow_factory=factory
    )
    turn_id = uuid4()
    employee = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="  員工原文\n ",
        uow_factory=factory,
    )
    questions = record_questions(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        questions=(
            Question(
                question="處理哪些工作？",
                options=(QuestionOption(label="客訴", description="聯絡並追蹤"),),
            ),
            Question(question="頻率？"),
            Question(question="留待補充？"),
        ),
        uow_factory=factory,
    )
    inputs = (
        AnswerInput(
            question_message_id=questions[0].message_id,
            selected=("客訴",),
            custom="  其他\n原話  ",
        ),
        AnswerInput(question_message_id=questions[1].message_id),
    )
    answers = record_answers(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        answers=inputs,
        uow_factory=factory,
    )
    assert (
        record_answers(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            answers=inputs,
            uow_factory=factory,
        )
        == answers
    )
    final = record_consultant_message(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="完整收尾",
        uow_factory=factory,
    )
    following = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=uuid4(),
        text="下一輪",
        uow_factory=factory,
    )
    queries = SqlAlchemyInterviewQueries(pg_engine)
    transcript = queries.list_messages(workspace_id=jd_workspace_id)
    assert [message.message_id for message in transcript] == [
        opening.message_id,
        employee.message_id,
        *(question.message_id for question in questions),
        *(answer.message_id for answer in answers),
        final.message_id,
        following.message_id,
    ]
    assert [message.text for message in transcript] == [
        "開場",
        "  員工原文\n ",
        "處理哪些工作？",
        "頻率？",
        "留待補充？",
        "選擇：客訴（聯絡並追蹤）\n自填：  其他\n原話  ",
        "略過",
        "完整收尾",
        "下一輪",
    ]
    assert (
        len(queries.list_messages(workspace_id=jd_workspace_id, turn_id=turn_id)) == 7
    )
    assert (
        queries.get_message(
            workspace_id=jd_workspace_id, message_id=questions[0].message_id
        )
        == questions[0]
    )
    withdraw_turn(workspace_id=jd_workspace_id, turn_id=turn_id, uow_factory=factory)
    withdraw_turn(workspace_id=jd_workspace_id, turn_id=turn_id, uow_factory=factory)
    assert [
        message.message_id
        for message in queries.list_messages(workspace_id=jd_workspace_id)
    ] == [opening.message_id, following.message_id]
    with pytest.raises(InterviewMessageNotFoundError):
        queries.get_message(
            workspace_id=jd_workspace_id, message_id=employee.message_id
        )


def test_invalid_last_answer_leaves_no_partial_rows_and_scope_cannot_be_crossed(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyInterviewUnitOfWork, sessions)
    turn_id = uuid4()
    record_turn_input(
        workspace_id=jd_workspace_id, turn_id=turn_id, text="開始", uow_factory=factory
    )
    questions = record_questions(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        questions=(Question(question="第一題"), Question(question="第二題")),
        uow_factory=factory,
    )
    queries = SqlAlchemyInterviewQueries(pg_engine)
    before = queries.list_messages(workspace_id=jd_workspace_id)
    with pytest.raises(InvalidAnswerError):
        record_answers(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            answers=(
                AnswerInput(question_message_id=questions[0].message_id, custom="合法"),
                AnswerInput(
                    question_message_id=questions[1].message_id, selected=("不存在",)
                ),
            ),
            uow_factory=factory,
        )
    assert queries.list_messages(workspace_id=jd_workspace_id) == before
    other = WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions)).create(
        interviewee_name="另一份合成訪談"
    )
    for workspace_id, other_turn in (
        (other.workspace_id, turn_id),
        (jd_workspace_id, uuid4()),
    ):
        record_turn_input(
            workspace_id=workspace_id,
            turn_id=other_turn,
            text="另一輪",
            uow_factory=factory,
        )
        with pytest.raises(InterviewQuestionNotFoundError):
            record_answers(
                workspace_id=workspace_id,
                turn_id=other_turn,
                answers=(AnswerInput(question_message_id=questions[0].message_id),),
                uow_factory=factory,
            )
    with pytest.raises(InterviewMessageNotFoundError):
        queries.get_message(
            workspace_id=other.workspace_id, message_id=questions[0].message_id
        )


def test_workspace_deletion_cascades_interview_and_preserves_other_workspace(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyInterviewUnitOfWork, sessions)
    workspaces = WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions))
    other = workspaces.create(interviewee_name="保留的合成訪談")
    turn_id = uuid4()
    for workspace_id in (jd_workspace_id, other.workspace_id):
        record_opening(workspace_id=workspace_id, text="開場", uow_factory=factory)
        record_turn_input(
            workspace_id=workspace_id, turn_id=turn_id, text="原文", uow_factory=factory
        )
        (question,) = record_questions(
            workspace_id=workspace_id,
            turn_id=turn_id,
            questions=(Question(question="問題"),),
            uow_factory=factory,
        )
        record_answers(
            workspace_id=workspace_id,
            turn_id=turn_id,
            answers=(AnswerInput(question_message_id=question.message_id),),
            uow_factory=factory,
        )
    queries = SqlAlchemyInterviewQueries(pg_engine)
    retained = queries.list_messages(workspace_id=other.workspace_id)
    workspaces.delete(workspace_id=jd_workspace_id)
    assert queries.list_messages(workspace_id=other.workspace_id) == retained
    with pytest.raises(WorkspaceNotFoundError):
        queries.list_messages(workspace_id=jd_workspace_id)
    with pg_engine.connect() as connection:
        for table in ("interview_turns", "interview_messages"):
            assert (
                connection.scalar(
                    text(f"SELECT count(*) FROM {table} WHERE workspace_id=:id"),
                    {"id": jd_workspace_id},
                )
                == 0
            )
