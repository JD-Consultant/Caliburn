"""Profile wire and generated models agree on explicit set/clear and fixed read shape."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ValidationError

from caliburn.contracts.generated.jd_profile_view import JdProfileView
from caliburn.contracts.generated.revise_jd_profile_request import ReviseJdProfileRequest

SCHEMAS = Path(__file__).parents[2] / "contracts/http"


@pytest.mark.parametrize(
    ("name", "model", "payload"),
    [
        (
            "jd-profile-view",
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
            "revise-jd-profile-request",
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
def test_profile_contract_round_trip(
    name: str, model: type[BaseModel], payload: dict[str, object]
) -> None:
    schema = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.validate(payload)
    assert model.model_validate(payload).model_dump(mode="json") == payload
    invalid = {**payload, "employee_name": "not a JD field"}
    assert not validator.is_valid(invalid)
    with pytest.raises(ValidationError):
        model.model_validate(invalid)
