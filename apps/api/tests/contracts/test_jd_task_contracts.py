"""Task schema, DTO and domain adapter agree on bounded edits and original intentions."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from caliburn.contracts.generated.edit_jd_tasks_request import EditJdTasksRequest
from caliburn.contracts.generated.jd_tasks_view import JdTasksView
from caliburn.features.job_description.task_changes import task_edit_payload
from caliburn.transport.http.jd_tasks import _edit_from_wire

SCHEMAS = Path(__file__).parents[2] / "contracts/http"


@pytest.mark.parametrize(
    "change",
    [
        {
            "action": "create_task",
            "area_id": None,
            "title": "盤點",
            "description": None,
            "outcomes": ["差異表"],
            "requirements": [],
        },
        {
            "action": "create_task",
            "area_id": str(uuid4()),
            "title": None,
            "description": "按實況盤點",
            "outcomes": [],
            "requirements": ["如實記錄"],
        },
        {
            "action": "revise_task",
            "task_id": str(uuid4()),
            "changes": [
                {"action": "set_field", "field": "title", "value": None},
                {"action": "set_field", "field": "description", "value": "整理紀錄"},
                {"action": "add_detail", "kind": "outcome", "text": "報表"},
                {"action": "revise_detail", "detail_id": str(uuid4()), "text": "核對記錄"},
                {"action": "remove_detail", "detail_id": str(uuid4())},
            ],
        },
        {
            "action": "move_task",
            "task_id": str(uuid4()),
            "area_id": None,
            "before_task_id": None,
            "changes": [],
        },
        {
            "action": "move_task",
            "task_id": str(uuid4()),
            "area_id": str(uuid4()),
            "before_task_id": str(uuid4()),
            "changes": [{"action": "add_detail", "kind": "requirement", "text": "維持核對條件"}],
        },
        {
            "action": "reorder_detail",
            "task_id": str(uuid4()),
            "detail_id": str(uuid4()),
            "before_detail_id": None,
        },
        {
            "action": "reorder_detail",
            "task_id": str(uuid4()),
            "detail_id": str(uuid4()),
            "before_detail_id": str(uuid4()),
        },
        {"action": "delete_task", "task_id": str(uuid4())},
    ],
)
def test_task_edit_round_trip_matches_original_intention(change: dict) -> None:
    schema = json.loads((SCHEMAS / "edit-jd-tasks-request.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = {"command_id": str(uuid4()), "expected_revision_id": str(uuid4()), "change": change}
    validator.validate(payload)
    dto = EditJdTasksRequest.model_validate(payload)
    assert dto.model_dump(mode="json") == payload
    assert task_edit_payload(_edit_from_wire(dto.change)) == change
    invalid = {**payload, "change": {**change, "content_revision_id": str(uuid4())}}
    assert not validator.is_valid(invalid)
    with pytest.raises(ValidationError):
        EditJdTasksRequest.model_validate(invalid)


def test_task_view_exposes_detail_identity_not_internal_revision() -> None:
    schema = json.loads((SCHEMAS / "jd-tasks-view.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = {
        "revision_id": str(uuid4()),
        "tasks": [
            {
                "task_id": str(uuid4()),
                "area_id": None,
                "title": "盤點",
                "description": None,
                "outcomes": [{"detail_id": str(uuid4()), "text": "差異表"}],
                "requirements": [],
            }
        ],
    }
    validator.validate(payload)
    assert JdTasksView.model_validate(payload).model_dump(mode="json") == payload
    payload["tasks"][0]["content_revision_id"] = str(uuid4())
    assert not validator.is_valid(payload)
    with pytest.raises(ValidationError):
        JdTasksView.model_validate(payload)
