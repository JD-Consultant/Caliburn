"""JSONB 依正式內容型別解碼；原文不在儲存邊界清洗。"""

import json

from caliburn.modules.interview.application.errors import InterviewDataError
from caliburn.modules.interview.domain.models.interview_message import InterviewMessage
from caliburn.modules.interview.domain.models.message_content import (
    Answer,
    MessageContent,
    Question,
    TextContent,
)
from caliburn.modules.interview.infrastructure.persistence.orm_models import (
    InterviewMessageRow,
)


def load_message(row: InterviewMessageRow) -> InterviewMessage:
    try:
        raw = json.dumps(row.content, ensure_ascii=False)
        content: MessageContent
        match row.kind:
            case "text":
                content = TextContent.model_validate_json(raw)
            case "question":
                content = Question.model_validate_json(raw)
            case "answer":
                content = Answer.model_validate_json(raw)
            case _:
                raise ValueError("Unknown interview message kind")
        return InterviewMessage.model_validate(
            {
                "id": row.id,
                "position": row.position,
                "speaker": row.speaker,
                "kind": row.kind,
                "content": content,
                "reply_to_message_id": row.reply_to_message_id,
                "created_at": row.created_at,
            }
        )
    except (ValueError, TypeError) as error:
        raise InterviewDataError("訪談訊息無法依正式內容格式重建") from error
