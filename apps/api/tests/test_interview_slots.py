"""T4:槽位定義/深問預算/覆蓋率門檻(純函式,無 DB 無 LLM)。"""
from app.interview.slots import (
    BUDGET_SLOTS, LIGHT_SLOTS, SLOT_DEFS,
    gate_missing, is_core, outputs_filled, slot_filled,
)


def _task(details=None, outputs=None):
    return {
        "task_codes": [{"code": "T1.1", "name": "測試規劃"}],
        "competency_blocks": [{"outputs": list(outputs or [])}],
        "details": details,
    }


def test_slot_defs_shape():
    assert len(SLOT_DEFS) == 11
    assert set(BUDGET_SLOTS) <= set(SLOT_DEFS)
    assert set(LIGHT_SLOTS) <= set(SLOT_DEFS)


def test_slot_filled_semantics():
    assert not slot_filled(None, "frequency")
    assert not slot_filled({"frequency": "  "}, "frequency")
    assert slot_filled({"frequency": "每週"}, "frequency")
    assert slot_filled({"time_share_pct": 0}, "time_share_pct")   # 數值 0 = 已答


def test_undecided_until_budget_slots_known():
    t = _task({"frequency": "每週"})
    assert is_core(t) is None
    assert gate_missing(t) == ["time_share_pct"]   # 先補預算槽,不問其他


def test_core_by_pct_and_by_high_frequency():
    assert is_core(_task({"frequency": "每季", "time_share_pct": 20})) is True
    assert is_core(_task({"frequency": "每日", "time_share_pct": 5})) is True
    assert is_core(_task({"frequency": "每季", "time_share_pct": 5})) is False


def test_light_gate_list():
    t = _task({"frequency": "每季", "time_share_pct": 5})
    assert gate_missing(t) == ["standards", "outputs"]
    t2 = _task({"frequency": "每季", "time_share_pct": 5, "standards": "主管確認"},
               outputs=[{"code": "O1", "name": "報表"}])
    assert gate_missing(t2) == []


def test_core_gate_requires_all_slots_and_outputs():
    full = {d: "x" for d in SLOT_DEFS}
    full["time_share_pct"] = 25
    t = _task(full, outputs=[{"code": "O1", "name": "測試計畫"}])
    assert is_core(t) is True and gate_missing(t) == []
    del full["wait_points"]
    t2 = _task(full, outputs=[{"code": "O1", "name": "測試計畫"}])
    assert gate_missing(t2) == ["wait_points"]
