"""公開保存用例以提交為回傳邊界；I/O 替身只驗協調契約。"""

from uuid import uuid4

import pytest

from caliburn.modules.interview.application.errors import (
    InterviewMessageNotFoundError,
    InterviewPersistenceError,
    InterviewTurnNotFoundError,
)
from caliburn.modules.interview.application.queries import get_message, list_messages
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
from tests.unit.modules.interview.memory_store import MemoryInterviewStore


def test_failed_commit_returns_no_saved_message() -> None:
    store = MemoryInterviewStore()
    workspace_id = uuid4()
    store.fail_commit = True
    with pytest.raises(InterviewPersistenceError):
        record_turn_input(
            workspace_id=workspace_id,
            turn_id=uuid4(),
            text="尚未提交",
            uow_factory=store.uow_factory,
        )
    assert list_messages(workspace_id=workspace_id, queries=store) == ()


def test_same_turn_uuid_in_other_workspace_does_not_grant_access() -> None:
    store = MemoryInterviewStore()
    workspace_id, turn_id = uuid4(), uuid4()
    message = record_turn_input(
        workspace_id=workspace_id,
        turn_id=turn_id,
        text="原文",
        uow_factory=store.uow_factory,
    )
    other_workspace = uuid4()
    with pytest.raises(InterviewTurnNotFoundError):
        record_consultant_message(
            workspace_id=other_workspace,
            turn_id=turn_id,
            text="越界",
            uow_factory=store.uow_factory,
        )
    with pytest.raises(InterviewMessageNotFoundError):
        get_message(
            workspace_id=other_workspace, message_id=message.message_id, queries=store
        )
    assert list_messages(workspace_id=other_workspace, queries=store) == ()


def test_recorded_input_is_readable_and_reentry_keeps_same_message() -> None:
    store = MemoryInterviewStore()
    workspace_id, turn_id = uuid4(), uuid4()
    first = record_turn_input(
        workspace_id=workspace_id,
        turn_id=turn_id,
        text=" 原文 ",
        uow_factory=store.uow_factory,
    )
    repeated = record_turn_input(
        workspace_id=workspace_id,
        turn_id=turn_id,
        text=" 原文 ",
        uow_factory=store.uow_factory,
    )
    assert repeated == first
    assert (
        get_message(
            workspace_id=workspace_id, message_id=first.message_id, queries=store
        )
        == first
    )
    assert [
        message.text
        for message in list_messages(workspace_id=workspace_id, queries=store)
    ] == [" 原文 "]


def test_opening_reentry_preserves_original_message_and_turn_identity() -> None:
    store = MemoryInterviewStore()
    workspace_id = uuid4()
    first = record_opening(
        workspace_id=workspace_id, text="開場", uow_factory=store.uow_factory
    )
    repeated = record_opening(
        workspace_id=workspace_id, text="開場", uow_factory=store.uow_factory
    )
    assert repeated == first
    assert len(list_messages(workspace_id=workspace_id, queries=store)) == 1


def test_question_answer_and_final_message_keep_actual_utterance_order() -> None:
    store = MemoryInterviewStore()
    workspace_id, turn_id = uuid4(), uuid4()
    record_turn_input(
        workspace_id=workspace_id,
        turn_id=turn_id,
        text="原輸入",
        uow_factory=store.uow_factory,
    )
    questions = record_questions(
        workspace_id=workspace_id,
        turn_id=turn_id,
        questions=(Question(question="Q1"), Question(question="Q2")),
        uow_factory=store.uow_factory,
    )
    answers = record_answers(
        workspace_id=workspace_id,
        turn_id=turn_id,
        answers=(
            AnswerInput(question_message_id=questions[0].message_id, custom="我的答案"),
        ),
        uow_factory=store.uow_factory,
    )
    final = record_consultant_message(
        workspace_id=workspace_id,
        turn_id=turn_id,
        text="最終發話",
        uow_factory=store.uow_factory,
    )
    messages = list_messages(workspace_id=workspace_id, queries=store)
    assert [message.text for message in messages] == [
        "原輸入",
        "Q1",
        "Q2",
        "自填：我的答案",
        "最終發話",
    ]
    assert answers[0].reply_to_message_id == questions[0].message_id
    assert final.reply_to_message_id is None


def test_withdrawal_hides_only_target_turn_and_missing_turn_is_noop() -> None:
    store = MemoryInterviewStore()
    workspace_id, turn_id = uuid4(), uuid4()
    opening = record_opening(
        workspace_id=workspace_id, text="開場", uow_factory=store.uow_factory
    )
    message = record_turn_input(
        workspace_id=workspace_id,
        turn_id=turn_id,
        text="原文",
        uow_factory=store.uow_factory,
    )
    withdraw_turn(
        workspace_id=workspace_id, turn_id=turn_id, uow_factory=store.uow_factory
    )
    withdraw_turn(
        workspace_id=workspace_id, turn_id=turn_id, uow_factory=store.uow_factory
    )
    withdraw_turn(
        workspace_id=workspace_id, turn_id=uuid4(), uow_factory=store.uow_factory
    )
    assert [
        item.message_id
        for item in list_messages(workspace_id=workspace_id, queries=store)
    ] == [opening.message_id]
    assert (
        list_messages(workspace_id=workspace_id, turn_id=turn_id, queries=store) == ()
    )
    with pytest.raises(InterviewMessageNotFoundError):
        get_message(
            workspace_id=workspace_id, message_id=message.message_id, queries=store
        )
