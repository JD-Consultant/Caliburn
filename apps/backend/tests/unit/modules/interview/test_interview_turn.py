"""從聚合公開行為驗證原文、穩定身分及失敗原子性。"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from caliburn.modules.interview.domain.errors import (
    InterviewAnswerConflictError,
    InterviewInputConflictError,
    InterviewQuestionNotFoundError,
    InterviewTurnKindError,
    InterviewTurnWithdrawnError,
    InvalidAnswerError,
)
from caliburn.modules.interview.domain.models.interview_turn import InterviewTurn
from caliburn.modules.interview.domain.models.message_content import (
    Answer,
    AnswerInput,
    Question,
    QuestionOption,
    TextContent,
)


def test_records_original_text_and_distinct_identity_for_repeated_utterance() -> None:
    original = "  我的工作\r\n包含排程。  "
    turn = InterviewTurn.create_conversation(
        workspace_id=uuid4(), turn_id=uuid4(), text=original
    )
    second = turn.record_text("consultant", original)

    assert [message.content for message in turn.messages] == [
        TextContent(text=original),
        TextContent(text=original),
    ]
    assert [message.position for message in turn.messages] == [0, 1]
    assert turn.messages[0].id != second.id


def test_records_each_question_and_partial_answers_as_separate_messages() -> None:
    turn = InterviewTurn.create_conversation(
        workspace_id=uuid4(), turn_id=uuid4(), text="員工原文"
    )
    questions = turn.record_questions(
        (Question(question="Q1"), Question(question="Q2"))
    )
    answers = turn.record_answers((AnswerInput(question_message_id=questions[1].id),))

    assert [message.position for message in turn.messages] == [0, 1, 2, 3]
    assert len({message.id for message in turn.messages}) == 4
    assert answers[0].reply_to_message_id == questions[1].id
    assert answers[0].content == Answer(selected=(), custom=None)
    assert [message.kind for message in turn.messages] == [
        "text",
        "question",
        "question",
        "answer",
    ]


def test_last_answer_outside_turn_rejects_whole_call_without_mutation() -> None:
    turn = InterviewTurn.create_conversation(
        workspace_id=uuid4(), turn_id=uuid4(), text="原文"
    )
    question = turn.record_questions((Question(question="Q1"),))[0]
    before = turn.messages
    with pytest.raises(InterviewQuestionNotFoundError):
        turn.record_answers(
            (
                AnswerInput(question_message_id=question.id, custom="合法答案"),
                AnswerInput(question_message_id=uuid4(), custom="其他輪的答案"),
            )
        )
    assert turn.messages == before


def test_last_invalid_question_or_answer_leaves_aggregate_unchanged() -> None:
    turn = InterviewTurn.create_conversation(
        workspace_id=uuid4(), turn_id=uuid4(), text="原文"
    )
    before = turn.messages
    with pytest.raises(ValidationError):
        turn.record_questions(
            (Question(question="有效題目"), TextContent(text="不是題目"))  # type: ignore[arg-type]  # 驗 runtime 錯誤輸入。
        )
    assert turn.messages == before
    first, second = turn.record_questions(
        (
            Question(question="Q1"),
            Question(question="Q2", options=(QuestionOption(label="A"),)),
        )
    )
    before = turn.messages
    with pytest.raises(InvalidAnswerError):
        turn.record_answers(
            (
                AnswerInput(question_message_id=first.id, custom="有效答案"),
                AnswerInput(question_message_id=second.id, selected=("不存在",)),
            )
        )
    assert turn.messages == before


def test_mixed_repeated_and_new_answers_keep_input_order_and_append_positions() -> None:
    turn = InterviewTurn.create_conversation(
        workspace_id=uuid4(), turn_id=uuid4(), text="原文"
    )
    first, second, third = turn.record_questions(
        tuple(Question(question=f"Q{i}") for i in range(3))
    )
    original = turn.record_answers((AnswerInput(question_message_id=second.id),))[0]
    answers = turn.record_answers(
        (
            AnswerInput(question_message_id=first.id, custom="第一題"),
            AnswerInput(question_message_id=second.id),
            AnswerInput(question_message_id=third.id, custom="第三題"),
        )
    )
    assert [answer.position for answer in answers] == [5, 4, 6]
    assert answers[1].id == original.id
    assert [message.position for message in turn.messages] == list(range(7))


def test_conversation_cannot_append_app_text() -> None:
    turn = InterviewTurn.create_conversation(
        workspace_id=uuid4(), turn_id=uuid4(), text="原文"
    )
    before = turn.messages
    with pytest.raises(InterviewTurnKindError):
        turn.record_text("app", "假冒開場")  # type: ignore[arg-type]  # 驗證 runtime 邊界。
    assert turn.messages == before


def test_initial_input_reentry_preserves_identity_and_rejects_changed_text() -> None:
    turn = InterviewTurn.create_conversation(
        workspace_id=uuid4(), turn_id=uuid4(), text="  原文  "
    )
    first = turn.messages[0]
    assert turn.record_input("  原文  ").id == first.id
    with pytest.raises(InterviewInputConflictError):
        turn.record_input("原文")
    assert turn.messages == (first,)


def test_same_answer_reuses_identity_and_changed_answer_rejects_whole_call() -> None:
    turn = InterviewTurn.create_conversation(
        workspace_id=uuid4(), turn_id=uuid4(), text="原文"
    )
    first, second = turn.record_questions(
        (Question(question="Q1"), Question(question="Q2"))
    )
    original = turn.record_answers(
        (AnswerInput(question_message_id=first.id, custom="A"),)
    )[0]
    repeated = turn.record_answers(
        (AnswerInput(question_message_id=first.id, custom="A"),)
    )[0]
    assert repeated.id == original.id
    assert repeated.position == original.position
    before = turn.messages
    with pytest.raises(InterviewAnswerConflictError):
        turn.record_answers(
            (
                AnswerInput(question_message_id=second.id, custom="合法答案"),
                AnswerInput(question_message_id=first.id, custom="不同答案"),
            )
        )
    assert turn.messages == before


def test_duplicate_question_in_one_answer_call_is_rejected_without_mutation() -> None:
    turn = InterviewTurn.create_conversation(
        workspace_id=uuid4(), turn_id=uuid4(), text="原文"
    )
    question = turn.record_questions((Question(question="Q1"),))[0]
    answer = AnswerInput(question_message_id=question.id)
    before = turn.messages
    with pytest.raises(InvalidAnswerError):
        turn.record_answers((answer, answer))
    assert turn.messages == before


def test_opening_is_stable_and_protected_from_conversation_writes_and_withdrawal() -> (
    None
):
    turn = InterviewTurn.create_opening(workspace_id=uuid4(), text=" 開場 ")
    opening = turn.record_opening(" 開場 ")
    assert opening.speaker == "app"
    assert opening.content == TextContent(text=" 開場 ")
    with pytest.raises(InterviewInputConflictError):
        turn.record_opening("另一開場")
    with pytest.raises(InterviewTurnKindError):
        turn.record_text("consultant", "一般對話")
    with pytest.raises(InterviewTurnKindError):
        turn.record_questions((Question(question="問題"),))
    with pytest.raises(InterviewTurnKindError):
        turn.record_answers(())
    with pytest.raises(InterviewTurnKindError):
        turn.record_input("員工輸入")
    with pytest.raises(InterviewTurnKindError):
        turn.withdraw()
    assert turn.messages == (opening,)


def test_withdrawal_is_idempotent_and_rejects_all_late_appends() -> None:
    turn = InterviewTurn.create_conversation(
        workspace_id=uuid4(), turn_id=uuid4(), text="原文"
    )
    question = turn.record_questions((Question(question="Q1"),))[0]
    before = turn.messages
    assert turn.withdraw() is True
    withdrawn_at = turn.withdrawn_at
    assert withdrawn_at is not None
    assert turn.withdraw() is False
    assert turn.withdrawn_at == withdrawn_at
    with pytest.raises(InterviewTurnWithdrawnError):
        turn.record_input("原文")
    with pytest.raises(InterviewTurnWithdrawnError):
        turn.record_text("consultant", "遲到顧問文字")
    with pytest.raises(InterviewTurnWithdrawnError):
        turn.record_questions((Question(question="遲到問題"),))
    with pytest.raises(InterviewTurnWithdrawnError):
        turn.record_answers((AnswerInput(question_message_id=question.id),))
    assert turn.messages == before
