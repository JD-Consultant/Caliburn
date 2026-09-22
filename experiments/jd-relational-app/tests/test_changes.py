"""Stable-identity JD net changes, including ordering and association counterexamples."""

from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from jd_relational.changes import ChangeRecord, compare_snapshots
from jd_relational.domain import CommandContext, Ref, SOURCE_COLUMNS, build_candidate
from jd_relational.snapshots import SnapshotValidationError, empty_domain, snapshot_from_domain
from test_snapshots import REVISION, complete_domain, uid


def compare(before, after):
    return compare_snapshots(snapshot_from_domain(before), snapshot_from_domain(after))


def records(changes, entity_kind, kind=None):
    return [item for item in changes if item.entity_kind == entity_kind and (kind is None or item.kind == kind)]


def ordered_tasks(count=4):
    value = empty_domain("document-a", REVISION)
    for i in range(count):
        identity = uid(100 + i)
        value["tasks"][identity] = {"task_id": identity, "duty_id": None, "name": "同名工作",
            "description": None, "position": i}
    return value


def test_identical_snapshot_and_serialized_array_order_have_no_net_changes():
    before = snapshot_from_domain(complete_domain())
    after = deepcopy(before)
    for value in after.values():
        if isinstance(value, list):
            value.reverse()
    assert compare_snapshots(before, after) == ()


def test_change_records_are_dataclasses_with_complete_detached_rows():
    before = complete_domain()
    after = deepcopy(before)
    after["tasks"][uid(3)]["description"] = "繁中😀\n保留空白 e\u0301  "
    left, right = snapshot_from_domain(before), snapshot_from_domain(after)
    saved = deepcopy((left, right))
    result = compare_snapshots(left, right)
    assert isinstance(result, tuple) and len(result) == 1 and isinstance(result[0], ChangeRecord)
    row = result[0]
    assert (row.kind, row.entity_kind, row.identity, row.changed_fields, row.affected_task_ids) == (
        "update", "task", (uid(3),), ("description",), (uid(3),))
    assert row.before == before["tasks"][uid(3)] and row.after == after["tasks"][uid(3)]
    assert (left, right) == saved
    with pytest.raises(FrozenInstanceError):
        row.kind = "delete"
    row.after["description"] = "只改輸出副本"
    assert (left, right) == saved


@pytest.mark.parametrize("field", ["job_title", "organization_unit", "employee_name", "reports_to", "purpose"])
def test_all_five_profile_fields_include_null_and_exact_text(field):
    before = complete_domain()
    after = deepcopy(before)
    after["profile"][field] = None if before["profile"][field] is not None else "未填名稱😀\n完整正文"
    result = compare(before, after)
    assert len(result) == 1
    assert (result[0].entity_kind, result[0].identity, result[0].changed_fields) == ("profile", (), (field,))
    assert result[0].before == before["profile"] and result[0].after == after["profile"]


def test_same_name_items_remain_distinct_and_name_only_can_become_description_only():
    before = ordered_tasks(2)
    after = deepcopy(before)
    after["tasks"][uid(101)].update(name=None, description="確切工作範圍")
    result = compare(before, after)
    assert len(result) == 1 and result[0].identity == (uid(101),)
    assert result[0].changed_fields == ("description", "name")


def test_empty_to_full_and_full_to_empty_cover_all_entities_and_source_targets():
    full = complete_domain()
    blank = empty_domain(full["document_id"], REVISION)
    added, removed = compare(blank, full), compare(full, blank)
    for entity_kind in ("collaborator", "duty", "task", "detail", "capability", "condition"):
        assert records(added, entity_kind, "create")
        assert records(removed, entity_kind, "delete")
    assert len(records(added, "task_capability", "link")) == 3
    assert len(records(removed, "task_capability", "unlink")) == 3
    assert len(records(added, "source_link", "link")) == 8
    assert len(records(removed, "source_link", "unlink")) == 8
    assert all(item.before is None for item in added if item.kind in ("create", "link"))
    assert all(item.after is None for item in removed if item.kind in ("delete", "unlink"))


def test_d01_keeps_task_and_owned_content_as_move_not_delete_create():
    before = complete_domain()
    context = CommandContext(before["document_id"], REVISION,
        {"duty": Ref(before["document_id"], REVISION, "duty", uid(2))}, {}, lambda: uid(800))
    after = build_candidate(before, {"tool": "jd_delete_item", "arguments": {
        "target_ref": "duty", "content_changes": []}}, context)
    result = compare(before, after)
    assert len(records(result, "duty", "delete")) == 1
    moved = records(result, "task")
    assert len(moved) == 1 and moved[0].kind == "move" and moved[0].identity == (uid(3),)
    assert moved[0].before["duty_id"] == uid(2) and moved[0].after["duty_id"] is None
    assert not records(result, "detail") and not records(result, "task_capability")
    assert len(records(result, "source_link", "unlink")) == 1


