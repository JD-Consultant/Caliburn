"""Public status admits only the defined controls, without formal or internal identities."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from caliburn.transport.http.models.consultant import ConsultantTurn
from tests.fixtures.http_contracts import http_validator


def test_consultant_status_schema_rejects_private_or_invented_state() -> None:
    validator = http_validator(ConsultantTurn)
    original = {
        "job_file_id": str(uuid4()),
        "execution_id": str(uuid4()),
        "status": "active",
        "pause_requested": False,
        "input_text": "合成原話",
        "allowed_controls": [],
        "commentary": [],
        "plan_preview": None,
        "candidate": None,
    }
    for status in ("active", "paused", "completed", "cancelled", "failed"):
        validator.validate(original | {"status": status})
    for controls in (["pause", "cancel"], ["cancel"], ["resume", "cancel"]):
        validator.validate(original | {"allowed_controls": controls})
    validator.validate(original | {"pause_requested": True})
    assert not validator.is_valid(
        {key: value for key, value in original.items() if key != "pause_requested"}
    )
    for invalid in (
        {"reasoning": "private"},
        {"interview_sequence": 2},
        {"source_id": str(uuid4())},
        {"status": "saving"},
        {"pause_requested": "true"},
        {"pause_requested": None},
        {"allowed_controls": ["retry"]},
        {"allowed_controls": ["cancel", "cancel"]},
        {
            "commentary": [
                {"response_id": "r", "message_id": "m", "text": "公開", "reasoning": "private"}
            ]
        },
        {
            "commentary": [
                {"response_id": "r", "message_id": "m", "text": "公開", "interview_sequence": 2}
            ]
        },
    ):
        assert not validator.is_valid(original | invalid)
        with pytest.raises(ValidationError):
            ConsultantTurn.model_validate(original | invalid)
