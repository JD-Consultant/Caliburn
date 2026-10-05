"""Behavioral isolation checks; no network or production database."""

import copy
import json
from pathlib import Path

import pytest
from workspace import Workspace, tool_definitions

HERE = Path(__file__).parent
MESSAGES = json.loads((HERE / "materials.json").read_text(encoding="utf-8"))["messages"]


def create(workspace, role, title="接單", body="原正文", refs=None):
    layer = "work_situation" if role == "b1" else "work_understanding"
    field = "work_situation_references" if role == "b2" else "interview_references"
    return workspace.invoke(
        role,
        f"create_{layer}",
        {
            "title": title,
            "description": "接單範圍",
            "body": body,
            field: refs if refs is not None else [2],
        },
    )


def test_future_and_reversed_ranges_rejected_without_partial_read():
    workspace = Workspace("one_collection", MESSAGES)
    workspace.read_through = 10
    for query in (
        {"kind": "messages", "sequences": [2, 12]},
        {"kind": "range", "start_sequence": 1, "end_sequence": 12},
        {"kind": "range", "start_sequence": 5, "end_sequence": 2},
    ):
        result = workspace.invoke("single", "read_interview", {"query": query})
        assert "error" in result and "messages" not in result
    result = workspace.invoke(
        "single",
        "read_interview",
        {"query": {"kind": "messages", "sequences": [4, 2, 2]}},
    )
    assert [message["interview_sequence"] for message in result["messages"]] == [2, 4]


def test_role_and_arm_permissions_are_enforced_not_just_described():
    dual = Workspace("two_layer", MESSAGES)
    single = Workspace("one_collection", MESSAGES)
    for workspace, role, name in (
        (dual, "b1", "read_work_understanding_map"),
        (dual, "b2", "delete_work_situation"),
        (single, "single", "read_work_situation_map"),
        (single, "reader", "create_work_understanding"),
    ):
        assert workspace.invoke(role, name, {})["error"]["code"] == "scope_not_allowed"


def test_snapshots_are_independent_and_keep_original_source_bounds():
    workspace = Workspace("one_collection", MESSAGES)
    workspace.read_through = 10
    assert create(workspace, "single")["status"] == "created"
    snapshot = workspace.snapshot()
    restored = Workspace.restore("one_collection", MESSAGES, snapshot)
    workspace.invoke(
        "single",
        "update_work_understanding",
        {"target_title": "接單", "changes": [{"field": "title", "value": "新名稱"}]},
    )
    workspace.read_through = 18
    assert restored.read_through == 10
    assert restored.map("work_understanding")["items"][0]["target_title"] == "接單"
    other = Workspace("one_collection", MESSAGES)
    assert other.map("work_understanding")["items"] == []


def test_rename_keeps_binding_and_delete_unlinks_without_deleting_downstream():
    workspace = Workspace("two_layer", MESSAGES)
    workspace.read_through = 10
    create(workspace, "b1")
    create(workspace, "b2", title="防止重送", refs=["接單"])
    workspace.invoke(
        "b1",
        "update_work_situation",
        {"target_title": "接單", "changes": [{"field": "title", "value": "訂單"}]},
    )
    result = workspace.invoke(
        "b2", "read_work_understanding", {"target_title": "防止重送"}
    )
    assert result["work_situation_references"][0]["target_title"] == "訂單"
    workspace.invoke("b1", "delete_work_situation", {"target_title": "訂單"})
    result = workspace.invoke(
        "b2", "read_work_understanding", {"target_title": "防止重送"}
    )
    assert result["work_situation_references"] == []


def test_invalid_sources_and_ambiguous_patch_leave_all_changes_unadopted():
    workspace = Workspace("one_collection", MESSAGES)
    workspace.read_through = 10
    assert "error" in create(workspace, "single", refs=[12])
    assert not workspace.map("work_understanding")["items"]
    create(workspace, "single", body="相同文字\n相同文字\n")
    before = workspace.snapshot()
    result = workspace.invoke(
        "single",
        "update_work_understanding",
        {
            "target_title": "接單",
            "changes": [
                {"field": "title", "value": "更名"},
                {"field": "body", "diff": "@@\n-相同文字\n+新文字\n"},
            ],
        },
    )
    assert "error" in result
    assert workspace.snapshot() == before


def test_unique_titles_and_atomic_reference_members():
    workspace = Workspace("one_collection", MESSAGES)
    workspace.read_through = 10
    create(workspace, "single")
    assert "error" in create(workspace, "single")
    before = copy.deepcopy(workspace.snapshot())
    for change in (
        {"field": "interview_references", "add": [4], "remove": [4]},
        {"field": "interview_references", "remove": [6]},
    ):
        assert "error" in workspace.invoke(
            "single",
            "update_work_understanding",
            {"target_title": "接單", "changes": [change]},
        )
        assert workspace.snapshot() == before


@pytest.mark.parametrize(
    "arm,role",
    [
        ("two_layer", "b1"),
        ("two_layer", "b2"),
        ("one_collection", "single"),
        ("two_layer", "reader"),
        ("one_collection", "reader"),
    ],
)
def test_tools_have_strict_schemas_and_no_scope_version_arguments(arm, role):
    from jsonschema import Draft202012Validator

    for tool in tool_definitions(arm, role):
        assert tool["strict"]
        Draft202012Validator.check_schema(tool["parameters"])
        assert (
            not {"version", "scope", "job_file_id"}
            & tool["parameters"]["properties"].keys()
        )
