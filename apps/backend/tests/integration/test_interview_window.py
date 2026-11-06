"""換窗只讀涵蓋界線之後的有效原話，撤回不會移動原保存座標。"""

from functools import partial
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine

from caliburn.modules.interview.application.errors import (
    InterviewMessageNotFoundError,
    WorkspaceNotFoundError,
)
from caliburn.modules.interview.application.recording import (
    record_answers,
    record_consultant_message,
    record_questions,
    record_turn_input,
)
from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.domain.models.message_content import (
    AnswerInput,
    Question,
    QuestionOption,
)
from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def test_withdrawn_anchor_keeps_strict_lower_bound_and_original_order(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))
    before, covered, after = uuid4(), uuid4(), uuid4()
    record_turn_input(
        workspace_id=jd_workspace_id, turn_id=before, text="已涵蓋", uow_factory=factory
    )
    anchor = record_turn_input(
        workspace_id=jd_workspace_id, turn_id=covered, text="界線", uow_factory=factory
    )
    first = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=after,
        text="  未涵蓋原文\n ",
        uow_factory=factory,
    )
    last = record_consultant_message(
        workspace_id=jd_workspace_id,
        turn_id=after,
        text="接續回覆",
        uow_factory=factory,
    )
    withdraw_turn(workspace_id=jd_workspace_id, turn_id=covered, uow_factory=factory)
    queries = SqlAlchemyInterviewQueries(pg_engine)
    result = queries.list_messages(
        workspace_id=jd_workspace_id, after_message_id=anchor.message_id
    )
    assert [message.message_id for message in result] == [
        first.message_id,
        last.message_id,
    ]
    assert [message.text for message in result] == ["  未涵蓋原文\n ", "接續回覆"]
    assert (
        queries.list_messages(
            workspace_id=jd_workspace_id, after_message_id=last.message_id
        )
        == ()
    )
    assert (
        queries.list_messages(
            workspace_id=jd_workspace_id,
            turn_id=before,
            after_message_id=anchor.message_id,
        )
        == ()
    )


def test_answer_after_boundary_keeps_original_question_projection(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))
    turn = uuid4()
    record_turn_input(
        workspace_id=jd_workspace_id, turn_id=turn, text="輸入", uow_factory=factory
    )
    (question,) = record_questions(
        workspace_id=jd_workspace_id,
        turn_id=turn,
        questions=(
            Question(
                question="工作？",
                options=(QuestionOption(label="盤點", description="逐筆核對"),),
            ),
        ),
        uow_factory=factory,
    )
    (answer,) = record_answers(
        workspace_id=jd_workspace_id,
        turn_id=turn,
        answers=(
            AnswerInput(
                question_message_id=question.message_id,
                selected=("盤點",),
                custom="  補充\n ",
            ),
        ),
        uow_factory=factory,
    )
    result = SqlAlchemyInterviewQueries(pg_engine).list_messages(
        workspace_id=jd_workspace_id,
        turn_id=turn,
        after_message_id=question.message_id,
    )
    assert len(result) == 1
    assert result[0].message_id == answer.message_id
    assert result[0].reply_to_message_id == question.message_id
    assert result[0].text == "選擇：盤點（逐筆核對）\n自填：  補充\n "


def test_window_rejects_unknown_or_foreign_anchor_and_keeps_workspace_error(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    other = WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions)).create(
        interviewee_name="另一個合成範圍"
    )
    anchor = record_turn_input(
        workspace_id=other.workspace_id,
        turn_id=uuid4(),
        text="另一份原話",
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, sessions),
    )
    queries = SqlAlchemyInterviewQueries(pg_engine)
    for message_id in (uuid4(), anchor.message_id):
        with pytest.raises(InterviewMessageNotFoundError):
            queries.list_messages(
                workspace_id=jd_workspace_id, after_message_id=message_id
            )
    with pytest.raises(WorkspaceNotFoundError):
        queries.list_messages(workspace_id=uuid4(), after_message_id=anchor.message_id)
