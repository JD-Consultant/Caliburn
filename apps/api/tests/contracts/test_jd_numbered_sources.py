"""JD interview evidence uses one numeric selector, including the current input."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from caliburn.transport.model_tools.jd_item_creation_wire import parse_item_creation
from caliburn.transport.model_tools.jd_item_revision_wire import parse_item_revision
from caliburn.transport.model_tools.jd_write_wire import parse_profile_write, parse_task_write


@pytest.mark.parametrize(
    ("name", "parser", "payload"),
    [
        (
            "revise-jd-profile",
            parse_profile_write,
            {
                "changes": [
                    {
                        "action": "add_source",
                        "field": "purpose",
                        "source": {"kind": "current_input"},
                    }
                ]
            },
        ),
        (
            "revise-jd-item",
            parse_item_revision,
            {
                "read_ref": "task_app",
                "changes": [
                    {
                        "action": "add_source",
                        "target": {"kind": "item"},
                        "source": {"kind": "current_input"},
                    }
                ],
            },
        ),
        (
            "create-jd-item",
            parse_item_creation,
            {
                "item": {
                    "kind": "responsibility_area",
                    "title": "交付",
                    "scope_text": None,
                    "supporting_sources": [{"kind": "current_input"}],
                }
            },
        ),
        (
            "create-jd-task",
            parse_task_write,
            {
                "parent_read_ref": None,
                "title": "交付",
                "description": None,
                "outcomes": [],
                "requirements": [],
                "required_knowledge": [],
                "required_skills": [],
                "supporting_sources": [{"kind": "current_input"}],
            },
        ),
    ],
)
def test_unnumbered_current_input_is_rejected_by_schema_and_parser(name, parser, payload):
    path = Path(__file__).parents[2] / f"contracts/tools/{name}-arguments.schema.json"
    validator = Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))
    assert not validator.is_valid(payload)
    with pytest.raises(ValidationError):
        parser(json.dumps(payload))
