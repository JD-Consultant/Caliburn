"""Public summary schema and generated DTO agree on boundaries, not provider extras."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from caliburn.contracts.generated.reasoning_summary import ReasoningSummary


def test_summary_contract_rejects_private_fields_and_invalid_part_identity():
    schema = json.loads(
        (Path(__file__).parents[2] / "contracts/http/reasoning-summary.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema)
    payload = {
        "response_id": "r",
        "item_id": "rs",
        "output_index": 0,
        "summary_index": 1,
        "text": "摘要",
    }
    validator.validate(payload)
    assert ReasoningSummary.model_validate(payload).model_dump(mode="json") == payload
    for invalid in (
        {**payload, "encrypted_content": "opaque"},
        {**payload, "content": [{"type": "reasoning_text", "text": "private"}]},
        {**payload, "summary_index": -1},
        {**payload, "output_index": "0"},
        {**payload, "text": ""},
    ):
        assert list(validator.iter_errors(invalid))
        with pytest.raises(ValidationError):
            ReasoningSummary.model_validate(invalid)
