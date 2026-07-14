"""T4(v3):書記 op 管線純函式——records_to_ops 映射 + land_ops(verify→_pending 落地)。

v3 不變量(ADR 0030):
- 一切寫入都是 `_pending` 標記,絕無直改;官方碼由程式從 ref_urn 導出。
- 幻覺 quote 被 verify 拒收(整筆丟、留痕);kind↔pool_id 跨池在映射層擋。
- v2 的三路落地(直寫/建議表/證據表)已退場。
"""
from app.interview.scribe import land_ops, records_to_ops

TASK = "ocs_content.ocu_units.U1.tasks.C"
UNIT = "ocs_content.ocu_units.U1"
POOL_ITEMS = {"K01": "測試設計技術", "S01": "測試工具使用", "A01": "謹慎細心"}
POOLS = {"knowledge": ["K01"], "skills": ["S01"], "attitudes": ["A01"]}
TURNS = {7: "我要先讀懂需求規格再設計案例,需求一改我就整批重審,每天都在弄客戶的 ticket,"
            "也要懂我們自己的 ERP 系統,每天都做這件事,還要會跑測試工具"}


def _doc():
    return {"ocs_content": {"ocu_units": [
        {"_uid": "U1", "ocu_name": "測試規劃",
         "tasks": [{"_tid": "C", "task_codes": [{"code": None, "name": "設計測試案例"}],
                    "competency_blocks": [{}], "details": {}}]}]},
        "ocs_attitude": {"attitudes": []}}


def _ops(records):
    return records_to_ops(records, turn_id=7, pools=POOLS, pool_items=POOL_ITEMS)


def _land(records, doc=None):
    ops, map_guard = _ops(records)
    new_doc, guard, landed = land_ops(
        ops, doc=doc or _doc(), turns=TURNS, ref_codes=set(POOL_ITEMS),
        header_codes=set(), pool_items=POOL_ITEMS)
    return new_doc, map_guard + guard, landed


def _block(doc):
    return doc["ocs_content"]["ocu_units"][0]["tasks"][0]["competency_blocks"][0]


# ---- 池通道:官方碼由 ref_urn 導出、落 pending-add ----

def test_pool_knowledge_lands_as_pending_with_ref():
    new_doc, _, landed = _land([{"type": "record_task_pool", "kind": "knowledge",
                                 "task": TASK, "pool_id": "K01",
                                 "quote": "我要先讀懂需求規格"}])
    assert new_doc is not None and len(landed) == 1
    entry = _block(new_doc)["knowledge"][0]
    assert entry["code"] == "K01" and entry["name"] == "測試設計技術"
    mark = entry["_pending"]
    assert mark["op"] == "add" and mark["by"] == "ai" and mark["turn_id"] == 7
    assert mark["src"]["ref_urn"] == "K01"
    assert mark["src"]["quote"]["text"] == "我要先讀懂需求規格"


def test_scribe_prompt_has_d8_rules():
    """D8 P5(實測 65b9aa3d):①不硬塞不相關任務 ②K/S 判準 ③玩笑不記。"""
    from app.interview.scribe import SCRIBE_SYS
    assert "add_custom_task" in SCRIBE_SYS and "硬塞" in SCRIBE_SYS
    assert "會操作" in SCRIBE_SYS
    assert "玩笑" in SCRIBE_SYS


def test_unknown_record_type_dropped_with_trace():
    ops, guard = _ops([{"type": "record_attitude_pool", "pool_id": "A01", "quote": "x"}])
    assert ops == [] and any("未知" in g for g in guard)


# ---- 語義守衛:kind↔pool_id 跨池在映射層擋 ----

def test_pool_id_cross_kind_rejected():
    ops, guard = _ops([{"type": "record_task_pool", "kind": "skills", "task": TASK,
                        "pool_id": "K01", "quote": "我要先讀懂需求規格"}])
    assert ops == [] and any("pool_id" in g for g in guard)


# ---- quote 守衛:幻覺引用整筆拒收(verify ②) ----

def test_hallucinated_quote_rejected_not_landed():
    new_doc, guard, landed = _land([{"type": "record_task_pool", "kind": "knowledge",
                                     "task": TASK, "pool_id": "K01",
                                     "quote": "我每天寫一萬行程式碼"}])
    assert new_doc is None and landed == []
    assert any("verify-reject" in g and "quote" in g for g in guard)


# ---- 自訂通道:一樣落 pending-add(不再有建議表) ----

