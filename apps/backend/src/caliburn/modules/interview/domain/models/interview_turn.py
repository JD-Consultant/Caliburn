"""同一 Workspace／輪次的訊息追加與撤回一致性邊界。"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal, Self
from uuid import UUID, uuid7

from pydantic import Field, model_validator

from caliburn.modules.interview.domain.errors import (
    InterviewAnswerConflictError,
    InterviewInputConflictError,
    InterviewQuestionNotFoundError,
    InterviewTurnKindError,
    InterviewTurnWithdrawnError,
    InvalidAnswerError,
)
from caliburn.modules.interview.domain.models.interview_message import (
    InterviewMessage,
)
from caliburn.modules.interview.domain.models.message_content import (
    Answer,
    AnswerInput,
    Question,
    TextContent,
)
from caliburn.shared.domain.base_aggregate_root import BaseAggregateRoot

type TurnKind = Literal["conversation", "opening"]


class InterviewTurn(BaseAggregateRoot[tuple[UUID, UUID]]):
    """建構子供持久層復水；新增訊息只經根方法取得模組產生的 UUID。"""

    kind: TurnKind = Field(frozen=True)
    created_at: datetime = Field(frozen=True)
    withdrawn_at: datetime | None = Field(default=None, frozen=True)
    messages: tuple[InterviewMessage, ...] = Field(default=(), frozen=True)

    @model_validator(mode="after")
    def _valid_saved_turn(self) -> Self:
        if not self.messages:
            raise ValueError("訪談輪次必須包含原始發話")
        identities: set[UUID] = set()
        questions: dict[UUID, Question] = {}
        answered: set[UUID] = set()
        for position, message in enumerate(self.messages):
            if message.position != position or message.id in identities:
                raise ValueError("訪談訊息身分或追加順序不一致")
            identities.add(message.id)
            if isinstance(message.content, Question):
                questions[message.id] = message.content
            elif isinstance(message.content, Answer):
                question_id = message.reply_to_message_id
                if question_id not in questions or question_id in answered:
                    raise ValueError("答案必須唯一對應同輪先前的原題")
                if (
                    questions[question_id].validate_answer(message.content)
                    != message.content
                ):
                    raise ValueError("答案選項必須依原題順序保存")
                answered.add(question_id)
        first = self.messages[0]
        if self.kind == "opening":
            if (
                len(self.messages) != 1
                or first.speaker != "app"
                or first.kind != "text"
                or self.withdrawn_at is not None
            ):
                raise ValueError("固定開場必須是單一有效 App 文字")
        elif (
            first.speaker != "employee"
            or first.kind != "text"
            or any(message.speaker == "app" for message in self.messages)
        ):
            raise ValueError("一般訪談必須以員工原文開始且不包含 App 開場")
        return self

    @property
    def workspace_id(self) -> UUID:
        return self.id[0]

    @property
    def turn_id(self) -> UUID:
        return self.id[1]

    @classmethod
    def create_conversation(
        cls, *, workspace_id: UUID, turn_id: UUID, text: str
    ) -> Self:
        now = datetime.now(UTC)
        message = InterviewMessage(
            id=uuid7(),
            position=0,
            speaker="employee",
            kind="text",
            content=TextContent(text=text),
            created_at=now,
        )
        return cls(
            id=(workspace_id, turn_id),
            kind="conversation",
            created_at=now,
            messages=(message,),
        )

    @classmethod
    def create_opening(cls, *, workspace_id: UUID, text: str) -> Self:
        now = datetime.now(UTC)
        message = InterviewMessage(
            id=uuid7(),
            position=0,
            speaker="app",
            kind="text",
            content=TextContent(text=text),
            created_at=now,
        )
        return cls(
            id=(workspace_id, uuid7()),
            kind="opening",
            created_at=now,
            messages=(message,),
        )

    def record_input(self, text: str) -> InterviewMessage:
        self._require_active_conversation()
        first = self.messages[0]
        if first.speaker != "employee" or first.content != TextContent(text=text):
            raise InterviewInputConflictError("原始訪談輸入不一致")
        return first

    def record_opening(self, text: str) -> InterviewMessage:
        if self.kind != "opening":
            raise InterviewTurnKindError("此輪不是固定開場")
        first = self.messages[0]
        if first.content != TextContent(text=text):
            raise InterviewInputConflictError("固定開場原文不一致")
        return first

    def record_text(
        self, speaker: Literal["employee", "consultant"], text: str
    ) -> InterviewMessage:
        self._require_active_conversation()
        if speaker not in ("employee", "consultant"):
            raise InterviewTurnKindError("一般訪談不能追加 App 開場文字")
        message = InterviewMessage(
            id=uuid7(),
            position=len(self.messages),
            speaker=speaker,
            kind="text",
            content=TextContent(text=text),
            created_at=datetime.now(UTC),
        )
        object.__setattr__(self, "messages", (*self.messages, message))
        return message

    def record_questions(
        self, questions: Sequence[Question]
    ) -> tuple[InterviewMessage, ...]:
        self._require_active_conversation()
        messages = tuple(
            InterviewMessage(
                id=uuid7(),
                position=len(self.messages) + index,
                speaker="consultant",
                kind="question",
                content=question,
                created_at=datetime.now(UTC),
            )
            for index, question in enumerate(questions)
        )
        object.__setattr__(self, "messages", (*self.messages, *messages))
        return messages

    def record_answers(
        self, answers: Sequence[AnswerInput]
    ) -> tuple[InterviewMessage, ...]:
        self._require_active_conversation()
        if len({answer.question_message_id for answer in answers}) != len(answers):
            raise InvalidAnswerError(
                "本次輸入不能重複回答同一問題", field="question_message_id"
            )
        questions = {
            message.id: message.content
            for message in self.messages
            if isinstance(message.content, Question)
        }
        for answer in answers:
            if answer.question_message_id not in questions:
                raise InterviewQuestionNotFoundError("原題不在指定訪談輪次")
        existing_answers = {
            message.reply_to_message_id: message
            for message in self.messages
            if message.kind == "answer"
        }
        validated = [
            (
                answer.question_message_id,
                questions[answer.question_message_id].validate_answer(
                    Answer(selected=answer.selected, custom=answer.custom)
                ),
            )
            for answer in answers
        ]
        for question_id, content in validated:
            existing = existing_answers.get(question_id)
            if existing is not None and existing.content != content:
                raise InterviewAnswerConflictError("原題已有不同的正式答案")
        results = []
        messages: list[InterviewMessage] = []
        for question_id, content in validated:
            existing = existing_answers.get(question_id)
            if existing is not None:
                results.append(existing)
                continue
            message = InterviewMessage(
                id=uuid7(),
                position=len(self.messages) + len(messages),
                speaker="employee",
                kind="answer",
                content=content,
                reply_to_message_id=question_id,
                created_at=datetime.now(UTC),
            )
            results.append(message)
            messages.append(message)
        object.__setattr__(self, "messages", (*self.messages, *messages))
        return tuple(results)

    def withdraw(self) -> bool:
        self._require_conversation()
        if self.withdrawn_at is not None:
            return False
        object.__setattr__(self, "withdrawn_at", datetime.now(UTC))
        return True

    def _require_active_conversation(self) -> None:
        self._require_conversation()
        if self.withdrawn_at is not None:
            raise InterviewTurnWithdrawnError("已撤回輪次不得追加")

    def _require_conversation(self) -> None:
        if self.kind != "conversation":
            raise InterviewTurnKindError("一般訪談不能操作固定開場")
