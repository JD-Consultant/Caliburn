"""Synthetic, in-memory business examples; these do not prove a database commit."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import itertools
import json

import pytest

from jd_relational.domain import CommandContext, DomainError, Ref, Source, build_candidate
from jd_relational.selection import Selection


@pytest.fixture
def world():
    snapshot = {
        "document_id": "doc", "revision": "r1",
        "profile": {"job_title": None, "organization_unit": None,
                    "employee_name": None, "reports_to": None, "purpose": None},
        "duties": {"d1": {"duty_id": "d1", "name": "維護", "scope_text": None, "position": 0}},
        "tasks": {
            "t1": {"task_id": "t1", "duty_id": "d1", "name": "客服", "description": "承諾處理客訴", "position": 0},
            "t2": {"task_id": "t2", "duty_id": "d1", "name": "月結", "description": "另一項有效工作", "position": 1},
        },
        "details": {
            "p1": {"detail_id": "p1", "task_id": "t1", "kind": "requirement", "text": "承諾立即解決", "position": 0},
            "p2": {"detail_id": "p2", "task_id": "t2", "kind": "requirement", "text": "核對月結", "position": 0},
        },
        "capabilities": {
            "k1": {"capability_id": "k1", "kind": "knowledge", "name": "異常狀態", "description": None, "position": 0},
            "s1": {"capability_id": "s1", "kind": "skill", "name": "客服協商", "description": None, "position": 0},
        },
        "task_capabilities": [
            {"task_id": "t1", "capability_id": "s1", "position": 0},
            {"task_id": "t2", "capability_id": "s1", "position": 0},
        ],
        "conditions": {"c1": {"condition_id": "c1", "kind": "shared_authority", "text": "自行承諾賠償", "position": 0}},
        "collaborators": {}, "source_links": [],
    }
    refs = {
        "tasks": Ref("doc", "r1", "container", "d1", child_kind="task"),
        "unassigned": Ref("doc", "r1", "container", child_kind="task"),
        "authority": Ref("doc", "r1", "container", child_kind="shared_authority"),
        "t1": Ref("doc", "r1", "task", "t1"),
        "t2": Ref("doc", "r1", "task", "t2"),
        "name": Ref("doc", "r1", "task", "t1", field="name"),
        "description": Ref("doc", "r1", "task", "t1", field="description"),
        "p1": Ref("doc", "r1", "detail", "p1"),
        "p2": Ref("doc", "r1", "detail", "p2"),
        "p1text": Ref("doc", "r1", "detail", "p1", field="text"),
        "k1": Ref("doc", "r1", "capability", "k1"),
        "s1": Ref("doc", "r1", "capability", "s1"),
        "c1": Ref("doc", "r1", "condition", "c1"),
    }
    ids = itertools.count(1)
    context = CommandContext("doc", "r1", refs,
                             {s: Source("doc") for s in ("qa1", "qa2", "qa3")},
                             lambda: f"new-{next(ids)}")
    return snapshot, context


def create(**overrides):
    args = {"container_ref": "tasks", "after_ref": None, "name": "異常診斷",
            "description": "辨識前端異常並提供診斷結果", "basis_refs": ["qa1"],
            "outcomes": [{"text": "診斷資訊", "basis_refs": ["qa2"]},
                         {"text": "轉交資訊", "basis_refs": []}],
            "requirements": [{"text": "區分已知與待驗證假設", "basis_refs": []}],
            "capabilities": [{"capability_ref": "k1", "basis_refs": ["qa3"]}]}
    args.update(overrides)
    return {"tool": "jd_create_task", "arguments": args}


def revise(*changes):
    return {"tool": "jd_revise_work", "arguments": {"changes": list(changes)}}


def field(target, text, sources=()):
    return {"kind": "set_field", "target_field_ref": target, "text": text, "basis_refs": list(sources)}


def detail(text, after=None, task="t1", kind="requirement", sources=()):
    return {"kind": "add_task_detail", "task_ref": task, "detail_kind": kind,
            "after_ref": after, "text": text, "basis_refs": list(sources)}


def relation(mode, capability="s1", sources=()):
    return {"kind": "set_task_capability", "task_ref": "t1", "capability_ref": capability,
            "mode": mode, "basis_refs": list(sources)}


def reject_unchanged(world, command, code="invalid_input"):
    snapshot, context = world
    before = deepcopy(snapshot)
    with pytest.raises(DomainError) as error:
        build_candidate(snapshot, command, context)
    assert error.value.code == code
    assert snapshot == before


def test_complete_create_and_each_source_belongs_to_its_target(world):
    snapshot, context = world
    before = deepcopy(snapshot)
    result = build_candidate(snapshot, create(), context)
    task_id, = result["tasks"].keys() - snapshot["tasks"].keys()
    task = result["tasks"][task_id]
    assert (task["name"], task["description"], task["duty_id"], task["position"]) == (
        "異常診斷", "辨識前端異常並提供診斷結果", "d1", 0)
    details = [row for row in result["details"].values() if row["task_id"] == task_id]
    assert [(row["kind"], row["text"], row["position"]) for row in details] == [
        ("outcome", "診斷資訊", 0), ("outcome", "轉交資訊", 1), ("requirement", "區分已知與待驗證假設", 0)]
    links = {link["source_ref"]: link for link in result["source_links"]}
    assert links["qa1"]["task_id"] == task_id
    assert links["qa2"]["detail_id"] == details[0]["detail_id"]
    assert (links["qa3"]["linked_task_id"], links["qa3"]["linked_capability_id"]) == (task_id, "k1")
    assert result["revision"] == "r1"  # Candidate building cannot advance persisted revision.
    assert snapshot == before


def test_partial_task_preserves_unknown_and_unassigned(world):
    snapshot, context = world
    result = build_candidate(snapshot, create(container_ref="unassigned", name=None,
        description="  僅知工作內容😀\r\n保留空間  ", outcomes=[], requirements=[], capabilities=[], basis_refs=[]), context)
    task_id, = result["tasks"].keys() - snapshot["tasks"].keys()
    assert result["tasks"][task_id] == {"document_id": "doc", "task_id": task_id,
        "duty_id": None, "name": None, "description": "  僅知工作內容😀\n保留空間  ", "position": 0}


@pytest.mark.parametrize("overrides", [
    {"name": " \t", "description": None},
    {"outcomes": [{"text": "有效", "basis_refs": []}, {"text": " \r\n", "basis_refs": []}]},
    {"capabilities": [{"capability_ref": "k1", "basis_refs": []}] * 2},
    {"capabilities": [{"capability_ref": "p1", "basis_refs": []}]},
    {"outcomes": [{"text": "甲", "basis_refs": []}] * 129},
    {"description": "甲" * 21846},
    {"description": "broken\ud800"},
])
def test_create_invalid_child_text_ref_or_limit_never_leaves_shell(world, overrides):
    reject_unchanged(world, create(**overrides))


def test_all_six_variants_correct_one_misunderstanding_together(world):
    snapshot, context = world
    result = build_candidate(snapshot, revise(
        field("description", "僅作技術診斷；客戶承諾交窗口處理", ["qa1"]),
        {"kind": "remove_task_detail", "detail_ref": "p1"},
        detail("無法確認根因時，区分觀察與假設", sources=["qa2"]),
        relation("unlink"),
        {"kind": "remove_condition", "condition_ref": "c1"},
        {"kind": "add_condition", "container_ref": "authority", "after_ref": None,
         "text": "賠償由主管核定", "basis_refs": []},
    ), context)
    assert result["tasks"]["t1"]["description"].startswith("僅作技術診斷")
    assert "p1" not in result["details"] and "c1" not in result["conditions"]
    assert result["tasks"]["t2"] == snapshot["tasks"]["t2"]
    assert result["details"]["p2"] == snapshot["details"]["p2"]
    assert result["capabilities"] == snapshot["capabilities"]
    assert result["task_capabilities"] == [snapshot["task_capabilities"][1]]
    assert any(row["text"] == "賠償由主管核定" for row in result["conditions"].values())


def test_final_row_invariant_allows_name_only_to_description_only(world):
    snapshot, context = world
    snapshot["tasks"]["t1"]["description"] = None
    result = build_candidate(snapshot, revise(field("name", " \t"), field("description", "確切本人工作")), context)
    assert result["tasks"]["t1"]["name"] is None
    assert result["tasks"]["t1"]["description"] == "確切本人工作"


@pytest.mark.parametrize("changes", [
    [],
    [field("name", "甲"), field("name", "乙")],
    [field("p1text", "甲"), {"kind": "remove_task_detail", "detail_ref": "p1"}],
    [relation("link"), relation("unlink")],
    [relation("link"), relation("link")],
    [detail("甲", after="p1"), {"kind": "remove_task_detail", "detail_ref": "p1"}],
    [field("description", "先正確"), detail(" \n")],
    [field("name", None), field("description", None)],
    [detail("甲", after="p2")],
    [detail("甲", after="p1", kind="outcome")],
    [relation("unlink", sources=["qa1"])],
    [{"kind": "remove_task_detail", "detail_ref": "p1"}] * 2,
    [{"kind": "add_task", "name": "超出範圍"}],
    [detail("甲")] * 65,
])
def test_atomic_correction_rejects_conflicts_and_invalid_final_state(world, changes):
    reject_unchanged(world, revise(*changes))


@pytest.mark.parametrize("anchor", [None, "p1"])
def test_same_anchor_insertions_keep_input_order(world, anchor):
    snapshot, context = world
    result = build_candidate(snapshot, revise(detail("第一", anchor), detail("第二", anchor)), context)
    rows = sorted((r for r in result["details"].values() if r["task_id"] == "t1"), key=lambda r: r["position"])
    expected = ["第一", "第二", "承諾立即解決"] if anchor is None else ["承諾立即解決", "第一", "第二"]
    assert [row["text"] for row in rows] == expected
    assert [row["position"] for row in rows] == [0, 1, 2]


@pytest.mark.parametrize("ref_patch,code", [
    ({"document_id": "other"}, "invalid_input"),
    ({"revision": "r0"}, "stale_view"),
    ({"entity_id": "deleted"}, "target_missing"),
    ({"kind": "capability"}, "target_missing"),
])
def test_ref_identity_scope_and_exact_base_are_app_validated(world, ref_patch, code):
    snapshot, context = world
    context.refs["description"] = replace(context.refs["description"], **ref_patch)
    reject_unchanged((snapshot, context), revise(field("description", "修正")), code)


@pytest.mark.parametrize("source", [Source("other"), Source("doc", False), None])
def test_invalid_or_unreadable_source_rejects_complete_command(world, source):
    snapshot, context = world
    if source is None:
        del context.sources["qa2"]
    else:
        context.sources["qa2"] = source
    reject_unchanged((snapshot, context), create())


def test_empty_basis_keeps_old_link_and_multi_field_basis_merges_at_final_value(world):
    snapshot, context = world
    snapshot["source_links"] = [{"source_link_id": "old", "document_id": "doc", "task_id": "t1",
                                  "source_ref": "qa3", "basis_digest": "a" * 64, "position": 0}]
    changed = build_candidate(snapshot, revise(field("description", "先修正")), context)
    assert changed["source_links"] == snapshot["source_links"]
    result = build_candidate(snapshot, revise(field("name", "診斷", ["qa1"]),
                                              field("description", "技術診斷", ["qa2", "qa1"])), context)
    links = result["source_links"]
    assert [link["source_ref"] for link in links] == ["qa3", "qa1", "qa2"]
    expected = hashlib.sha256(json.dumps({"name": "診斷", "description": "技術診斷"},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert links[0] == snapshot["source_links"][0]
    assert links[1]["basis_digest"] == links[2]["basis_digest"] == expected


def test_explicit_relink_keeps_identity_and_idempotent_candidate(world):
    snapshot, context = world
    command = revise(field("name", "客服", ["qa1"]))
    first = build_candidate(snapshot, command, context)
    second = build_candidate(first, command, context)
    assert first == second


def test_relation_basis_uses_final_task_and_capability_text_only_when_explicit(world):
    snapshot, context = world
    context.refs["skill_name"] = Ref("doc", "r1", "capability", "s1", field="name")
    first = build_candidate(snapshot, revise(relation("link", sources=["qa1"])), context)
    old_link = deepcopy(first["source_links"][0])
    without_relink = build_candidate(first, revise(field("description", "技術診斷")), context)
    assert without_relink["source_links"][0] == old_link
    result = build_candidate(first, revise(relation("link", sources=["qa1"]),
        field("description", "技術診斷"), field("skill_name", "診斷溝通")), context)
    expected = hashlib.sha256(json.dumps({
        "task": {"name": "客服", "description": "技術診斷"},
        "capability": {"kind": "skill", "name": "診斷溝通", "description": None}},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert result["source_links"][0]["source_link_id"] == old_link["source_link_id"]
    assert result["source_links"][0]["basis_digest"] == expected != old_link["basis_digest"]


def test_two_opaque_refs_for_one_field_still_conflict(world):
    snapshot, context = world
    context.refs["name_alias"] = context.refs["name"]
    reject_unchanged((snapshot, context), revise(field("name", "甲"), field("name_alias", "乙")))


def test_removed_detail_relation_condition_sources_are_removed_not_reassigned(world):
    snapshot, context = world
    snapshot["source_links"] = [
        {"source_link_id": "a", "detail_id": "p1", "source_ref": "qa1", "basis_digest": "a" * 64, "position": 0},
        {"source_link_id": "b", "linked_task_id": "t1", "linked_capability_id": "s1", "source_ref": "qa2", "basis_digest": "b" * 64, "position": 0},
        {"source_link_id": "c", "condition_id": "c1", "source_ref": "qa3", "basis_digest": "c" * 64, "position": 0},
    ]
    result = build_candidate(snapshot, revise(
        {"kind": "remove_task_detail", "detail_ref": "p1"}, relation("unlink"),
        {"kind": "remove_condition", "condition_ref": "c1"}), context)
    assert result["source_links"] == []
    assert result["capabilities"] == snapshot["capabilities"]


def test_relation_link_unlink_are_idempotent_sets(world):
    snapshot, context = world
    assert build_candidate(snapshot, revise(relation("link")), context) == snapshot
    assert build_candidate(snapshot, revise(relation("unlink", "k1")), context) == snapshot


def test_appending_capability_normalizes_sparse_positions_without_reordering(world):
    snapshot, context = world
    snapshot["task_capabilities"][0]["position"] = 20
    result = build_candidate(snapshot, revise(relation("link", "k1")), context)
    rows = sorted((row for row in result["task_capabilities"] if row["task_id"] == "t1"),
                  key=lambda row: (row["position"], row["capability_id"]))
    assert [(row["capability_id"], row["position"]) for row in rows] == [("s1", 0), ("k1", 1)]


def test_appending_source_normalizes_sparse_positions_without_reordering(world):
    snapshot, context = world
    snapshot["source_links"] = [{"source_link_id": "old", "task_id": "t1", "source_ref": "qa1",
                                  "basis_digest": "a" * 64, "position": 20}]
    result = build_candidate(snapshot, revise(field("description", "修正", ["qa2"])), context)
    rows = sorted(result["source_links"], key=lambda row: (row["position"], row["source_link_id"]))
    assert [(row["source_ref"], row["position"]) for row in rows] == [("qa1", 0), ("qa2", 1)]
    assert rows[0]["basis_digest"] == "a" * 64


def test_idempotent_existing_link_does_not_reposition_sparse_group(world):
    snapshot, context = world
    snapshot["task_capabilities"][0]["position"] = 20
    assert build_candidate(snapshot, revise(relation("link")), context) == snapshot
    snapshot["source_links"] = [{"source_link_id": "old", "task_id": "t1", "source_ref": "qa1",
                                  "basis_digest": "a" * 64, "position": 20}]
    result = build_candidate(snapshot, revise(field("description", "修正", ["qa1"])), context)
    assert result["source_links"][0]["position"] == 20


def test_payload_limit_rejects_before_mutation(world):
    # Each field is within 64 KiB; the entire indivisible operation exceeds 1 MiB.
    reject_unchanged(world, revise(*(detail("x" * 65536) for _ in range(17))))


def test_new_identity_collision_rejects_without_overwriting_existing_work(world):
    snapshot, context = world
    reject_unchanged((snapshot, replace(context, new_id=lambda: "t1")), create())


@pytest.fixture
def editing_world(world):
    snapshot, context = world
    snapshot["duties"]["d2"] = {"duty_id": "d2", "name": "支援", "scope_text": "另有約定", "position": 10}
    snapshot["tasks"]["t3"] = {"task_id": "t3", "duty_id": None, "name": "獨立工作", "description": None, "position": 20}
    snapshot["collaborators"]["co1"] = {"collaborator_id": "co1", "name": "窗口", "scope_text": None, "position": 0}
    context.refs.update({
        "duties": Ref("doc", "r1", "container", child_kind="duty"),
        "collaborators": Ref("doc", "r1", "container", child_kind="collaborator"),
        "knowledge": Ref("doc", "r1", "container", child_kind="knowledge"),
        "skills": Ref("doc", "r1", "container", child_kind="skill"),
        "outcomes": Ref("doc", "r1", "container", "t1", child_kind="outcome"),
        "requirements": Ref("doc", "r1", "container", "t1", child_kind="requirement"),
        "other_requirements": Ref("doc", "r1", "container", "t2", child_kind="requirement"),
        "schedule": Ref("doc", "r1", "container", child_kind="schedule_travel"),
        "destination": Ref("doc", "r1", "container", "d2", child_kind="task"),
        "d1": Ref("doc", "r1", "duty", "d1"),
        "d2": Ref("doc", "r1", "duty", "d2"),
        "d1scope": Ref("doc", "r1", "duty", "d1", field="scope_text"),
        "d2scope": Ref("doc", "r1", "duty", "d2", field="scope_text"),
        "d2name": Ref("doc", "r1", "duty", "d2", field="name"),
        "t3": Ref("doc", "r1", "task", "t3"),
        "t3name": Ref("doc", "r1", "task", "t3", field="name"),
        "title": Ref("doc", "r1", "profile", field="job_title"),
        "co1": Ref("doc", "r1", "collaborator", "co1"),
    })
    return snapshot, context


def command(tool, **arguments):
    return {"tool": f"jd_{tool}", "arguments": arguments}


def insert(kind, container, **values):
    return command("insert_item", item={"kind": kind, "container_ref": container,
        "after_ref": None, "basis_refs": [], **values})


def test_single_field_and_relation_tools_share_revision_semantics(editing_world):
    snapshot, context = editing_world
    direct = command("set_text", target_field_ref="description", text="  完整\r\n全文  ", basis_refs=[])
    assert build_candidate(snapshot, direct, context) == build_candidate(snapshot,
        revise(field("description", "  完整\r\n全文  ")), context)
    direct = command("set_task_capability", task_ref="t1", capability_ref="s1", mode="unlink", basis_refs=[])
    assert build_candidate(snapshot, direct, context) == build_candidate(snapshot, revise(relation("unlink")), context)


@pytest.mark.parametrize("kind,container,values,collection,row_kind", [
    ("duty", "duties", {"name": None, "scope_text": "未知名稱但範圍已知"}, "duties", None),
    ("collaborator", "collaborators", {"name": None, "scope_text": "負責對外聯繫"}, "collaborators", None),
    ("knowledge", "knowledge", {"name": "異常狀態", "description": "同名但不同內涵"}, "capabilities", "knowledge"),
    ("skill", "skills", {"name": None, "description": "逐步診斷"}, "capabilities", "skill"),
    ("outcome", "outcomes", {"text": "診斷結果"}, "details", "outcome"),
    ("requirement", "requirements", {"text": "先確認安全隔離"}, "details", "requirement"),
    ("condition", "authority", {"text": "明確權限"}, "conditions", "shared_authority"),
])
def test_insert_all_seven_variants_with_full_known_content(editing_world, kind, container, values, collection, row_kind):
    snapshot, context = editing_world
    before = deepcopy(snapshot)
    result = build_candidate(snapshot, insert(kind, container, **values), context)
    identity, = result[collection].keys() - snapshot[collection].keys()
    assert all(result[collection][identity][key] == value for key, value in values.items())
    if row_kind:
        assert result[collection][identity]["kind"] == row_kind
    if collection == "details":
        assert result[collection][identity]["task_id"] == "t1"
    assert result[collection][identity]["position"] == 0
    assert snapshot == before


@pytest.mark.parametrize("item", [
    insert("knowledge", "skills", name="錯組", description=None),
    insert("outcome", "requirements", text="不自動改kind"),
    insert("condition", "duties", text="錯容器"),
    insert("requirement", "requirements", text=" \n"),
    insert("duty", "duties", name=None, scope_text=None),
    insert("requirement", "requirements", after_ref="p2", text="錯task"),
    insert("task", "tasks", name="不得繞過完整task", description=None),
])
def test_insert_invalid_kind_container_or_content_is_atomic(editing_world, item):
    reject_unchanged(editing_world, item)


def test_selection_replaces_only_captured_occurrence_with_app_offsets(editing_world):
    snapshot, context = editing_world
    snapshot["tasks"]["t1"]["description"] = "甲😀按月檢查\n按月回報"
    context = replace(context, selections={"sel": Selection("description",
        snapshot["tasks"]["t1"]["description"], 3, 5, "按月")})
    result = build_candidate(snapshot, command("replace_selection", selection_ref="sel",
        replacement_text="每季", basis_refs=["qa1"]), context)
    assert result["tasks"]["t1"]["description"] == "甲😀每季檢查\n按月回報"
    assert result["source_links"][0]["task_id"] == "t1"


@pytest.mark.parametrize("selection,token,replacement,code", [
    (Selection("description", "過時內容", 0, 1, "過"), "sel", "新", "stale_view"),
    (Selection("description", "甲😀按月", 1, 2, "",), "sel", "新", "invalid_input"),
    (Selection("t1", "甲😀按月", 0, 1, "甲"), "sel", "新", "invalid_input"),
    (Selection("description", "甲😀按月", 0, 1, "甲"), "description", "新", "invalid_input"),
    (Selection("description", "甲😀按月", 0, 0, ""), "sel", "新", "invalid_input"),
])
def test_selection_invalid_capture_does_not_fall_back_to_full_field(editing_world, selection, token, replacement, code):
    snapshot, context = editing_world
    snapshot["tasks"]["t1"]["description"] = "甲😀按月"
    context = replace(context, selections={"sel": selection})
    reject_unchanged((snapshot, context), command("replace_selection", selection_ref=token,
        replacement_text=replacement, basis_refs=[]), code)


def test_selection_empty_replacement_uses_final_whole_item_constraint(editing_world):
    snapshot, context = editing_world
    text = snapshot["tasks"]["t1"]["description"]
    context = replace(context, selections={"sel": Selection("description", text, 0, len(text), text)})
    result = build_candidate(snapshot, command("replace_selection", selection_ref="sel", replacement_text="", basis_refs=[]), context)
    assert result["tasks"]["t1"]["description"] is None
    assert result["tasks"]["t1"]["name"] == "客服"
    snapshot["tasks"]["t1"]["name"] = None
    reject_unchanged((snapshot, context), command("replace_selection", selection_ref="sel", replacement_text="", basis_refs=[]))


def delete(target, changes=()):
    return command("delete_item", target_ref=target, content_changes=list(changes))


def move(target, destination, after=None, changes=()):
    return command("move_item", target_ref=target, destination_container_ref=destination,
                   after_ref=after, content_changes=list(changes))


def source_link(identity, **target):
    return {"source_link_id": identity, "source_ref": "qa1", "basis_digest": "a" * 64, "position": 0, **target}


def test_delete_duty_keeps_tasks_and_atomically_adds_correct_outcome_requirement(editing_world):
    snapshot, context = editing_world
    snapshot["duties"]["d1"]["scope_text"] = "先安全隔離；交付維修紀錄"
    snapshot["source_links"] = [source_link("duty-source", duty_id="d1"), source_link("task-source", task_id="t1")]
    before = deepcopy(snapshot)
    result = build_candidate(snapshot, delete("d1", [
        detail("先安全隔離"), detail("維修紀錄", kind="outcome"),
        field("description", "在本人約定範圍內診斷")]), context)
    assert "d1" not in result["duties"]
    assert result["tasks"].keys() == snapshot["tasks"].keys()
    rows = sorted(result["tasks"].values(), key=lambda row: row["position"])
    assert [(row["task_id"], row["duty_id"], row["position"]) for row in rows] == [
        ("t3", None, 0), ("t1", None, 1), ("t2", None, 2)]
    new_details = [row for key, row in result["details"].items() if key not in snapshot["details"]]
    assert {(row["kind"], row["text"]) for row in new_details} == {
        ("requirement", "先安全隔離"), ("outcome", "維修紀錄")}
    assert result["task_capabilities"] == snapshot["task_capabilities"]
    assert result["source_links"] == [snapshot["source_links"][1]]
    assert snapshot == before


@pytest.mark.parametrize("changes", [
    [field("t3name", "無關工作")], [detail("無關要求", task="t3")],
    [field("d1scope", "即將刪除的目標")], [field("title", "無關全職位")],
    [relation("unlink")], [detail("有效"), detail(" \n")],
])
def test_delete_duty_scope_or_late_invalid_change_never_loses_original_scope(editing_world, changes):
    reject_unchanged(editing_world, delete("d1", changes))


def test_delete_task_removes_owned_rows_and_sources_but_keeps_shared_definition(editing_world):
    snapshot, context = editing_world
    snapshot["source_links"] = [source_link("task-source", task_id="t1"),
        source_link("detail-source", detail_id="p1"),
        source_link("relation-source", linked_task_id="t1", linked_capability_id="s1"),
        source_link("shared-source", capability_id="s1")]
    result = build_candidate(snapshot, delete("t1"), context)
    assert "t1" not in result["tasks"] and "p1" not in result["details"]
    assert result["details"]["p2"] == snapshot["details"]["p2"]
    assert result["tasks"]["t2"]["position"] == 0
    assert result["capabilities"] == snapshot["capabilities"]
    assert result["task_capabilities"] == [snapshot["task_capabilities"][1]]
    assert result["source_links"] == [snapshot["source_links"][3]]


def test_used_capability_delete_returns_real_issued_target_reference(editing_world):
    snapshot, context = editing_world
    with pytest.raises(DomainError) as error:
        build_candidate(snapshot, delete("s1"), context)
    assert error.value.code == "dependent_items"
    assert "s1" in error.value.refs
    assert all(ref in context.refs for ref in error.value.refs)
    reject_unchanged(editing_world, delete("s1"), "dependent_items")


@pytest.mark.parametrize("target,collection", [("p1", "details"), ("c1", "conditions"), ("co1", "collaborators"), ("k1", "capabilities")])
def test_delete_independent_item_removes_only_its_own_source(editing_world, target, collection):
    snapshot, context = editing_world
    kind = context.refs[target].kind
    snapshot["source_links"] = [source_link("own", **{f"{kind}_id": target}), source_link("other", task_id="t2")]
    result = build_candidate(snapshot, delete(target), context)
    assert target not in result[collection]
    assert result["source_links"] == [snapshot["source_links"][1]]


@pytest.mark.parametrize("operation", [delete("t1", [field("description", "不得搭配")]), delete("name"),
    move("t1", "tasks", changes=[field("description", "同容器只是重排")]),
    move("k1", "skills"), move("p1", "other_requirements"), move("c1", "schedule"),
    move("t1", "destination", after="t1"), move("t1", "destination", after="t3"),
    move("t1", "destination", changes=[field("t3name", "無關")]),
    move("t1", "destination", changes=[field("d2name", "摘要以外")]),
    move("t1", "destination", changes=[relation("unlink")]),
    move("t1", "destination", changes=[field("description", "有效"), detail(" \n")]),
])
def test_structural_changes_reject_wrong_scope_kind_or_self_anchor_atomically(editing_world, operation):
    reject_unchanged(editing_world, operation)


def test_cross_duty_move_keeps_identity_components_and_sources_with_scoped_revision(editing_world):
    snapshot, context = editing_world
    snapshot["source_links"] = [source_link("task-source", task_id="t1"), source_link("detail-source", detail_id="p1")]
    result = build_candidate(snapshot, move("t1", "destination", changes=[
        field("description", "仍限原服務約定"), field("d1scope", "移出此工作"),
        field("d2scope", "包含約定支援"), detail("必要交接", after="p1")]), context)
    assert result["tasks"]["t1"]["duty_id"] == "d2"
    assert result["tasks"]["t1"]["description"] == "仍限原服務約定"
    assert result["tasks"]["t2"]["duty_id"] == "d1" and result["tasks"]["t2"]["position"] == 0
    assert result["details"]["p1"] == snapshot["details"]["p1"]
    assert result["task_capabilities"] == snapshot["task_capabilities"]
    assert result["source_links"] == snapshot["source_links"]


def test_task_can_move_to_unassigned_without_inheriting_or_copying_scope(editing_world):
    snapshot, context = editing_world
    result = build_candidate(snapshot, move("t1", "unassigned", after="t3"), context)
    assert result["tasks"]["t1"] == {**snapshot["tasks"]["t1"], "duty_id": None, "position": 1}
    assert result["tasks"]["t3"]["position"] == 0
    assert result["duties"] == snapshot["duties"]


@pytest.mark.parametrize("target,container,anchor,collection,expected", [
    ("t2", "tasks", None, "tasks", ["t2", "t1"]),
    ("d1", "duties", "d2", "duties", ["d2", "d1"]),
])
def test_same_container_reorder_preserves_stable_ids(editing_world, target, container, anchor, collection, expected):
    snapshot, context = editing_world
    result = build_candidate(snapshot, move(target, container, anchor), context)
    rows = [row for row in result[collection].values() if collection != "tasks" or row["duty_id"] == "d1"]
    id_column = "task_id" if collection == "tasks" else "duty_id"
    assert [row[id_column] for row in sorted(rows, key=lambda row: row["position"])] == expected
    assert result["details"] == snapshot["details"]
    assert result["capabilities"] == snapshot["capabilities"]


def test_blank_document_can_build_all_six_chapters_and_continue_editing(world):
    original, context = world
    snapshot = {"document_id": "doc", "revision": "r1", "profile": deepcopy(original["profile"]),
        "duties": {}, "tasks": {}, "details": {}, "capabilities": {}, "conditions": {},
        "collaborators": {}, "task_capabilities": [], "source_links": []}
    context = replace(context, refs={})
    for token, child in {"duties": "duty", "collaborators": "collaborator", "knowledge": "knowledge",
                         "skills": "skill", "unassigned": "task"}.items():
        context.refs[token] = Ref("doc", "r1", "container", child_kind=child)
    for field_name, text in {"job_title": "維護工程師", "organization_unit": "技術組", "employee_name": "合成員工",
                             "reports_to": "組長", "purpose": "維持约定服務範圍內系統運作"}.items():
        context.refs[field_name] = Ref("doc", "r1", "profile", field=field_name)
        snapshot = build_candidate(snapshot, command("set_text", target_field_ref=field_name, text=text, basis_refs=[]), context)
    snapshot = build_candidate(snapshot, insert("collaborator", "collaborators", name="服務窗口", scope_text="對外承諾"), context)
    snapshot = build_candidate(snapshot, insert("duty", "duties", name="系統維護", scope_text="依服務約定"), context)
    duty_id, = snapshot["duties"]
    context.refs["tasks"] = Ref("doc", "r1", "container", duty_id, child_kind="task")
    snapshot = build_candidate(snapshot, insert("knowledge", "knowledge", name="系統異常", description="理解失敗狀態"), context)
    knowledge_id, = snapshot["capabilities"]
    context.refs["k1"] = Ref("doc", "r1", "capability", knowledge_id)
    snapshot = build_candidate(snapshot, insert("skill", "skills", name="診斷", description="逐步定位問題"), context)
    skill_id, = snapshot["capabilities"].keys() - {knowledge_id}
    context.refs["skill"] = Ref("doc", "r1", "capability", skill_id)
    snapshot = build_candidate(snapshot, create(capabilities=[
        {"capability_ref": "k1", "basis_refs": []}, {"capability_ref": "skill", "basis_refs": []}]), context)
    task_id, = snapshot["tasks"]
    context.refs["task"] = Ref("doc", "r1", "task", task_id)
    context.refs["body"] = Ref("doc", "r1", "task", task_id, field="description")
    for kind, text in {"work_environment": "本機作業", "schedule_travel": "依排定時程",
                       "shared_authority": "依授權處理", "shared_collaboration": "與服務窗口交接",
                       "qualification": "具備約定專業資格"}.items():
        context.refs[kind] = Ref("doc", "r1", "container", child_kind=kind)
        snapshot = build_candidate(snapshot, insert("condition", kind, text=text), context)
    assert all(snapshot["profile"].values())
    assert len(snapshot["collaborators"]) == len(snapshot["duties"]) == len(snapshot["tasks"]) == 1
    assert {row["kind"] for row in snapshot["details"].values()} == {"outcome", "requirement"}
    assert {row["kind"] for row in snapshot["capabilities"].values()} == {"knowledge", "skill"}
    assert len(snapshot["conditions"]) == 5 and len(snapshot["task_capabilities"]) == 2
    # App fixture refs are explicit; this sequence constructs candidates, never saves or issues production refs.
    snapshot = build_candidate(snapshot, move("task", "unassigned", changes=[
        field("body", "仍按約定服務範圍診斷與交接")]), context)
    assert snapshot["tasks"][task_id]["duty_id"] is None
    snapshot = build_candidate(snapshot, move("task", "tasks"), context)
    assert snapshot["tasks"][task_id]["duty_id"] == duty_id
    snapshot = build_candidate(snapshot, command("set_task_capability", task_ref="task", capability_ref="skill",
        mode="unlink", basis_refs=[]), context)
    snapshot = build_candidate(snapshot, delete("skill"), context)
    assert skill_id not in snapshot["capabilities"] and knowledge_id in snapshot["capabilities"]
    assert snapshot["revision"] == "r1"