def test_custom_knowledge_lands_pending_without_code():
    new_doc, _, _ = _land([{"type": "record_task_custom", "kind": "knowledge",
                            "task": TASK, "name": "自家 ERP 領域知識",
                            "quote": "懂我們自己的 ERP"}])
    entry = _block(new_doc)["knowledge"][0]
    assert entry["code"] is None and entry["name"] == "自家 ERP 領域知識"
    assert entry["_pending"]["src"].get("ref_urn") is None


def test_draft_indicator_lands_pending_text():
    new_doc, _, _ = _land([{"type": "draft_indicator", "task": TASK,
                            "text": "能在需求變更時整批重審受影響案例",
                            "quote": "需求一改我就整批重審"}])
    entry = _block(new_doc)["indicators"][0]
    assert entry["text"].startswith("能在需求變更") and entry["_pending"]["op"] == "add"


def test_add_custom_task_creates_pending_taskgroup():
    new_doc, _, _ = _land([{"type": "add_custom_task", "unit_ref": UNIT,
                            "name": "客戶問題單重現", "quote": "每天都在弄客戶的 ticket"}])
    tasks = new_doc["ocs_content"]["ocu_units"][0]["tasks"]
    assert len(tasks) == 2
    new_task = tasks[1]
    assert new_task["task_codes"][0] == {"code": None, "name": "客戶問題單重現"}
    assert new_task["_pending"]["op"] == "add"


# ---- set_slot → mod:值上綠字、舊值收進集合式 _pending ----

def test_set_slot_lands_value_with_collection_pending():
    slot = f"{TASK}.details.frequency"
    doc = _doc()
    doc["ocs_content"]["ocu_units"][0]["tasks"][0]["details"] = {"frequency": "每月"}
    new_doc, _, _ = _land([{"type": "set_slot", "path": slot, "value": "每天",
                            "quote": "每天都做這件事"}], doc=doc)
    details = new_doc["ocs_content"]["ocu_units"][0]["tasks"][0]["details"]
    assert details["frequency"] == "每天"
    mark = details["_pending"]["frequency"]
    assert mark["op"] == "mod" and mark["prev"] == "每月"


def test_set_slot_coerces_numeric_pct():
    """time_share_pct「25%」→ 25.0(share_sum/is_core 吃數;2026-07-13 sim 抓漏)。"""
    slot = f"{TASK}.details.time_share_pct"
    new_doc, _, _ = _land([{"type": "set_slot", "path": slot, "value": "25%",
                            "quote": "每天都做這件事"}], doc=_doc())
    details = new_doc["ocs_content"]["ocu_units"][0]["tasks"][0]["details"]
    assert details["time_share_pct"] == 25.0


# ---- 跨任務:多筆各落各的 ----

def test_multi_records_land_on_their_tasks():
    doc = {"ocs_content": {"ocu_units": [{"_uid": "U1", "tasks": [
        {"_tid": "C1", "task_codes": [{"code": None, "name": "甲"}],
         "competency_blocks": [{}], "details": {}},
        {"_tid": "C2", "task_codes": [{"code": None, "name": "乙"}],
         "competency_blocks": [{}], "details": {}}]}]},
        "ocs_attitude": {"attitudes": []}}
    t1, t2 = "ocs_content.ocu_units.U1.tasks.C1", "ocs_content.ocu_units.U1.tasks.C2"
    new_doc, _, landed = _land(
        [{"type": "record_task_pool", "kind": "knowledge", "task": t1,
          "pool_id": "K01", "quote": "讀懂需求規格"},
         {"type": "record_task_pool", "kind": "skills", "task": t2,
          "pool_id": "S01", "quote": "會跑測試工具"}], doc=doc)
    assert len(landed) == 2
    tasks = new_doc["ocs_content"]["ocu_units"][0]["tasks"]
    assert tasks[0]["competency_blocks"][0]["knowledge"][0]["code"] == "K01"
    assert tasks[1]["competency_blocks"][0]["skills"][0]["code"] == "S01"


# ---- 部分失敗:好筆落、壞筆丟留痕 ----

def test_partial_failure_lands_good_drops_bad():
    new_doc, guard, landed = _land(
        [{"type": "record_task_custom", "kind": "knowledge", "task": TASK,
          "name": "ERP 知識", "quote": "懂我們自己的 ERP"},
         {"type": "record_task_custom", "kind": "skills", "task": TASK,
          "name": "編故事", "quote": "這句是幻覺"}])
    assert len(landed) == 1 and new_doc is not None
    assert _block(new_doc)["knowledge"][0]["name"] == "ERP 知識"
    assert "skills" not in _block(new_doc) or _block(new_doc)["skills"] == []
    assert any("verify-reject" in g for g in guard)


def test_none_record_yields_no_ops():
    ops, guard = _ops([{"type": "none"}])
    assert ops == [] and guard == []
