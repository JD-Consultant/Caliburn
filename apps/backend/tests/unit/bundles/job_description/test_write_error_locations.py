"""模型拒絕指出原參數位置；已成功修改與修正後重送分開驗證。"""

import json
from uuid import UUID

import pytest

from caliburn.modules.job_description.domain.models.citation import InterviewReference
from tests.unit.bundles.job_description.test_write_tools import Harness, payload


@pytest.mark.parametrize(
    "changes,location,reason",
    [
        (
            [{"action": "set_field", "field": "description", "value": "PRIVATE"}],
            "changes[0].field",
            "不適用",
        ),
        (
            [
                {"action": "set_field", "field": "scope", "value": "PRIVATE"},
                {"action": "clear_field", "field": "scope"},
            ],
            "changes[1].field",
            "重複",
        ),
    ],
)
def test_revision_field_rejection_is_located_and_repairable(
    changes: list[dict[str, str]], location: str, reason: str
) -> None:
    harness = Harness()
    created = payload(
        harness.invoke("create_jd_item", {"item": {"kind": "duty", "name": "設備"}})
    )
    before = harness.store.snapshot()
    rejected = payload(
        harness.invoke(
            "revise_jd_item", {"read_ref": created["read_ref"], "changes": changes}
        )
    )
    assert rejected["code"] == "invalid_arguments"
    assert location in rejected["message"] and reason in rejected["message"]
    if reason == "不適用":
        assert "name" in rejected["next_action"] and "scope" in rejected["next_action"]
    assert "PRIVATE" not in json.dumps(rejected)
    assert harness.store.snapshot() == before and harness.store.commits == 1

    repaired = payload(
        harness.invoke(
            "revise_jd_item",
            {
                "read_ref": created["read_ref"],
                "changes": [{"action": "set_field", "field": "scope", "value": "維護"}],
            },
        )
    )
    assert repaired["status"] == "updated"
    assert harness.store.commits == 2
    assert harness.store.snapshot().duties[0].scope == "維護"


@pytest.mark.parametrize("nested", [False, True])
def test_unknown_interview_reference_is_repairable_without_read_tool(
    nested: bool,
) -> None:
    harness = Harness()
    duty = harness.store.root.add_duty(name="設備")
    duty_ref = harness.ref("duty", duty)
    source = {"kind": "interview", "message_ref": "message_9223372036854775807"}
    if nested:
        name = "revise_jd_item"
        arguments: dict[str, object] = {
            "read_ref": duty_ref,
            "changes": [{"action": "add_source", "source": source}],
        }
        location = "changes[0].source.message_ref"
    else:
        name = "create_jd_task"
        arguments = {
            "name": "巡檢",
            "parent_read_ref": duty_ref,
            "supporting_sources": [source],
        }
        location = "supporting_sources[0].message_ref"
    before = harness.store.snapshot()
    rejected = payload(harness.invoke(name, arguments))
    assert rejected["code"] == "target_not_found"
    assert location in rejected["message"]
    assert source["message_ref"] in rejected["message"]
    assert "read_interview" not in rejected["next_action"]
    assert "read_jd" not in rejected["next_action"]
    assert "message_ref" in rejected["next_action"]
    assert "PRIVATE REFERENCE DETAIL" not in json.dumps(rejected)
    assert harness.store.snapshot() == before
    assert harness.store.commits == 0

    available = InterviewReference(
        workspace_id=harness.store.root.workspace_id, message_id=UUID(int=23)
    )
    harness.store.available_sources.add(available)
    source["message_ref"] = harness.ref("message", available.message_id)
    repaired = payload(harness.invoke(name, arguments))
    assert repaired["status"] == ("updated" if nested else "created")
    assert harness.store.commits == 1
    assert len(harness.store.snapshot().citations) == 1
    assert harness.store.snapshot().citations[0].source == available


def test_unknown_jd_reference_points_to_jd_navigation() -> None:
    harness = Harness()
    rejected = payload(
        harness.invoke("delete_jd_item", {"read_ref": "task_9223372036854775807"})
    )
    assert rejected["code"] == "target_not_found"
    assert "read_ref" in rejected["message"]
    assert "task_9223372036854775807" in rejected["message"]
    assert "read_jd" in rejected["next_action"]
    assert harness.store.commits == 0


def test_wrong_kind_reused_reference_lists_both_parameter_locations() -> None:
    harness = Harness()
    created = payload(harness.invoke("create_jd_task", {"name": "核對"}))
    task_ref = created["read_ref"]
    before = harness.store.snapshot()
    rejected = payload(
        harness.invoke(
            "revise_jd_item",
            {
                "read_ref": task_ref,
                "changes": [
                    {
                        "action": "set_capability",
                        "relationship": "link",
                        "capability_read_ref": task_ref,
                    }
                ],
            },
        )
    )
    assert rejected["code"] == "target_not_found"
    assert "read_ref" in rejected["message"]
    assert "changes[0].capability_read_ref" in rejected["message"]
    assert "knowledge" in rejected["next_action"]
    assert "skill" in rejected["next_action"]
    assert harness.store.snapshot() == before
    assert harness.store.commits == 1


