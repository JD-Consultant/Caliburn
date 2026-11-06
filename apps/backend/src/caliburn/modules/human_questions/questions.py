"""已展示問題、完整回答集合與同答比較；單題規則沿訪談 Domain。"""

import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from caliburn.modules.interview.domain.errors import InvalidAnswerError
from caliburn.modules.interview.domain.models.message_content import (
    Answer,
    AnswerInput,
    InterviewText,
    Question,
)


class QuestionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    questions: list[Question] = Field(min_length=1)


class SavedQuestion(Question):
    """訪談模組已保存並交付給使用者的題目。"""

    message_id: UUID
    question_ref: str


class AnswerBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    answers: list[AnswerInput]

    def matches(self, other: AnswerBatch) -> bool:
        """比較已保存答案；題目和選項順序不構成異答。"""
        by_id = {answer.question_message_id: answer for answer in self.answers}
        other_by_id = {answer.question_message_id: answer for answer in other.answers}
        if (
            len(by_id) != len(self.answers)
            or len(other_by_id) != len(other.answers)
            or by_id.keys() != other_by_id.keys()
        ):
            return False
        for question_id, answer in by_id.items():
            other_answer = other_by_id[question_id]
            selected = set(answer.selected)
            other_selected = set(other_answer.selected)
            if (
                len(selected) != len(answer.selected)
                or len(other_selected) != len(other_answer.selected)
                or selected != other_selected
                or answer.custom != other_answer.custom
            ):
                return False
        return True


class AnsweredQuestion(Answer):
    """模型結果使用持久訊息短碼，正式題答身分仍由訪談模組保存。"""

    question: InterviewText
    question_ref: str
    answer_ref: str


class QuestionToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    answers: list[AnsweredQuestion]


class InvalidAnswers(ValueError):
    """回答不符合已展示問題；訊息不包含使用者輸入。"""

    def __init__(
        self, message: str, location: tuple[str | int, ...] = ("answers",)
    ) -> None:
        super().__init__(message)
        self.location = location


class PendingQuestions(BaseModel):
    """已展示問題及其所屬步驟、呼叫定位。"""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    type: Literal["user_questions"] = "user_questions"
    questions: list[SavedQuestion] = Field(min_length=1)
    model_step: int = Field(ge=1, le=9007199254740991)
    call_id: str = Field(min_length=1)

    def validate_answers(self, answers: AnswerBatch) -> AnswerBatch:
        """核對完整回答集合，依原題順序呼叫唯一單題驗答規則。"""
        by_id = {
            answer.question_message_id: (index, answer)
            for index, answer in enumerate(answers.answers)
        }
        if len(by_id) != len(answers.answers) or by_id.keys() != {
            question.message_id for question in self.questions
        }:
            raise InvalidAnswers("每題必須對應一筆答案")
        normalized = []
        for question in self.questions:
            index, answer = by_id[question.message_id]
            try:
                validated = question.validate_answer(answer)
            except InvalidAnswerError as error:
                raise InvalidAnswers(
                    str(error), ("answers", index, error.field)
                ) from error
            normalized.append(
                AnswerInput(
                    question_message_id=question.message_id,
                    selected=validated.selected,
                    custom=validated.custom,
                )
            )
        return AnswerBatch(answers=normalized)


def read_pending_questions(value: object) -> PendingQuestions | None:
    """只解讀提問資料；其他種類的值不屬於本能力。"""
    if not isinstance(value, dict) or value.get("type") != "user_questions":
        return None
    return PendingQuestions.model_validate_json(json.dumps(value))