def test_shared_capability_update_reports_union_of_both_versions_task_links():
    before = complete_domain()
    after = deepcopy(before)
    after["capabilities"][uid(10)]["description"] = "更正共用技能，不能漏先前引用任務"
    after["task_capabilities"] = [row for row in after["task_capabilities"] if row["task_id"] != uid(4)]
    after["tasks"][uid(50)] = {"task_id": uid(50), "duty_id": None, "name": "新增任務", "description": None, "position": 5}
    after["task_capabilities"].append({"task_id": uid(50), "capability_id": uid(10), "position": 0})
    result = compare(before, after)
    changed = records(result, "capability", "update")
    assert len(changed) == 1 and changed[0].identity == (uid(10),)
    assert changed[0].affected_task_ids == (uid(3), uid(4), uid(50))
    assert records(result, "task_capability", "unlink")[0].identity == (uid(4), uid(10))
    assert records(result, "task_capability", "link")[0].identity == (uid(50), uid(10))


@pytest.mark.parametrize("field,value", [("basis_digest", "b" * 64), ("source_ref", "issued-source-updated")])
def test_source_updates_preserve_complete_rows_and_affected_tasks(field, value):
    before = complete_domain()
    after = deepcopy(before)
    after["source_links"][7][field] = value
    result = compare(before, after)
    assert len(result) == 1
    assert (result[0].kind, result[0].entity_kind, result[0].changed_fields) == ("update", "source_link", (field,))
    assert result[0].affected_task_ids == (uid(3),)
    assert result[0].before == before["source_links"][7]


@pytest.mark.parametrize("action", ["insert", "delete", "renumber"])
def test_position_normalization_does_not_invent_survivor_reorders(action):
    before = ordered_tasks()
    after = deepcopy(before)
    if action == "insert":
        after["tasks"][uid(99)] = {"task_id": uid(99), "duty_id": None, "name": "新首項", "description": None, "position": 0}
        for item in before["tasks"]:
            after["tasks"][item]["position"] += 1
    elif action == "delete":
        del after["tasks"][uid(100)]
        for row in after["tasks"].values():
            row["position"] -= 1
    else:
        for row in after["tasks"].values():
            row["position"] = row["position"] * 10 + 50
    result = compare(before, after)
    assert not any(item.kind in ("reorder", "update", "move") for item in result)
    assert len(result) == (0 if action == "renumber" else 1)


def test_real_reorder_is_separate_from_text_and_deterministic():
    before = ordered_tasks()
    after = deepcopy(before)
    after["tasks"][uid(100)]["position"] = 3
    for i in range(101, 104):
        after["tasks"][uid(i)]["position"] -= 1
    after["tasks"][uid(100)]["description"] = "排序同時補正文"
    result = compare(before, after)
    assert [(row.kind, row.identity) for row in result] == [("update", (uid(100),)), ("reorder", (uid(100),))]
    assert result == compare(before, after)


def test_move_plus_text_keeps_surviving_sibling_normalization_out_of_reorders():
    before = ordered_tasks()
    before["duties"][uid(2)] = {"duty_id": uid(2), "name": "另一組", "scope_text": None, "position": 0}
    after = deepcopy(before)
    after["tasks"][uid(100)].update(duty_id=uid(2), position=0, description="限新組已確認範圍")
    for i in range(101, 104):
        after["tasks"][uid(i)]["position"] -= 1
    result = compare(before, after)
    assert [(row.kind, row.identity) for row in result] == [("update", (uid(100),)), ("move", (uid(100),))]


def test_outcome_and_requirement_or_knowledge_and_skill_positions_are_separate():
    before = complete_domain()
    after = deepcopy(before)
    after["details"][uid(7)]["position"] = 100
    after["details"][uid(8)]["position"] = 101
    after["capabilities"][uid(9)]["position"] = 200
    assert compare(before, after) == ()


def test_relation_and_source_order_compare_only_surviving_members_of_same_target():
    before = complete_domain()
    before["source_links"].append({**before["source_links"][3], "source_link_id": uid(90),
        "source_ref": "another-source", "position": 1})
    after = deepcopy(before)
    for row in after["task_capabilities"]:
        if row["task_id"] == uid(3):
            row["position"] = 1 - row["position"]
    after["source_links"][3]["position"] = 1
    after["source_links"][-1]["position"] = 0
    result = compare(before, after)
    assert len(records(result, "task_capability", "reorder")) == 1
    assert len(records(result, "source_link", "reorder")) == 1
    assert not any(item.kind in ("link", "unlink", "update") for item in result)


