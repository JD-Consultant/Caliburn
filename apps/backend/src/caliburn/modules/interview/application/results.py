"""完整訊息與有序訪談的不可變讀取結果。"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from caliburn.modules.interview.application.errors import InterviewDataError
from caliburn.modules.interview.domain.models.interview_message import (
    InterviewMessage,
    MessageKind,
    Speaker,
)
from caliburn.modules.interview.domain.models.message_content import (
    MessageContent,
    Question,
    TextContent,
)


@dataclass(frozen=True, slots=True)
class MessageView:
    message_id: UUID
    turn_id: UUID
    position: int
    speaker: Speaker
    kind: MessageKind
    content: MessageContent
    reply_to_message_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TranscriptMessage:
    message_id: UUID
    turn_id: UUID
    speaker: Speaker
    kind: MessageKind
    text: str
    reply_to_message_id: UUID | None


def message_view(turn_id: UUID, message: InterviewMessage) -> MessageView:
    return MessageView(
        message_id=message.id,
        turn_id=turn_id,
        position=message.position,
        speaker=message.speaker,
        kind=message.kind,
        content=message.content,
        reply_to_message_id=message.reply_to_message_id,
        created_at=message.created_at,
    )


def transcript_message(
    message: MessageView, question: Question | None = None
) -> TranscriptMessage:
    """投影使用原題選項說明；不把自填、略過及未答混為一談。"""
    content = message.content
    if isinstance(content, TextContent):
        text = content.text
    elif isinstance(content, Question):
        text = content.question
    else:
        if question is None:
            raise InterviewDataError("答案缺少同輪原題")
        answer = question.validate_answer(content)
        parts = []
        if answer.selected:
            selected = set(answer.selected)
            labels = [
                f"{option.label}（{option.description}）"
                if option.description is not None
                else option.label
                for option in question.options
                if option.label in selected
            ]
            parts.append("選擇：" + "、".join(labels))
        if answer.custom is not None:
            parts.append("自填：" + answer.custom)
        text = "\n".join(parts) if parts else "略過"
    return TranscriptMessage(
        message_id=message.message_id,
        turn_id=message.turn_id,
        speaker=message.speaker,
        kind=message.kind,
        text=text,
        reply_to_message_id=message.reply_to_message_id,
    )
