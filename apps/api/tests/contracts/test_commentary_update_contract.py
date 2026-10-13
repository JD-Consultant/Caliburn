"""The single SSE wire authority permits only five public fields."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from caliburn.transport.http.models.consultant import CommentaryUpdate
from tests.fixtures.http_contracts import http_validator


def test_public_commentary_wire_matches_generated_model_and_rejects_private_fields() -> None:
    validator = http_validator(CommentaryUpdate)
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
