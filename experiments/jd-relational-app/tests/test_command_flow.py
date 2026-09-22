"""An employee and either model transport reach the identical business candidate."""

from copy import deepcopy
from dataclasses import replace
from itertools import count
import json

import pytest

from jd_relational.domain import CommandContext, DomainError, Ref, Source
from jd_relational.application import prepare_edit as build_candidate
from jd_relational.selection import Selection
from jd_relational.transport import manual_command, model_command


def baseline():
    snapshot = {
        "document_id": "scope-a", "revision": "base-1",
        "profile": {"job_title": "前端工程師", "organization_unit": None,
                    "employee_name": None, "reports_to": None, "purpose": None},
        "duties": {}, "tasks": {}, "details": {}, "conditions": {}, "collaborators": {},
        "capabilities": {
            "skill-a": {"capability_id": "skill-a", "kind": "skill", "name": "問題診斷",
                        "description": "透過重現與介面資料辨識異常", "position": 0},
            "skill-b": {"capability_id": "skill-b", "kind": "skill", "name": "問題診斷",
                        "description": "辨識鍵盤操作及可用性障礙", "position": 1},
        },
        "task_capabilities": [], "source_links": [],
    }
    ids = count(1)
    context = CommandContext("scope-a", "base-1", {
        "unassigned": Ref("scope-a", "base-1", "container", child_kind="task"),
        "picked-skill": Ref("scope-a", "base-1", "capability", "skill-a"),
    }, {"source-qa": Source("scope-a")}, lambda: f"app-{next(ids)}")
    return snapshot, context


def create_arguments():
    return {"container_ref": "unassigned", "after_ref": None, "name": None,
            "description": "  處理約定範圍的異常😀\r\n時程仍待確認。  ", "basis_refs": ["source-qa"],
            "outcomes": [{"text": "可回查的診斷", "basis_refs": []}, {"text": "可接續處理的交接資料", "basis_refs": []}],
            "requirements": [{"text": "未確認不得宣稱已解決", "basis_refs": []}],
            "capabilities": [{"capability_ref": "picked-skill", "basis_refs": []}]}


