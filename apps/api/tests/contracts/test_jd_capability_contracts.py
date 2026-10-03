"""Shared definition and task-use contracts preserve bounded, typed intentions."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from caliburn.contracts.generated.edit_jd_capabilities_request import EditJdCapabilitiesRequest
from caliburn.contracts.generated.jd_capabilities_view import JdCapabilitiesView
from caliburn.features.job_description.capability_changes import capability_change_payload
from caliburn.transport.http.jd_capabilities import _change_from_wire

SCHEMAS = Path(__file__).parents[2] / "contracts/http"


def validator_for(filename: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS / filename).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.mark.parametrize(
    "change",
    [
        {
            "action": "create_capability",
            "kind": "knowledge",
            "name": "資料介面",
            "description": None,
        },
        {"action": "create_capability", "kind": "skill", "name": None, "description": "診斷錯誤"},
        {
            "action": "create_capability",
            "kind": "skill",
            "name": "診斷",
            "description": "讀取錯誤訊號\n定位故障",
        },
        {
            "action": "revise_capability",
            "capability_id": str(uuid4()),
            "changes": [
                {"field": "name", "value": None},
                {"field": "description", "value": "新敘述"},
            ],
        },
        {"action": "delete_capability", "capability_id": str(uuid4())},
        {
            "action": "reorder_capability",
            "capability_id": str(uuid4()),
            "before_capability_id": None,
        },
        {
            "action": "reorder_capability",
            "capability_id": str(uuid4()),
            "before_capability_id": str(uuid4()),
        },
        {
            "action": "set_task_capability",
            "task_id": str(uuid4()),
            "capability_id": str(uuid4()),
            "linked": False,
        },
        {
            "action": "reorder_task_capability",
            "task_id": str(uuid4()),
            "capability_id": str(uuid4()),
            "before_capability_id": None,
        },
        {
            "action": "reorder_task_capability",
            "task_id": str(uuid4()),
            "capability_id": str(uuid4()),
            "before_capability_id": str(uuid4()),
        },
    ],
)
def test_edit_schema_generated_dto_and_domain_round_trip(change: dict) -> None:
    validator = validator_for("edit-jd-capabilities-request.schema.json")
    payload = {"command_id": str(uuid4()), "expected_revision_id": str(uuid4()), "change": change}
    validator.validate(payload)
    dto = EditJdCapabilitiesRequest.model_validate(payload)
    assert dto.model_dump(mode="json") == payload
    stored = capability_change_payload(_change_from_wire(dto.change))
    if change["action"] == "revise_capability":
        assert stored == [
            {"action": change["action"], "capability_id": change["capability_id"]},
            *change["changes"],
        ]
    else:
        assert stored == [change]
    invalid = {**payload, "change": {**change, "content_revision_id": str(uuid4())}}
    assert not validator.is_valid(invalid)
    with pytest.raises(ValidationError):
        EditJdCapabilitiesRequest.model_validate(invalid)


@pytest.mark.parametrize(
    "fields",
    [
        {"name": None, "description": None},
        {"name": ""},
        {"name": " \n\t"},
        {"description": "bad\x00"},
        {"kind": "other"},
        {"name": 1},
        {"name": "\u3000"},
    ],
)
def test_schema_and_dto_reject_invalid_definition(fields: dict) -> None:
    payload = {
        "command_id": str(uuid4()),
        "expected_revision_id": str(uuid4()),
        "change": {
            "action": "create_capability",
            "kind": "knowledge",
            "name": "知識",
            "description": None,
            **fields,
        },
    }
    assert not validator_for("edit-jd-capabilities-request.schema.json").is_valid(payload)
    with pytest.raises(ValidationError):
        EditJdCapabilitiesRequest.model_validate(payload)


def test_view_exposes_shared_content_once_with_ordered_identity_links() -> None:
    capability_id = str(uuid4())
    payload = {
        "revision_id": str(uuid4()),
        "capabilities": [
            {
                "capability_id": capability_id,
                "kind": "skill",
                "name": None,
                "description": "故障診斷",
            }
        ],
        "task_links": [{"task_id": str(uuid4()), "capability_id": capability_id} for _ in range(2)],
    }
    validator = validator_for("jd-capabilities-view.schema.json")
    validator.validate(payload)
    assert JdCapabilitiesView.model_validate(payload).model_dump(mode="json") == payload
    payload["capabilities"][0]["content_revision_id"] = str(uuid4())
    assert not validator.is_valid(payload)
    with pytest.raises(ValidationError):
        JdCapabilitiesView.model_validate(payload)
