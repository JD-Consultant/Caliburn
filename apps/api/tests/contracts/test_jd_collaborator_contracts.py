"""Collaborator DTO generation preserves values, null semantics and strict nested shapes."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from caliburn.contracts.generated.edit_jd_collaborators_request import EditJdCollaboratorsRequest
from caliburn.contracts.generated.jd_collaborators_view import JdCollaboratorsView

SCHEMAS = Path(__file__).parents[2] / "contracts/http"


@pytest.mark.parametrize(
    "change",
    [
        {"action": "create_collaborator", "name": "交付", "scope_text": None},
        {"action": "create_collaborator", "name": None, "scope_text": "前端範圍"},
        {
            "action": "revise_collaborator",
            "collaborator_id": str(uuid4()),
            "changes": [
                {"field": "name", "value": None},
                {"field": "scope_text", "value": "已確認範圍"},
            ],
        },
        {"action": "delete_collaborator", "collaborator_id": str(uuid4())},
        {
            "action": "reorder_collaborator",
            "collaborator_id": str(uuid4()),
            "before_collaborator_id": None,
        },
        {
            "action": "reorder_collaborator",
            "collaborator_id": str(uuid4()),
            "before_collaborator_id": str(uuid4()),
        },
    ],
)
def test_edit_round_trip_and_rejected_extra_keys(change: dict) -> None:
    schema = json.loads(
        (SCHEMAS / "edit-jd-collaborators-request.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = {"command_id": str(uuid4()), "expected_revision_id": str(uuid4()), "change": change}
    validator.validate(payload)
    assert EditJdCollaboratorsRequest.model_validate(payload).model_dump(mode="json") == payload
    invalid = {**payload, "change": {**change, "internal_revision": str(uuid4())}}
    assert not validator.is_valid(invalid)
    with pytest.raises(ValidationError):
        EditJdCollaboratorsRequest.model_validate(invalid)


def test_collaborator_view_does_not_expose_internal_content_revision() -> None:
    schema = json.loads((SCHEMAS / "jd-collaborators-view.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = {
        "revision_id": str(uuid4()),
        "collaborators": [
            {"collaborator_id": str(uuid4()), "name": None, "scope_text": "已確認範圍"},
        ],
    }
    validator.validate(payload)
    assert JdCollaboratorsView.model_validate(payload).model_dump(mode="json") == payload
    payload["collaborators"][0]["content_revision_id"] = str(uuid4())
    assert not validator.is_valid(payload)
    with pytest.raises(ValidationError):
        JdCollaboratorsView.model_validate(payload)
