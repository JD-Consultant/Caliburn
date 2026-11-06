"""問答互動與訪談保存共用的單題驗答接縫。"""

import pytest
from pydantic import ValidationError

from caliburn.modules.interview.domain.errors import InvalidAnswerError
from caliburn.modules.interview.domain.models.message_content import (
    Answer,
    Question,
    QuestionOption,
    TextContent,
)


def test_normalizes_selection_in_question_order_and_keeps_custom_exactly() -> None:
    question = Question(
        question="工作內容？",
        options=(QuestionOption(label="A"), QuestionOption(label="B")),
        multi_select=True,
    )

    answer = question.validate_answer(
        Answer(selected=("B", "A"), custom="  同時\r\n支援現場。 ")
    )

    assert answer == Answer(selected=("A", "B"), custom="  同時\r\n支援現場。 ")


@pytest.mark.parametrize("selected", [("A", "A"), ("missing",), ("A", "B")])
def test_rejects_duplicate_unknown_and_multiple_single_choice_selection(
    selected: tuple[str, ...],
) -> None:
    question = Question(
        question="主要工作？",
        options=(QuestionOption(label="A"), QuestionOption(label="B")),
    )
    with pytest.raises(InvalidAnswerError):
        question.validate_answer(Answer(selected=selected))


def test_question_rejects_duplicate_option_labels() -> None:
    with pytest.raises(ValidationError):
        Question(
            question="工作？",
            options=(QuestionOption(label="A"), QuestionOption(label="A")),
        )


@pytest.mark.parametrize("invalid", ["nul\x00text", "surrogate\ud800"])
def test_rejects_unstorable_text_in_all_content_fields(invalid: str) -> None:
    with pytest.raises(ValidationError):
        TextContent(text=invalid)
    with pytest.raises(ValidationError):
        Question(question=invalid)
    with pytest.raises(ValidationError):
        Question(question="Q", header=invalid)
    with pytest.raises(ValidationError):
        QuestionOption(label=invalid)
    with pytest.raises(ValidationError):
        QuestionOption(label="A", description=invalid)
    with pytest.raises(ValidationError):
        Answer(custom=invalid)
    with pytest.raises(ValidationError):
        Answer(selected=(invalid,))


def test_content_is_deeply_immutable_and_empty_custom_remains_distinct_from_skip() -> (
    None
):
    question = Question(question="Q", options=(QuestionOption(label="A"),))
    with pytest.raises(ValidationError):
        question.options[0].__setattr__("label", "changed")
    with pytest.raises(ValidationError):
        question.__setattr__("options", ())
    assert question.validate_answer(Answer(custom="")) == Answer(custom="")
    assert question.validate_answer(Answer(custom=" ")) == Answer(custom=" ")
    assert question.validate_answer(Answer()) != Answer(custom="")
