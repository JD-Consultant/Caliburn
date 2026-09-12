"""Synthetic, in-memory business examples; these do not prove a database commit."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import itertools
import json

import pytest

from jd_relational.domain import CommandContext, DomainError, Ref, Source, build_candidate


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
