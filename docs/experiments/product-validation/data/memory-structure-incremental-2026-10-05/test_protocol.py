"""Context and reader provenance checks (added after the protocol implementation)."""

import json
from pathlib import Path

import pytest
from protocol import context, reader_context, validate_completion
from workspace import Workspace

MATERIAL = json.loads(
    (Path(__file__).parent / "materials.json").read_text(encoding="utf-8")
)


def test_only_current_batch_messages_are_preloaded():
    workspace = Workspace("one_collection", MATERIAL["messages"])
    workspace.read_through = 14
    result = context(workspace, "single", MATERIAL["batches"][1])
    assert [
        item["interview_sequence"] for item in result["new_interview_messages"]
    ] == [11, 12, 13, 14]
    assert set(result) == {"資料性質", "maps", "new_interview_messages"}
    assert set(result["maps"]) == {"work_understanding"}
    assert "產品負責人" not in json.dumps(result, ensure_ascii=False)


def test_b2_sees_zero_to_new_object_diff_but_b1_sees_no_understanding():
    workspace = Workspace("two_layer", MATERIAL["messages"])
    workspace.read_through = 10
    workspace.invoke(
        "b1",
        "create_work_situation",
        {
            "title": "訂單",
            "description": "防重送",
            "body": "甲處理前端",
            "interview_references": [2],
        },
    )
    result = context(workspace, "b2", MATERIAL["batches"][0], {})
    assert "new_interview_messages" not in result
    assert result["situation_changes"][0]["before_title"] is None
    assert "+" in result["situation_changes"][0]["diff"]
    assert set(context(workspace, "b1", MATERIAL["batches"][0])["maps"]) == {
        "work_situation"
    }


def test_reader_gets_navigation_not_body_or_raw_interview():
    workspace = Workspace("one_collection", MATERIAL["messages"])
    assert set(reader_context(workspace, "問題")) == {
        "question",
        "work_understanding_map",
    }


def test_reader_cannot_cite_unread_body():
    workspace = Workspace("one_collection", MATERIAL["messages"])
    result = {
        "task": {"title": "接單", "work": "防重送"},
        "unknowns": [],
        "references": [{"kind": "work_understanding", "target_title": "接單"}],
    }
    with pytest.raises(ValueError, match="unread_reference"):
        validate_completion("reader", result, workspace, set())
    validate_completion("reader", result, workspace, {("work_understanding", "接單")})
