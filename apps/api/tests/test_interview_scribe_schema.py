"""T3:書記兩通道 schema(strict 受限解碼;spec 2026-07-08 §3.1)。
分離變體、每個 enum 全鎖死;池空→不生該變體(fail-closed)。純函式。"""
import json

from app.interview.scribe_schema import ScribeOutput, scribe_schema

TASKS = ["ocs_content.ocu_units.U1.tasks.C"]
UNITS = ["ocs_content.ocu_units.U1"]
SLOTS = [f"{TASKS[0]}.details.frequency", f"{TASKS[0]}.details.wait_points"]
POOLS = {"knowledge": ["K01", "K02"], "skills": ["S01"], "attitudes": ["A01", "A03"]}


def _variant_tags(schema: dict) -> set[str]:
    variants = schema["properties"]["records"]["items"]["anyOf"]
    return {v["properties"]["type"]["enum"][0] for v in variants}


def _variant(schema: dict, tag: str) -> dict:
    for v in schema["properties"]["records"]["items"]["anyOf"]:
        if v["properties"]["type"]["enum"][0] == tag:
            return v
    raise KeyError(tag)


def test_full_inputs_produce_all_channels():
    s = scribe_schema(slot_paths=SLOTS, pools=POOLS, task_keys=TASKS, unit_keys=UNITS)
    tags = _variant_tags(s)
    assert {"set_slot", "record_task_pool", "record_attitude_pool", "record_task_custom",
            "record_attitude_custom", "draft_indicator", "add_custom_task", "none"} == tags


def test_none_always_present_even_empty():
    s = scribe_schema(slot_paths=[], pools={}, task_keys=[], unit_keys=[])
    assert _variant_tags(s) == {"none"}          # fail-closed:無輸入 → 只剩逃生口


def test_empty_pool_drops_pool_variant_not_custom():
    s = scribe_schema(slot_paths=SLOTS, pools={}, task_keys=TASKS, unit_keys=UNITS)
    tags = _variant_tags(s)
    assert "record_task_pool" not in tags and "record_attitude_pool" not in tags
    assert "record_task_custom" in tags          # 自訂通道不靠池,仍在


def test_pool_enums_locked_to_given_ids():
    s = scribe_schema(slot_paths=SLOTS, pools=POOLS, task_keys=TASKS, unit_keys=UNITS)
    tp = _variant(s, "record_task_pool")
    assert set(tp["properties"]["pool_id"]["enum"]) == {"K01", "K02", "S01"}   # task 池聯集
    assert set(tp["properties"]["kind"]["enum"]) == {"knowledge", "skills"}    # 有池的 task-kind
    ap = _variant(s, "record_attitude_pool")
    assert set(ap["properties"]["pool_id"]["enum"]) == {"A01", "A03"}


def test_task_and_slot_enums_locked():
    s = scribe_schema(slot_paths=SLOTS, pools=POOLS, task_keys=TASKS, unit_keys=UNITS)
    assert _variant(s, "set_slot")["properties"]["path"]["enum"] == SLOTS
    assert _variant(s, "draft_indicator")["properties"]["task"]["enum"] == TASKS
    assert _variant(s, "add_custom_task")["properties"]["unit_ref"]["enum"] == UNITS


def test_strict_shape_all_required_no_additional():
    s = scribe_schema(slot_paths=SLOTS, pools=POOLS, task_keys=TASKS, unit_keys=UNITS)
    assert s["additionalProperties"] is False and s["required"] == ["records"]
    for v in s["properties"]["records"]["items"]["anyOf"]:
        assert v["additionalProperties"] is False
        assert set(v["required"]) == set(v["properties"])   # 全欄位 required
    json.dumps(s)                                           # 可序列化(送 API)


def test_pydantic_validates_records_and_quote():
    ok = ScribeOutput.model_validate({"records": [
        {"type": "record_task_pool", "kind": "knowledge", "task": TASKS[0],
         "pool_id": "K01", "quote": "我要先讀懂需求規格"},
        {"type": "none"}]})
    assert ok.records[0].type == "record_task_pool"
    assert ok.records[1].type == "none"


def test_pydantic_rejects_unknown_type():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ScribeOutput.model_validate({"records": [{"type": "delete_all"}]})
