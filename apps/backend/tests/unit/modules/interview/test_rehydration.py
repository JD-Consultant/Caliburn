"""保存原件復水時維持訊息的種類、角色及答題關係。"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from caliburn.modules.interview.domain.models.interview_message import InterviewMessage
from caliburn.modules.interview.domain.models.interview_turn import InterviewTurn
from caliburn.modules.interview.domain.models.message_content import (
    Answer,
    Question,
    TextContent,
)


@pytest.mark.parametrize(
    "overrides",
    [
        {"kind": "question", "speaker": "employee", "content": Question(question="Q")},
        {"kind": "question", "content": TextContent(text="文字")},
        {"kind": "text", "reply_to_message_id": uuid4()},
        {"kind": "answer", "speaker": "employee", "content": Answer()},
        {
            "kind": "answer",
            "speaker": "consultant",
            "content": Answer(),
            "reply_to_message_id": uuid4(),
        },
    ],
)
def test_rejects_inconsistent_message_kind_speaker_content_and_reply(
    overrides: dict[str, object],
) -> None:
    values = {
        "id": uuid4(),
        "position": 0,
        "speaker": "consultant",
        "kind": "text",
        "content": TextContent(text="原文"),
        "created_at": datetime.now(UTC),
    }
    with pytest.raises(ValidationError):
        InterviewMessage.model_validate(values | overrides)


def test_rehydrated_turn_rejects_duplicate_identity_and_foreign_question() -> None:
    turn = InterviewTurn.create_conversation(
        workspace_id=uuid4(), turn_id=uuid4(), text="原文"
    )
    first = turn.messages[0]
    duplicate = InterviewMessage(
        id=first.id,
        position=1,
        speaker="consultant",
        kind="text",
        content=TextContent(text="第二則"),
        created_at=datetime.now(UTC),
    )
    foreign_answer = InterviewMessage(
        id=uuid4(),
        position=1,
        speaker="employee",
        kind="answer",
        content=Answer(),
        reply_to_message_id=uuid4(),
        created_at=datetime.now(UTC),
    )
    for messages in ((first, duplicate), (first, foreign_answer), ()):
        with pytest.raises(ValidationError):
            InterviewTurn(
                id=turn.id,
                kind="conversation",
                created_at=turn.created_at,
                messages=messages,
            )