def model_arguments(value):
    if isinstance(value, list):
        return [model_arguments(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        result["basis_evidence_keys" if key == "basis_refs" else key] = model_arguments(item)
    return result


def test_manual_and_model_create_full_task_then_correct_without_losing_children():
    outputs = []
    for mode in ("manual", "openai-json", "anthropic-object"):
        snapshot, context = baseline()
        original = deepcopy(snapshot)

        def adapt(tool, payload):
            if mode == "manual":
                return manual_command({"tool": tool, "arguments": payload})
            return model_command(tool, json.dumps(payload) if mode == "openai-json" else payload)

        payload = create_arguments() if mode == "manual" else model_arguments(create_arguments())
        candidate = build_candidate(snapshot, adapt("jd_create_task", payload), context)
        assert snapshot == original
        assert candidate["capabilities"] == snapshot["capabilities"]
        task_id, = candidate["tasks"]
        assert candidate["tasks"][task_id]["name"] is None
        assert candidate["tasks"][task_id]["description"] == "  處理約定範圍的異常😀\n時程仍待確認。  "
        assert [row["capability_id"] for row in candidate["task_capabilities"]] == ["skill-a"]
        # A separately supplied, trusted base stands in for a later read. No DB save is claimed.
        next_base = deepcopy(candidate)
        next_base["revision"] = "base-2"
        next_context = replace(context, base_revision="base-2", refs={
            "description-now": Ref("scope-a", "base-2", "task", task_id, field="description")})
        correction = {"changes": [{"kind": "set_field", "target_field_ref": "description-now",
                                  "text": "只有 B 系統有月檢；A 系統僅提供交付後缺陷修正。", "basis_refs": []}]}
        correction_payload = correction if mode == "manual" else model_arguments(correction)
        revised = build_candidate(next_base, adapt("jd_revise_work", correction_payload), next_context)
        assert revised["details"] == next_base["details"]
        assert revised["task_capabilities"] == next_base["task_capabilities"]
        assert revised["source_links"] == next_base["source_links"]  # Old basis retained, not silently refreshed.
        outputs.append(revised)
    assert outputs[0] == outputs[1] == outputs[2]


@pytest.mark.parametrize("mode", ["manual", "model"])
def test_valid_first_change_and_stale_second_reference_return_no_candidate(mode):
    snapshot, context = baseline()
    candidate = build_candidate(snapshot, model_command("jd_create_task", model_arguments(create_arguments())), context)
    task_id, = candidate["tasks"]
    context = replace(context, refs={
        "current": Ref("scope-a", "base-1", "task", task_id, field="name"),
        "stale": Ref("scope-a", "older", "task", task_id, field="description"),
    })
    payload = {"changes": [
        {"kind": "set_field", "target_field_ref": "current", "text": "有意義名稱", "basis_refs": []},
        {"kind": "set_field", "target_field_ref": "stale", "text": "不得套用", "basis_refs": []},
    ]}
    command = (manual_command({"tool": "jd_revise_work", "arguments": payload}) if mode == "manual"
               else model_command("jd_revise_work", json.dumps(model_arguments(payload))))
    before = deepcopy(candidate)
    with pytest.raises(DomainError) as error:
        build_candidate(candidate, command, context)
    assert error.value.code == "stale_view"
    assert candidate == before


def test_monthly_check_correction_preserves_other_valid_and_low_frequency_work():
    snapshot, context = baseline()
    snapshot["tasks"] = {
        "monthly": {"task_id": "monthly", "duty_id": None, "name": "定期檢查", "description": "A、B 系統都有月檢", "position": 0},
        "defects": {"task_id": "defects", "duty_id": None, "name": "交付後缺陷修正", "description": "A 系統交付後，處理約定範圍的缺陷", "position": 1},
        "rare": {"task_id": "rare", "duty_id": None, "name": "上線異常", "description": "低頻但重要：釐清上線異常並轉交負責角色", "position": 2},
    }
    snapshot["details"] = {"monthly-requirement": {"detail_id": "monthly-requirement", "task_id": "monthly",
                                                "kind": "requirement", "text": "檢查 A、B 系統", "position": 0}}
    snapshot["task_capabilities"] = [{"task_id": "rare", "capability_id": "skill-a", "position": 0}]
    context = replace(context, refs={
        "monthly-description": Ref("scope-a", "base-1", "task", "monthly", field="description"),
        "monthly-requirement-text": Ref("scope-a", "base-1", "detail", "monthly-requirement", field="text"),
    })
    expected = deepcopy(snapshot)
    expected["tasks"]["monthly"]["description"] = "只有 B 系統有月檢"
    expected["details"]["monthly-requirement"]["text"] = "依 B 系統服務約定檢查"
    command = model_command("jd_revise_work", model_arguments({"changes": [
        {"kind": "set_field", "target_field_ref": "monthly-description", "text": "只有 B 系統有月檢", "basis_refs": []},
        {"kind": "set_field", "target_field_ref": "monthly-requirement-text", "text": "依 B 系統服務約定檢查", "basis_refs": []},
    ]}))
    assert build_candidate(snapshot, command, context) == expected


def test_all_eight_operations_share_manual_and_both_model_paths():
    outputs = []
    for mode in ("manual", "openai-json", "anthropic-object"):
        snapshot, context = baseline()
        refs = dict(context.refs)
        refs.update({"duties": Ref("scope-a", "base-1", "container", child_kind="duty"),
                     "title": Ref("scope-a", "base-1", "profile", field="job_title")})
        context = replace(context, refs=refs)
        observed = set()

        def apply(tool, payload):
            nonlocal snapshot
            before = deepcopy(snapshot)
            model_payload = payload if mode == "manual" else model_arguments(payload)
            command = (manual_command({"tool": tool, "arguments": payload}) if mode == "manual"
                       else model_command(tool, json.dumps(model_payload) if mode == "openai-json" else model_payload))
            candidate = build_candidate(snapshot, command, context)
            assert snapshot == before
            assert candidate["revision"] == "base-1"  # Preparation only, no simulated commit.
            snapshot = candidate
            observed.add(tool)

        apply("jd_set_text", {"target_field_ref": "title", "text": "維護工程師", "basis_refs": []})
        apply("jd_insert_item", {"item": {"kind": "duty", "container_ref": "duties", "after_ref": None,
            "name": "例行維護", "scope_text": "只處理 B 系統", "basis_refs": []}})
        duty_id, = snapshot["duties"]
        refs["duty"] = Ref("scope-a", "base-1", "duty", duty_id)
        refs["duty-tasks"] = Ref("scope-a", "base-1", "container", duty_id, child_kind="task")
        payload = create_arguments()
        payload.update(container_ref="duty-tasks", description="B 系統每月檢查；其他每月事項另行確認。")
        apply("jd_create_task", payload)
        task_id, = snapshot["tasks"]
        refs["task"] = Ref("scope-a", "base-1", "task", task_id)
        refs["body"] = Ref("scope-a", "base-1", "task", task_id, field="description")
        refs["task-name"] = Ref("scope-a", "base-1", "task", task_id, field="name")
        original_details = deepcopy(snapshot["details"])
        original_sources = deepcopy(snapshot["source_links"])

        text = snapshot["tasks"][task_id]["description"]
        start = len(text[:text.index("每月")].encode("utf-16-le")) // 2
        context = replace(context, selections={"selection": Selection("body", text, start, start + 2, "每月")})
        apply("jd_replace_selection", {"selection_ref": "selection", "replacement_text": "每季", "basis_refs": []})
        assert snapshot["tasks"][task_id]["description"] == "B 系統每季檢查；其他每月事項另行確認。"
        apply("jd_revise_work", {"changes": [{"kind": "set_field", "target_field_ref": "task-name",
                                               "text": "B 系統例行檢查", "basis_refs": []}]})
        apply("jd_set_task_capability", {"task_ref": "task", "capability_ref": "picked-skill", "mode": "unlink", "basis_refs": []})
        apply("jd_set_task_capability", {"task_ref": "task", "capability_ref": "picked-skill", "mode": "link", "basis_refs": []})
        apply("jd_move_item", {"target_ref": "task", "destination_container_ref": "unassigned", "after_ref": None,
                                "content_changes": []})
        apply("jd_delete_item", {"target_ref": "duty", "content_changes": []})
        assert snapshot["duties"] == {}
        assert snapshot["tasks"][task_id]["duty_id"] is None
        assert snapshot["details"] == original_details
        assert snapshot["source_links"] == original_sources
        assert [link["capability_id"] for link in snapshot["task_capabilities"]] == ["skill-a"]
        assert snapshot["capabilities"]["skill-b"]["description"] == "辨識鍵盤操作及可用性障礙"
        assert len(observed) == 8
        outputs.append(snapshot)
    assert outputs[0] == outputs[1] == outputs[2]
