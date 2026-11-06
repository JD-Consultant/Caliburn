"""供 Context 編排直接呼叫的來源選取與投影公開函式。"""

import json
from dataclasses import replace
from uuid import UUID

import pytest

from caliburn.bundles.interview.context import (
    InterviewContextSelectionError,
    insert_interview_context,
    project_interview_context,
    select_interview_context,
)
from caliburn.modules.interview.application.results import TranscriptMessage


def transcript_message(number: int, *, turn: int = 10) -> TranscriptMessage:
    return TranscriptMessage(
        message_id=UUID(int=number),
        turn_id=UUID(int=turn),
        speaker="employee",
        kind="text",
        text=f"原話 {number}",
        reply_to_message_id=None,
    )


@pytest.mark.parametrize("message_ids, expected", [((), []), ((3, 1), [1, 3])])
def test_explicit_selection_uses_transcript_order_and_empty_means_no_preload(
    message_ids: tuple[int, ...], expected: list[int]
) -> None:
    transcript = tuple(transcript_message(number) for number in (1, 2, 3))

    selected = select_interview_context(
        transcript,
        turn_id=UUID(int=20),
        message_ids=tuple(UUID(int=number) for number in message_ids),
    )

    assert [source.message.message_id.int for source in selected] == expected


@pytest.mark.parametrize(
    "message_id, reason", [(1, "current_turn"), (9, "unavailable")]
)
def test_explicit_current_or_missing_source_is_rejected(
    message_id: int, reason: str
) -> None:
    with pytest.raises(ValueError, match=reason):
        select_interview_context(
            (transcript_message(1, turn=20),),
            turn_id=UUID(int=20),
            message_ids=(UUID(int=message_id),),
        )


def test_selected_answer_brings_its_question_as_support_without_changing_text() -> None:
    question = replace(
        transcript_message(9),
        speaker="consultant",
        kind="question",
        text="原題？\n請補充",
    )
    answer = replace(
        transcript_message(1),
        kind="answer",
        text="自填： 答覆原文 ",
        reply_to_message_id=question.message_id,
    )

    selected = select_interview_context(
        (transcript_message(3), question, answer),
        turn_id=UUID(int=20),
        message_ids=(answer.message_id,),
    )

    assert [(source.message, source.supporting_question) for source in selected] == [
        (question, True),
        (answer, False),
    ]
    (projected,) = project_interview_context(
        selected,
        refs={question.message_id: "message_41", answer.message_id: "message_7"},
    )
    assert isinstance(projected, dict)
    content = projected.get("content")
    assert isinstance(content, str)
    material = json.loads(content)
    assert material["messages"] == [
        {
            "ref": "message_41",
            "speaker": "consultant",
            "kind": "question",
            "text": "原題？\n請補充",
            "reply_to": None,
            "supporting_question": True,
        },
        {
            "ref": "message_7",
            "speaker": "employee",
            "kind": "answer",
            "text": "自填： 答覆原文 ",
            "reply_to": "message_41",
            "supporting_question": False,
        },
    ]


@pytest.mark.parametrize(
    "question_turn, reason", [(None, "missing_question"), (20, "current_turn")]
)
def test_required_question_cannot_be_missing_or_reintroduce_current_turn(
    question_turn: int | None, reason: str
) -> None:
    answer = replace(
        transcript_message(1), kind="answer", reply_to_message_id=UUID(int=9)
    )
    transcript: tuple[TranscriptMessage, ...] = (answer,)
    if question_turn is not None:
        question = replace(
            transcript_message(9, turn=question_turn),
            speaker="consultant",
            kind="question",
        )
        transcript = (question, answer)

    with pytest.raises(InterviewContextSelectionError) as caught:
        select_interview_context(
            transcript, turn_id=UUID(int=20), message_ids=(answer.message_id,)
        )

    assert caught.value.reason == reason
    assert caught.value.message_id == UUID(int=9)


@pytest.mark.parametrize("position", [-1, 2])
def test_insertion_rejects_position_outside_current_input(position: int) -> None:
    with pytest.raises(ValueError):
        insert_interview_context(
            [{"role": "user", "content": "本輪原文"}], [], position=position
        )
