"""從公開執行原件投影實際展示的問題與已保存答案。"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from langgraph.types import StateSnapshot
from pydantic import BaseModel, ValidationError

from caliburn.modules.agent.application.errors import TurnConflict
from caliburn.modules.agent.application.turn_history import TurnExecution, step_views
from caliburn.modules.agent.application.views import ToolCallView
from caliburn.modules.human_questions.questions import (
    AnswerBatch,
    QuestionToolResult,
    SavedQuestion,
    read_pending_questions,
)
from caliburn.modules.interview.domain.models.message_content import AnswerInput


class QuestionExchange(BaseModel):
    model_step: int
    call_id: str
    questions: list[SavedQuestion]
    answers: list[AnswerInput] | None
    status: Literal["waiting", "answered", "unanswered"]


@dataclass(frozen=True)
class DisplayedQuestionCall:
    call: ToolCallView
    questions: list[SavedQuestion]


def question_call(
    snapshots: Sequence[StateSnapshot], turn_id: UUID, model_step: int, call_id: str
) -> DisplayedQuestionCall | None:
    for step in step_views(list(snapshots), turn_id):
        if step.model_step != model_step:
            continue
        for call in step.tool_calls:
            if call.call_id != call_id or call.name != "ask_user_question":
                continue
            for recorded_interrupt in step.interrupts:
                pending = read_pending_questions(recorded_interrupt.value)
                if pending is not None and pending.call_id == call_id:
                    return DisplayedQuestionCall(call, pending.questions)
    return None


def saved_answers(
    call: ToolCallView, questions: Sequence[SavedQuestion]
) -> AnswerBatch | None:
    if call.output is None:
        return None
    try:
        result = QuestionToolResult.model_validate_json(call.output)
        by_ref = {question.question_ref: question.message_id for question in questions}
        if (
            len(result.answers) != len(by_ref)
            or {answer.question_ref for answer in result.answers} != by_ref.keys()
        ):
            raise TurnConflict("這次工具結果未對應完整的實際展示問題")
        return AnswerBatch(
            answers=[
                AnswerInput(
                    question_message_id=by_ref[answer.question_ref],
                    selected=answer.selected,
                    custom=answer.custom,
                )
                for answer in result.answers
            ]
        )
    except ValidationError as error:
        raise TurnConflict("這次工具呼叫已結束，沒有可回答的問題") from error


def question_exchanges(
    execution: TurnExecution, turn_id: UUID
) -> list[QuestionExchange]:
    snapshots = [execution.current, *execution.history]
    waiting: set[tuple[int, str]] = set()
    if execution.current.values.get("turn_id") == turn_id:
        for interrupt in execution.current.interrupts:
            pending = read_pending_questions(interrupt.value)
            if pending is not None and execution.can_resume_interrupt(interrupt):
                waiting.add((pending.model_step, pending.call_id))

    exchanges = []
    for step in step_views(snapshots, turn_id):
        displayed = {}
        for recorded_interrupt in step.interrupts:
            pending = read_pending_questions(recorded_interrupt.value)
            if pending is not None:
                displayed[pending.call_id] = pending.questions
        for call in step.tool_calls:
            if call.name != "ask_user_question" or call.call_id not in displayed:
                continue
            try:
                answers = saved_answers(call, displayed[call.call_id])
            except TurnConflict:
                answers = None
            exchanges.append(
                QuestionExchange(
                    model_step=step.model_step,
                    call_id=call.call_id,
                    questions=displayed[call.call_id],
                    answers=answers.answers if answers is not None else None,
                    status=(
                        "answered"
                        if answers is not None
                        else "waiting"
                        if (step.model_step, call.call_id) in waiting
                        else "unanswered"
                    ),
                )
            )
    return exchanges
