"""原文與單題內容；互動端共用此處的選項和驗答規則。"""

from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from caliburn.modules.interview.domain.errors import InvalidAnswerError
from caliburn.shared.domain.base_value_object import BaseValueObject


def _storage_text(value: str) -> str:
    if "\x00" in value:
        raise ValueError("訪談文字不可包含 U+0000")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("訪談文字必須可編碼為 UTF-8") from error
    return value


InterviewText = Annotated[
    str,
    AfterValidator(_storage_text),
    Field(json_schema_extra={"pattern": r"^[^\u0000\uD800-\uDFFF]*$"}),
]


class TextContent(BaseValueObject):
    model_config = ConfigDict(hide_input_in_errors=True)
    text: InterviewText


class QuestionOption(BaseValueObject):
    model_config = ConfigDict(hide_input_in_errors=True)
    label: InterviewText = Field(min_length=1)
    description: InterviewText | None = None


class Answer(BaseValueObject):
    model_config = ConfigDict(hide_input_in_errors=True)
    selected: tuple[InterviewText, ...] = ()
    custom: InterviewText | None = None


class AnswerInput(Answer):
    question_message_id: UUID


class Question(BaseValueObject):
    model_config = ConfigDict(hide_input_in_errors=True)
    question: InterviewText = Field(min_length=1)
    header: InterviewText | None = None
    options: tuple[QuestionOption, ...] = ()
    multi_select: bool = False

    @field_validator("options")
    @classmethod
    def _unique_options(
        cls, options: tuple[QuestionOption, ...]
    ) -> tuple[QuestionOption, ...]:
        labels: set[str] = set()
        for index, option in enumerate(options):
            if option.label in labels:
                raise PydanticCustomError(
                    "duplicate_option_label", "duplicate option label", {"index": index}
                )
            labels.add(option.label)
        return options

    def validate_answer(self, answer: Answer) -> Answer:
        """核對單題選項並依原題順序回傳，保留自填原文。"""
        selected = set(answer.selected)
        labels = {option.label for option in self.options}
        if len(selected) != len(answer.selected) or not selected.issubset(labels):
            raise InvalidAnswerError("selected 必須來自原題的選項 label，且不可重複")
        if not self.multi_select and len(selected) > 1:
            raise InvalidAnswerError("單選題最多只能選擇一個選項")
        return Answer(
            selected=tuple(
                option.label for option in self.options if option.label in selected
            ),
            custom=answer.custom,
        )


type MessageContent = TextContent | Question | Answer
