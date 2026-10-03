"""The schema and generated DTO must reject the same invalid wire payloads."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from caliburn.contracts.generated.health_status import HealthStatus

SCHEMA_PATH = Path(__file__).parents[2] / "contracts/http/health-status.schema.json"


def test_health_status_round_trip() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    payload = {"status": "ok"}
    Draft202012Validator(schema).validate(payload)
    assert json.loads(HealthStatus.model_validate(payload).model_dump_json()) == payload


@pytest.mark.parametrize(
    "payload", [{}, {"status": "ready"}, {"status": 1}, {"status": "ok", "secret": "unexpected"}]
)
def test_health_contract_rejects_invalid_payload(payload: dict[str, object]) -> None:
    validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    assert not validator.is_valid(payload)
    with pytest.raises(ValidationError):
        HealthStatus.model_validate(payload)
