"""Authored revise-item input keeps finite variants and App-owned identity out of wire."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


@pytest.fixture
def validator():
    path = Path(__file__).parents[2] / "contracts/tools/revise-jd-item-arguments.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_finite_changes_keep_each_direct_source_owner(validator):
    validator.validate(
        {
            "read_ref": "task_app",
            "changes": [
                {"action": "set_field", "field": "description", "value": "完整新文"},
                {"action": "clear_field", "field": "title"},
                {
                    "action": "add_detail",
                    "kind": "outcome",
                    "text": "成果",
                    "supporting_sources": [],
                },
                {"action": "revise_detail", "detail_read_ref": "outcome_app", "text": "新成果"},
                {"action": "remove_detail", "detail_read_ref": "requirement_app"},
                {
                    "action": "set_capability",
                    "capability_read_ref": "skill_app",
                    "relationship": "link",
                    "supporting_sources": [{"kind": "current_input"}],
                },
                {
                    "action": "set_capability",
                    "capability_read_ref": "knowledge_app",
                    "relationship": "unlink",
                },
                {
                    "action": "reorder_capability",
                    "capability_read_ref": "skill_app",
                    "position": {"kind": "after", "capability_read_ref": "skill_neighbor"},
                },
                {
                    "action": "add_source",
                    "target": {"kind": "item"},
                    "source": {"kind": "work_situation", "target_title": "工作"},
                },
                {
                    "action": "remove_source",
                    "target": {"kind": "detail", "detail_read_ref": "outcome_app"},
                    "citation_ref": "citation_app",
                },
                {
                    "action": "confirm_reference_alignment",
                    "target": {"kind": "capability_relation", "capability_read_ref": "skill_app"},
                    "citation_ref": "citation_relation",
                },
            ],
        }
    )


@pytest.mark.parametrize(
    "change",
    [
        {"action": "clear_field", "field": "text"},
        {"action": "clear_field", "field": "title", "value": None},
        {
            "action": "set_capability",
            "capability_read_ref": "skill_app",
            "relationship": "unlink",
            "supporting_sources": [],
        },
        {
            "action": "reorder_capability",
            "capability_read_ref": "skill_app",
            "position": {"kind": "first", "capability_read_ref": "neighbor"},
        },
        {
            "action": "add_source",
            "target": {"kind": "item"},
            "source": {"kind": "current_input", "source_id": "fake"},
        },
    ],
)
def test_unrelated_fields_and_empty_shell_actions_are_rejected(validator, change):
    assert list(validator.iter_errors({"read_ref": "task_app", "changes": [change]}))
