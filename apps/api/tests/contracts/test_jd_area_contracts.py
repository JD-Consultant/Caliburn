"""Area DTO generation preserves values, null semantics and strict nested shapes."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from caliburn.contracts.generated.edit_jd_areas_request import EditJdAreasRequest
from caliburn.contracts.generated.jd_areas_view import JdAreasView

SCHEMAS = Path(__file__).parents[2] / "contracts/http"


@pytest.mark.parametrize(
    "change",
    [
        {"action": "create_area", "title": "交付", "scope_text": None},
        {"action": "create_area", "title": None, "scope_text": "前端範圍"},
        {
            "action": "revise_area",
            "area_id": str(uuid4()),
            "changes": [
                {"field": "title", "value": None},
                {"field": "scope_text", "value": "已確認範圍"},
            ],
        },
        {"action": "delete_area", "area_id": str(uuid4())},
        {"action": "reorder_area", "area_id": str(uuid4()), "before_area_id": None},
        {"action": "reorder_area", "area_id": str(uuid4()), "before_area_id": str(uuid4())},
    ],
)
def test_edit_round_trip_and_rejected_extra_keys(change: dict) -> None:
    schema = json.loads((SCHEMAS / "edit-jd-areas-request.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = {"command_id": str(uuid4()), "expected_revision_id": str(uuid4()), "change": change}
    validator.validate(payload)
    assert EditJdAreasRequest.model_validate(payload).model_dump(mode="json") == payload
    invalid = {**payload, "change": {**change, "internal_revision": str(uuid4())}}
    assert not validator.is_valid(invalid)
    with pytest.raises(ValidationError):
        EditJdAreasRequest.model_validate(invalid)


def test_area_view_does_not_expose_internal_content_revision() -> None:
    schema = json.loads((SCHEMAS / "jd-areas-view.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = {
        "revision_id": str(uuid4()),
        "areas": [
            {"area_id": str(uuid4()), "title": None, "scope_text": "已確認範圍"},
        ],
    }
    validator.validate(payload)
    assert JdAreasView.model_validate(payload).model_dump(mode="json") == payload
    payload["areas"][0]["content_revision_id"] = str(uuid4())
    assert not validator.is_valid(payload)
    with pytest.raises(ValidationError):
        JdAreasView.model_validate(payload)
