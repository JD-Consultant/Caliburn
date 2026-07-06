"""T5:指令 pydantic 解析 + strict-subset schema 不變量(純函式)。"""
import pytest
from pydantic import ValidationError

from app.interview.commands import TurnOutput, turn_output_schema

ALL_NINE = {
    "commands": [
        {"type": "reply", "text": "了解!"},
        {"type": "ask", "question": "多久跑一次?", "target_path": "u1.t1.details.frequency"},
        {"type": "ask_choice", "question": "有做哪些?", "options": ["T1.1", "T1.2"],
         "target_path": None},
        {"type": "set_slot", "path": "u1.t1.details.volume", "value": "約300條",
         "quote": "大概三百多條"},
        {"type": "set_slot", "path": "u1.t1.details.time_share_pct", "value": 25,
         "quote": "大概四分之一的時間"},
        {"type": "correct_slot", "path": "u1.t1.details.frequency", "value": "每雙週",
         "quote": "應該是每兩週啦"},
        {"type": "add_task", "unit_ref": "u1", "name": "客戶問題單重現", "quote": "還有 ticket"},
        {"type": "add_duty", "name": "客戶問題支援", "quote": "幫客服處理"},
        {"type": "skip", "path": "u1.t1.details.wait_points", "reason": "受訪者明確表示無等待"},
        {"type": "advance", "next_focus": "u1.t2"},
    ],
    "saturation": False,
}


def test_parse_all_commands_roundtrip():
    out = TurnOutput.model_validate(ALL_NINE)
    assert len(out.commands) == 10
    assert out.commands[4].value == 25          # 數值槽
    assert out.commands[8].reason.startswith("受訪者")


def test_unknown_type_rejected():
    with pytest.raises(ValidationError):
        TurnOutput.model_validate({"commands": [{"type": "delete_all"}], "saturation": False})


SAFE_KEYS = {"type", "properties", "required", "additionalProperties", "enum", "anyOf", "items"}


def _walk_schema(node, check):
    """只走「schema 節點」:properties 容器的 key 是欄位名,不套關鍵字檢查。"""
    check(node)
    for k, v in node.items():
        if k == "properties":
            for sub in v.values():
                _walk_schema(sub, check)
        elif k == "items":
            _walk_schema(v, check)
        elif k == "anyOf":
            for sub in v:
                _walk_schema(sub, check)


def test_schema_strict_invariants():
    schema = turn_output_schema(["T1.1", "T1.2"])

    def check(d):
        assert set(d) <= SAFE_KEYS, f"unsafe keyword: {set(d) - SAFE_KEYS}"
        if d.get("type") == "object":
            assert d["additionalProperties"] is False
            assert d["required"] == list(d["properties"])   # 全欄位 required(strict 規則)

    _walk_schema(schema, check)


def test_schema_choice_variant_gating():
    no_choice = turn_output_schema(None)
    with_choice = turn_output_schema(["A", "B"])
    s_no, s_yes = str(no_choice), str(with_choice)
    assert "ask_choice" not in s_no                 # 沒池 id → LLM 發不出選單
    assert "ask_choice" in s_yes
    assert "'enum': ['A', 'B']" in s_yes            # 池 id 鎖進 enum


def _variants_by_tag(schema):
    variants = schema["properties"]["commands"]["items"]["anyOf"]
    return {v["properties"]["type"]["enum"][0]: v for v in variants}


def test_schema_slot_paths_lock_write_paths():
    """槽位 path 是目錄類值:給了 slot_paths 就用 enum 鎖死(LLM 發不出幽靈槽)。"""
    paths = ["u1.t1.details.frequency", "ocs_profile.job_description"]
    by_tag = _variants_by_tag(turn_output_schema(None, slot_paths=paths))
    for tag in ("set_slot", "correct_slot", "skip"):
        assert by_tag[tag]["properties"]["path"] == {"enum": paths}, tag
    # ask.target_path 不鎖(允許 None 開放問)
    assert by_tag["ask"]["properties"]["target_path"] == {"type": ["string", "null"]}


def test_schema_no_slot_paths_keeps_string_paths():
    by_tag = _variants_by_tag(turn_output_schema(None))
    assert by_tag["set_slot"]["properties"]["path"] == {"type": "string"}
