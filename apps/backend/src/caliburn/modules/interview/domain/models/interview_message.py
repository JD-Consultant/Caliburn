"""訪談內部訊息的穩定身分與不可變正文。"""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from caliburn.modules.interview.domain.models.message_content import (
    Answer,
    MessageContent,
    Question,
    TextContent,
)
from caliburn.shared.domain.base_entity import BaseEntity

type Speaker = Literal["app", "employee", "consultant"]
type MessageKind = Literal["text", "question", "answer"]


class InterviewMessage(BaseEntity[UUID]):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)
    position: int = Field(ge=0)
    speaker: Speaker
    kind: MessageKind
    content: MessageContent
    reply_to_message_id: UUID | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _consistent_content(self) -> Self:
        if self.kind == "text":
            if (
                not isinstance(self.content, TextContent)
                or self.reply_to_message_id is not None
            ):
                raise ValueError("文字訊息不能帶答題關係或其他種類正文")
        elif self.kind == "question":
            if (
                not isinstance(self.content, Question)
                or self.speaker != "consultant"
                or self.reply_to_message_id is not None
            ):
                raise ValueError("問題訊息必須是顧問題目且不帶答題關係")
        elif (
            not isinstance(self.content, Answer)
            or self.speaker != "employee"
            or self.reply_to_message_id is None
        ):
            raise ValueError("答案訊息必須是員工答案並指向原題")
        return self
