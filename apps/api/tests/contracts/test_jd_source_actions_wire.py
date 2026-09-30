"""Source intents stay inside the two canonical revise schemas and use provider-safe wire."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from caliburn.transport.model_tools.jd_item_revision_wire import parse_item_revision
from caliburn.transport.model_tools.jd_write_wire import parse_profile_write
from caliburn.transport.model_tools.jd_writes import jd_write_definitions


@pytest.mark.parametrize("kind", ["profile", "item"])
def test_canonical_source_variants_reach_parser_and_definition_without_private_coordinates(kind):
    name = f"revise_jd_{kind}"
    schema = json.loads(
        (
            Path(__file__).parents[2] / f"contracts/tools/revise-jd-{kind}-arguments.schema.json"
        ).read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    parser = parse_profile_write if kind == "profile" else parse_item_revision
    outer = {} if kind == "profile" else {"read_ref": "task_from_app"}
    target = {"field": "purpose"} if kind == "profile" else {"target": {"kind": "item"}}
    definition = next(value for value in jd_write_definitions() if value["name"] == name)
    assert definition["strict"] is True
    expected = dict(schema)
    expected.pop("$schema")
    assert definition["parameters"] == expected
    assert definition["parameters"]["type"] == "object"

    def check(node):
        if isinstance(node, dict):
            if "$ref" in node:
                assert set(node) == {"$ref"}
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(definition["parameters"])

    changes = [
        {"action": "add_source", **target, "source": source}
        for source in (
            {"kind": "current_input"},
            {"kind": "interview", "interview_sequence": 2},
            {"kind": "work_situation", "target_title": "盤點"},
            {"kind": "work_understanding", "target_title": "庫存管理"},
        )
    ] + [
        {"action": action, **target, "citation_ref": "citation_from_app"}
        for action in ("remove_source", "confirm_reference_alignment")
    ]
    for change in changes:
        payload = {**outer, "changes": [change]}
        validator.validate(payload)
        assert parser(json.dumps(payload)) is not None
        for extra in ({"revision_id": "forged"}, {"source": None}):
            invalid = {**outer, "changes": [{**change, **extra}]}
            assert not validator.is_valid(invalid)
            with pytest.raises(ValidationError):
                parser(json.dumps(invalid))
