"""Agent request 的 UUID 接受政策沿共用 HTTP 值型別。"""

import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.agent.presentation.api.schemas import (
    SubmitTurnRequest,
)
from caliburn.modules.human_questions.api import AnswerTurnRequest


@pytest.mark.parametrize(
    "value",
    [
        "00112233-4455-6677-8899-aabbccddeeff",
        "00112233-4455-6677-8899-AABBCCDDEEFF",
    ],
)
def test_turn_request_accepts_hyphenated_uuid_and_preserves_input(value: str) -> None:
    request = SubmitTurnRequest.model_validate_json(
        json.dumps({"turn_id": value, "input": " 合成原文\n"})
    )

    assert request.turn_id == UUID("00112233-4455-6677-8899-aabbccddeeff")
    assert request.input == " 合成原文\n"


@pytest.mark.parametrize(
    "value",
    [
        "00112233445566778899aabbccddeeff",
        "urn:uuid:00112233-4455-6677-8899-aabbccddeeff",
        "{00112233-4455-6677-8899-aabbccddeeff}",
        "00112233-4455-6677-8899-aabbccddeeff\n",
    ],
)
def test_turn_request_rejects_non_wire_uuid_spelling(value: str) -> None:
    with pytest.raises(ValidationError):
        SubmitTurnRequest.model_validate_json(
            json.dumps({"turn_id": value, "input": "合成輸入"})
        )


@pytest.mark.parametrize("value", [1, 1.0])
def test_answer_step_accepts_json_mathematical_integers(value: int | float) -> None:
    """JSON 數學整數沿公開契約接受；不是只接受 Python int。"""
    request = AnswerTurnRequest.model_validate(
        {"model_step": value, "call_id": "ask", "answers": []}
    )
    assert request.model_step == 1


@pytest.mark.parametrize("value", [True, "1", 1.5, 0, 9007199254740992])
def test_answer_step_rejects_non_integer_or_out_of_range_values(value: object) -> None:
    with pytest.raises(ValidationError):
        AnswerTurnRequest.model_validate(
            {"model_step": value, "call_id": "ask", "answers": []}
        )
