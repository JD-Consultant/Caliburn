"""Profile wire and generated models agree on explicit set/clear and fixed read shape."""

from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ValidationError

from caliburn.transport.http.models.jd_profile_edits import ReviseJdProfileRequest
from caliburn.transport.http.models.jd_views import JdProfileView
from tests.fixtures.http_contracts import http_schema


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            JdProfileView,
            {
                "revision_id": str(uuid4()),
                "profile": {
                    "job_title": "前端工程師",
                    "organization_unit": None,
                    "reports_to": None,
                    "purpose": "交付及維護約定範圍的網站前端。",
                },
            },
        ),
        (
            ReviseJdProfileRequest,
            {
                "command_id": str(uuid4()),
                "expected_revision_id": str(uuid4()),
                "changes": [
                    {"action": "set_field", "field": "job_title", "value": "前端工程師"},
                    {"action": "clear_field", "field": "purpose"},
                ],
            },
        ),
    ],
)
def test_profile_contract_round_trip(model: type[BaseModel], payload: dict[str, object]) -> None:
    schema = http_schema(model)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.validate(payload)
    assert model.model_validate(payload).model_dump(mode="json") == payload
    invalid = {**payload, "employee_name": "not a JD field"}
    assert not validator.is_valid(invalid)
    with pytest.raises(ValidationError):
        model.model_validate(invalid)
