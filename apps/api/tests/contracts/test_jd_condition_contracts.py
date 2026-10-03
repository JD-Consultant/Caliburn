"""Condition contracts reject unknown kinds and preserve explicit field changes."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from caliburn.contracts.generated.edit_jd_conditions_request import EditJdConditionsRequest
from caliburn.contracts.generated.jd_conditions_view import JdConditionsView

SCHEMAS = Path(__file__).parents[2] / "contracts/http"


@pytest.mark.parametrize(
    "change",
    [
        {"action": "create_condition", "kind": "qualification", "text": "法定證照"},
        {"action": "create_condition", "kind": "shared_authority", "text": "共通決策邊界"},
        {"action": "create_condition", "kind": "shared_collaboration", "text": "跨團隊共通協調"},
        {
            "action": "revise_condition",
            "condition_id": str(uuid4()),
            "changes": [
                {"field": "text", "value": "依排班到現場"},
                {"field": "kind", "value": "schedule_travel"},
            ],
        },
        {"action": "delete_condition", "condition_id": str(uuid4())},
        {"action": "reorder_condition", "condition_id": str(uuid4()), "before_condition_id": None},
    ],
)
def test_request_round_trip_and_unknown_keys_rejected(change: dict) -> None:
    schema = json.loads(
        (SCHEMAS / "edit-jd-conditions-request.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = {"command_id": str(uuid4()), "expected_revision_id": str(uuid4()), "change": change}
    validator.validate(payload)
    assert EditJdConditionsRequest.model_validate(payload).model_dump(mode="json") == payload
    invalid = {**payload, "change": {**change, "internal_revision": str(uuid4())}}
    assert not validator.is_valid(invalid)
    with pytest.raises(ValidationError):
        EditJdConditionsRequest.model_validate(invalid)


def test_view_contains_no_internal_content_revision() -> None:
    schema = json.loads((SCHEMAS / "jd-conditions-view.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = {
        "revision_id": str(uuid4()),
        "conditions": [
            {"condition_id": str(uuid4()), "kind": "work_environment", "text": "室內工作"},
        ],
    }
    validator.validate(payload)
    assert JdConditionsView.model_validate(payload).model_dump(mode="json") == payload
    payload["conditions"][0]["content_revision_id"] = str(uuid4())
    assert not validator.is_valid(payload)
    with pytest.raises(ValidationError):
        JdConditionsView.model_validate(payload)
