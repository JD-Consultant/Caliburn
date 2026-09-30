"""The single SSE wire authority permits only five public fields."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from caliburn.contracts.generated.commentary_update import CommentaryUpdate


def test_public_commentary_wire_matches_generated_model_and_rejects_private_fields() -> None:
    schema = json.loads(
        (Path(__file__).parents[2] / "contracts/http/commentary-update.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = {
        "job_file_id": str(uuid4()),
        "execution_id": str(uuid4()),
        "response_id": "r",
        "message_id": "m",
        "text": "公開\n累積全文",
    }
    validator.validate(payload)
    assert CommentaryUpdate.model_validate(payload).model_dump(mode="json") == payload
    invalid_payloads = [
        {**payload, "reasoning": "private"},
        {**payload, "phase": "commentary"},
        {**payload, "tools": []},
        {**payload, "job_file_id": "bad"},
        {**payload, "text": 7},
        {key: value for key, value in payload.items() if key != "text"},
    ]
    for invalid in invalid_payloads:
        assert list(validator.iter_errors(invalid))
        with pytest.raises(ValidationError):
            CommentaryUpdate.model_validate(invalid)
