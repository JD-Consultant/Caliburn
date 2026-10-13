"""Generated finite wire choices become one typed item revision, without scope fabrication."""

import json

import pytest
from pydantic import ValidationError

from caliburn.features.job_description.item_revision import (
    AddItemDetail,
    AddItemSource,
    ItemFieldChange,
    ItemSourceTarget,
    ReorderItemCapability,
    SetItemCapability,
)
from caliburn.features.job_description.source_intents import InterviewSourceSelection
from caliburn.features.job_description.tasks import DetailKind
from caliburn.transport.model_tools.jd_item_revision_wire import parse_item_revision


def test_revision_wire_keeps_full_text_and_shared_task_source():
    intent = parse_item_revision(
        json.dumps(
            {
                "read_ref": "task_app",
                "changes": [
                    {"action": "set_field", "field": "description", "value": "完整新值"},
                    {"action": "clear_field", "field": "title"},
                    {
                        "action": "add_detail",
                        "kind": "requirement",
                        "text": "完整要求",
                    },
                    {
                        "action": "add_source",
                        "target": {
                            "kind": "item",
                        },
                        "source": {"kind": "interview", "interview_sequence": 2},
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
                ],
            }
        )
    )
    assert intent.read_ref == "task_app"
    assert intent.changes == (
        ItemFieldChange("description", "完整新值"),
        ItemFieldChange("title", None),
        AddItemDetail(DetailKind.REQUIREMENT, "完整要求"),
        AddItemSource(ItemSourceTarget(), InterviewSourceSelection(2)),
        SetItemCapability("knowledge_app", False),
        ReorderItemCapability("skill_app", "after", "skill_neighbor"),
    )


def test_wire_rejects_unlink_sources_and_model_owned_operation_identity():
    for value in (
        {
            "read_ref": "task_app",
            "changes": [
                {
                    "action": "set_capability",
                    "capability_read_ref": "skill_app",
                    "relationship": "unlink",
                    "supporting_sources": [],
                }
            ],
        },
        {
            "read_ref": "task_app",
            "changes": [{"action": "clear_field", "field": "title"}],
            "operation_id": "fake",
        },
    ):
        with pytest.raises(ValidationError):
            parse_item_revision(json.dumps(value))