def group_fixture(entity_kind):
    value = empty_domain("document-a", REVISION)
    if entity_kind in ("detail", "task_capability"):
        value["tasks"][uid(700)] = {"task_id": uid(700), "duty_id": None,
            "name": "上層任務", "description": None, "position": 0}
    group = {"collaborator": "collaborators", "duty": "duties", "task": "tasks", "detail": "details",
             "capability": "capabilities", "condition": "conditions", "task_capability": "task_capabilities",
             "source_link": "source_links"}[entity_kind]
    for i in range(3):
        identity = uid(100 + i)
        row = {"position": i}
        if entity_kind in ("collaborator", "duty"):
            row.update({f"{entity_kind}_id": identity, "name": "相同名稱", "scope_text": None})
        elif entity_kind == "task":
            row.update(task_id=identity, duty_id=None, name="相同名稱", description=None)
        elif entity_kind == "detail":
            row.update(detail_id=identity, task_id=uid(700), kind="requirement", text="必要要求")
        elif entity_kind == "capability":
            row.update(capability_id=identity, kind="knowledge", name="相同名稱", description=None)
        elif entity_kind == "condition":
            row.update(condition_id=identity, kind="schedule_travel", text="工作安排")
        elif entity_kind == "task_capability":
            value["capabilities"][identity] = {"capability_id": identity, "kind": "skill", "name": "技能",
                                               "description": None, "position": i}
            row.update(task_id=uid(700), capability_id=identity)
        else:
            row.update({**dict.fromkeys(SOURCE_COLUMNS), "profile_field": "purpose", "source_link_id": identity,
                        "source_ref": f"source-{i}", "basis_digest": "a" * 64})
        if isinstance(value[group], list):
            value[group].append(row)
        else:
            value[group][identity] = row
    return value, group


@pytest.mark.parametrize("entity_kind", ["collaborator", "duty", "task", "detail", "capability", "condition",
                                         "task_capability", "source_link"])
def test_every_fixed_group_detects_a_real_relative_reorder(entity_kind):
    before, group = group_fixture(entity_kind)
    after = deepcopy(before)
    rows = after[group] if isinstance(after[group], list) else list(after[group].values())
    rows[0]["position"], rows[1]["position"], rows[2]["position"] = 2, 0, 1
    result = compare(before, after)
    assert len(result) == 1 and result[0].kind == "reorder" and result[0].entity_kind == entity_kind
    assert result[0].identity == ((uid(700), uid(100)) if entity_kind == "task_capability" else (uid(100),))


@pytest.mark.parametrize("entity_kind", ["task_capability", "source_link"])
def test_unlink_first_association_does_not_label_remaining_associations_reordered(entity_kind):
    before, group = group_fixture(entity_kind)
    after = deepcopy(before)
    del after[group][0]
    for row in after[group]:
        row["position"] -= 1
    result = compare(before, after)
    assert len(result) == 1 and result[0].kind == "unlink" and result[0].entity_kind == entity_kind


def test_source_target_change_reports_exact_fields_and_union_of_affected_tasks():
    before = complete_domain()
    after = deepcopy(before)
    after["source_links"][3]["task_id"] = uid(4)
    result = compare(before, after)
    assert len(result) == 1 and result[0].kind == "update"
    assert result[0].changed_fields == ("task_id",) and result[0].affected_task_ids == (uid(3), uid(4))


def test_shared_capability_source_update_reports_all_linked_tasks():
    before = complete_domain()
    before["source_links"][5]["capability_id"] = uid(10)
    after = deepcopy(before)
    after["source_links"][5]["basis_digest"] = "b" * 64
    result = compare(before, after)
    assert len(result) == 1 and result[0].affected_task_ids == (uid(3), uid(4))


def test_reorder_can_change_relative_order_without_changing_its_raw_position():
    before = ordered_tasks(3)
    after = deepcopy(before)
    for row in after["tasks"].values():
        row["position"] = 2 - row["position"]
    result = compare(before, after)
    middle = next(row for row in result if row.identity == (uid(101),))
    assert middle.kind == "reorder" and middle.changed_fields == () and middle.before == middle.after
    assert not any(row.kind == "update" for row in result)


def test_large_unique_sibling_group_preserves_identity_matching():
    before = ordered_tasks(250)
    after = deepcopy(before)
    after["tasks"][uid(100)]["position"] = 249
    for i in range(101, 350):
        after["tasks"][uid(i)]["position"] -= 1
    result = compare(before, after)
    assert len(result) == 1 and result[0].kind == "reorder" and result[0].identity == (uid(100),)


@pytest.mark.parametrize("damage", ["document", "version", "duplicate", "unknown", "bad_lf"])
def test_invalid_or_cross_document_snapshots_are_rejected(damage):
    before = snapshot_from_domain(complete_domain())
    after = deepcopy(before)
    if damage == "document":
        after["document_id"] = "document-b"
    elif damage == "version":
        after["format_version"] = 2
    elif damage == "duplicate":
        after["tasks"].append(deepcopy(after["tasks"][0]))
    elif damage == "unknown":
        after["profile"]["invented"] = "不可靜默捨棄"
    else:
        after["tasks"][0]["description"] = "不能輸入\r\n非canonical文字"
    with pytest.raises(SnapshotValidationError):
        compare_snapshots(before, after)


def test_net_equal_endpoints_do_not_reconstruct_intermediate_edits():
    start = snapshot_from_domain(complete_domain())
    intermediate = deepcopy(start)
    intermediate["profile"]["purpose"] = "中途錯誤更改"
    assert compare_snapshots(start, intermediate)
    assert compare_snapshots(intermediate, start)
    assert compare_snapshots(start, deepcopy(start)) == ()
