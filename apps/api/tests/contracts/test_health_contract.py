"""The schema and generated DTO must reject the same invalid wire payloads."""

import json

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from caliburn.transport.http.models.consultant import HealthStatus
from tests.fixtures.http_contracts import http_schema, http_validator


def test_health_status_round_trip() -> None:
    schema = http_schema(HealthStatus)
    Draft202012Validator.check_schema(schema)
    payload = {"status": "ok"}
    Draft202012Validator(schema).validate(payload)
    assert json.loads(HealthStatus.model_validate(payload).model_dump_json()) == payload


@pytest.mark.parametrize(
    "payload", [{}, {"status": "ready"}, {"status": 1}, {"status": "ok", "secret": "unexpected"}]
)
def test_health_contract_rejects_invalid_payload(payload: dict[str, object]) -> None:
    validator = http_validator(HealthStatus)
    assert not validator.is_valid(payload)
    with pytest.raises(ValidationError):
        HealthStatus.model_validate(payload)
