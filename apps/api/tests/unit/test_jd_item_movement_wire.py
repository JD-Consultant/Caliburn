"""The canonical move schema exposes only placement and bounded content choices."""

import json

import pytest
from pydantic import ValidationError

from caliburn.features.job_description.tasks import DetailKind
from caliburn.transport.model_tools.jd_item_movement_wire import parse_item_movement
from caliburn.workflows.jd_item_movement import (
    CurrentItemContainer,
    ItemPosition,
    MoveItemInput,
    MovementDetailAddition,
    MovementTextChange,
    TaskParentDestination,
)


def test_move_wire_distinguishes_unassigned_from_current_container():
    assert parse_item_movement(
        json.dumps(
            {
                "read_ref": "task_app",
                "destination": {"kind": "task_parent", "parent_read_ref": None},
                "position": {"kind": "after", "neighbor_read_ref": "task_neighbor"},
                "content_changes": [
                    {
                        "action": "set_field",
                        "read_ref": "task_app",
                        "field": "description",
                        "value": "完整限制",
                    },
                    {"action": "clear_field", "read_ref": "task_app", "field": "title"},
                    {"action": "add_detail", "kind": "requirement", "text": "需遵守的條件"},
                ],
            }
        )
    ) == MoveItemInput(
        "task_app",
        TaskParentDestination(None),
        ItemPosition("after", "task_neighbor"),
        (
            MovementTextChange("task_app", "description", "完整限制"),
            MovementTextChange("task_app", "title", None),
            MovementDetailAddition(DetailKind.REQUIREMENT, "需遵守的條件"),
        ),
    )
    assert parse_item_movement(
        json.dumps(
            {
                "read_ref": "knowledge_app",
                "destination": {"kind": "current_container"},
                "position": {"kind": "first"},
                "content_changes": [],
            }
        )
    ) == MoveItemInput("knowledge_app", CurrentItemContainer(), ItemPosition("first"))


@pytest.mark.parametrize(
    "override",
    [
        {"job_file_id": "model_must_not_choose_scope"},
        {"position": {"kind": "first", "neighbor_read_ref": "ignored?"}},
        {"position": {"kind": "before"}},
        {"destination": {"kind": "current_container", "parent_read_ref": None}},
        {
            "content_changes": [
                {"action": "clear_field", "read_ref": "outcome_app", "field": "text"}
            ]
        },
    ],
)
def test_move_wire_rejects_scope_and_ambiguous_parameters(override):
    with pytest.raises(ValidationError):
        parse_item_movement(
            json.dumps(
                {
                    "read_ref": "task_app",
                    "destination": {"kind": "current_container"},
                    "position": {"kind": "last"},
                    "content_changes": [],
                    **override,
                }
            )
        )
