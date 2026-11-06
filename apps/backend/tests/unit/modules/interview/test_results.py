"""訪談投影保留語意與原文，不保存第二份文字。"""

from uuid import uuid4

from caliburn.modules.interview.application.results import (
    message_view,
    transcript_message,
)
from caliburn.modules.interview.domain.models.interview_turn import InterviewTurn
from caliburn.modules.interview.domain.models.message_content import (
    AnswerInput,
    Question,
    QuestionOption,
)


def test_transcript_keeps_selected_description_custom_text_and_explicit_skip() -> None:
    turn = InterviewTurn.create_conversation(
        workspace_id=uuid4(), turn_id=uuid4(), text="  原文\r\n"
    )
    question = Question(
        question="完整題幹？",
        header="分類",
        multi_select=True,
        options=(
            QuestionOption(label="A", description="獨特含義"),
            QuestionOption(label="B"),
        ),
    )
    first, second = turn.record_questions((question, Question(question="Q2")))
    selected, skipped = turn.record_answers(
        (
            AnswerInput(
                question_message_id=first.id, selected=("B", "A"), custom="  補充\r\n"
            ),
            AnswerInput(question_message_id=second.id),
        )
    )

    assert (
        transcript_message(message_view(turn.turn_id, turn.messages[0])).text
        == "  原文\r\n"
    )
    assert transcript_message(message_view(turn.turn_id, first)).text == "完整題幹？"
    assert transcript_message(message_view(turn.turn_id, selected), question).text == (
        "選擇：A（獨特含義）、B\n自填：  補充\r\n"
    )
    assert (
        transcript_message(
            message_view(turn.turn_id, skipped), Question(question="Q2")
        ).text
        == "略過"
    )
