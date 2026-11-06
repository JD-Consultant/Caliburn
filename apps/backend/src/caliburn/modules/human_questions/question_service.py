"""問答查讀與驗答；執行及保存確認交由 Agent 的通用准入。"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from langgraph.types import StateSnapshot

from caliburn.modules.agent.application.agent_service import AgentService
from caliburn.modules.agent.application.errors import TurnConflict
from caliburn.modules.agent.application.views import TurnSubmission
from caliburn.modules.agent.interrupts import InterruptResume, ResumePoint
from caliburn.modules.human_questions.agent_history import (
    QuestionExchange,
    question_call,
    question_exchanges,
    saved_answers,
)
from caliburn.modules.human_questions.questions import (
    AnswerBatch,
    read_pending_questions,
)


@dataclass(frozen=True)
class AnswerSubmission:
    turn_id: UUID
    model_step: int
    call_id: str
    answers: AnswerBatch

    @property
    def request_key(self) -> str:
        return json.dumps(
            [
                "human_questions",
                self.model_step,
                self.call_id,
                [
                    [
                        str(answer.question_message_id),
                        sorted(answer.selected),
                        answer.custom,
                    ]
                    for answer in sorted(
                        self.answers.answers, key=lambda item: item.question_message_id
                    )
                ],
            ],
            ensure_ascii=True,
        )

    def prepare(self, snapshot: StateSnapshot) -> InterruptResume:
        for interrupt in snapshot.interrupts:
            questions = read_pending_questions(interrupt.value)
            if questions is not None and (
                questions.model_step == self.model_step
                and questions.call_id == self.call_id
            ):
                answers = questions.validate_answers(self.answers)
                return InterruptResume(
                    point=ResumePoint(
                        checkpoint_id=snapshot.config["configurable"]["checkpoint_id"],
                        interrupt=interrupt,
                    ),
                    value=answers.model_dump(mode="json", exclude_none=True),
                )
        raise TurnConflict("指定呼叫目前沒有等待人工回答")

    def is_saved(self, snapshots: Sequence[StateSnapshot]) -> bool:
        displayed = question_call(
            snapshots, self.turn_id, self.model_step, self.call_id
        )
        if displayed is None:
            raise TurnConflict("查無指定的人工提問呼叫")
        recorded = saved_answers(displayed.call, displayed.questions)
        if recorded is None:
            return False
        if not recorded.matches(self.answers):
            raise TurnConflict("這批問題已保存不同答案")
        return True


class QuestionService:
    def __init__(self, agent: AgentService) -> None:
        self._agent = agent

    async def list_questions(
        self, *, workspace_id: UUID, turn_id: UUID
    ) -> list[QuestionExchange]:
        execution = await self._agent.read_turn_execution(
            workspace_id=workspace_id, turn_id=turn_id
        )
        return question_exchanges(execution, turn_id)

    async def pending_questions(
        self, *, workspace_id: UUID, turn_id: UUID
    ) -> list[QuestionExchange]:
        return [
            exchange
            for exchange in await self.list_questions(
                workspace_id=workspace_id, turn_id=turn_id
            )
            if exchange.status == "waiting"
        ]

    async def submit_answers(
        self,
        *,
        workspace_id: UUID,
        turn_id: UUID,
        model_step: int,
        call_id: str,
        answers: AnswerBatch,
    ) -> TurnSubmission:
        submission = AnswerSubmission(turn_id, model_step, call_id, answers)
        return await self._agent.resume_interrupt(
            workspace_id=workspace_id,
            turn_id=turn_id,
            request_key=submission.request_key,
            prepare=submission.prepare,
            is_saved=submission.is_saved,
        )