def test_blank_nested_text_rejection_uses_parameter_path_without_union_names() -> None:
    harness = Harness()
    duty = harness.store.root.add_duty(name="設備")
    rejected = payload(
        harness.invoke(
            "revise_jd_item",
            {
                "read_ref": harness.ref("duty", duty),
                "changes": [
                    {"action": "set_field", "field": "name", "value": "PRIVATE"},
                    {"action": "set_field", "field": "scope", "value": "  "},
                ],
            },
        )
    )
    assert rejected["code"] == "invalid_arguments"
    assert "changes[1].value" in rejected["message"]
    assert "非空白" in rejected["message"]
    assert "SetField" not in rejected["message"]
    assert "PRIVATE" not in json.dumps(rejected)
    assert harness.store.commits == 0


def test_long_entry_name_rejection_explains_domain_limit_without_revalidating() -> None:
    harness = Harness()
    rejected = payload(
        harness.invoke("create_jd_item", {"item": {"kind": "duty", "name": "x" * 256}})
    )
    assert rejected["code"] == "invalid_arguments"
    assert "255" in rejected["next_action"] and "空白" in rejected["next_action"]
    assert "x" * 256 not in json.dumps(rejected)
    assert harness.store.commits == 0
    repaired = payload(
        harness.invoke(
            "create_jd_item",
            {"item": {"kind": "duty", "name": " " * 260 + "設備" + " " * 260}},
        )
    )
    assert repaired["status"] == "created"
    assert harness.store.snapshot().duties[0].name == "設備"
    assert harness.store.commits == 1


def test_value_error_uses_the_matching_action_branch() -> None:
    harness = Harness()
    task = harness.store.root.add_task(name="巡檢")
    rejected = payload(
        harness.invoke(
            "revise_jd_item",
            {
                "read_ref": harness.ref("task", task),
                "changes": [{"action": "set_competency_level", "value": "  "}],
            },
        )
    )
    assert "changes[0].value" in rejected["message"]
    assert "級別" in rejected["message"]
    assert "非空白" not in rejected["message"]
    assert harness.store.commits == 0


def test_movement_field_rejection_keeps_the_original_content_change_index() -> None:
    harness = Harness()
    old_duty = harness.store.root.add_duty(name="設備")
    new_duty = harness.store.root.add_duty(name="巡檢")
    task = harness.store.root.add_task(name="檢查", duty_id=old_duty)
    before = harness.store.snapshot()
    rejected = payload(
        harness.invoke(
            "move_jd_item",
            {
                "read_ref": harness.ref("task", task),
                "destination": {
                    "kind": "task_parent",
                    "parent_read_ref": harness.ref("duty", new_duty),
                },
                "before_read_ref": None,
                "content_changes": [
                    {
                        "action": "set_duty_scope",
                        "duty_read_ref": harness.ref("duty", old_duty),
                        "scope": "設備維護",
                    },
                    {"action": "set_field", "field": "name", "value": "新名"},
                    {"action": "set_field", "field": "name", "value": "PRIVATE"},
                ],
            },
        )
    )
    assert "content_changes[2].field" in rejected["message"]
    assert "PRIVATE" not in json.dumps(rejected)
    assert harness.store.snapshot() == before and harness.store.commits == 0


@pytest.mark.parametrize("use_uuid", [False, True])
def test_task_parent_rejection_locates_kind_or_schema_problem(use_uuid: bool) -> None:
    harness = Harness()
    duty = harness.store.root.add_duty(name="設備")
    task = harness.store.root.add_task(name="existing task")
    task_ref = harness.ref("task", task)
    parent = str(task) if use_uuid else task_ref
    before = harness.store.snapshot()
    rejected = payload(
        harness.invoke(
            "create_jd_task", {"name": "new task", "parent_read_ref": parent}
        )
    )
    assert "parent_read_ref" in rejected["message"]
    if use_uuid:
        assert rejected["code"] == "invalid_arguments"
        assert parent not in json.dumps(rejected)
    else:
        assert rejected["code"] == "target_not_found"
        assert task_ref in rejected["message"]
        assert "duty" in rejected["next_action"]
        assert "read_jd" in rejected["next_action"]
    assert harness.store.snapshot() == before and harness.store.commits == 0

    repaired = payload(
        harness.invoke(
            "create_jd_task",
            {"name": "new task", "parent_read_ref": harness.ref("duty", duty)},
        )
    )
    assert repaired["status"] == "created"
    assert harness.store.snapshot().tasks[-1].duty_id == duty
    assert harness.store.commits == 1
