"""T4a:書記施作器 apply_scribe(純函式;spec §3.2、§16.3)。
把驗證過的 ScribeRecord 確定性落文件:能力區塊/態度 append + 細項槽(重用 executor 守衛)。
守衛:quote 驗證、pool_id∈pools[kind]、task/unit 解析。無 LLM 無 DB。"""
from app.interview.scribe import apply_scribe

TASK = "ocs_content.ocu_units.U1.tasks.C"
UNIT = "ocs_content.ocu_units.U1"
# pool_id → 官方名(建 schema 時由 knowledge 帶來,施作器據以寫 name)
POOL_ITEMS = {"K01": "測試設計技術", "S01": "測試工具使用", "A01": "謹慎細心"}
POOLS = {"knowledge": ["K01"], "skills": ["S01"], "attitudes": ["A01"]}


def _doc():
    return {"ocs_content": {"ocu_units": [
        {"_uid": "U1", "ocu_name": "測試規劃",
         "tasks": [{"_tid": "C", "competency_blocks": [{}], "details": {}}]}]},
        "ocs_attitude": {"attitudes": []}}


def _apply(records, doc=None, employee_texts=None, human_touched=None):
    return apply_scribe(
        records, doc=doc or _doc(), pool_items=POOL_ITEMS, pools=POOLS,
        employee_texts=employee_texts or ["我要先讀懂需求規格再設計案例"],
        human_touched=human_touched or [])


def _block(doc):
    return doc["ocs_content"]["ocu_units"][0]["tasks"][0]["competency_blocks"][0]


# ---- 池通道:寫官方碼+名到能力區塊 ----

def test_pool_knowledge_written_to_block():
    r = [{"type": "record_task_pool", "kind": "knowledge", "task": TASK,
          "pool_id": "K01", "quote": "我要先讀懂需求規格"}]
    res = _apply(r)
    assert res.new_doc is not None
    assert _block(res.new_doc)["knowledge"] == [{"code": "K01", "name": "測試設計技術"}]
    assert res.evidence[0]["verified"] is True


def test_scribe_prompt_has_d8_rules():
    """D8 P5(實測 65b9aa3d):①不硬塞不相關任務(改提新任務)②K/S 判準 ③玩笑不記。"""
    from app.interview.scribe import SCRIBE_SYS
    assert "add_custom_task" in SCRIBE_SYS and "硬塞" in SCRIBE_SYS   # ① 歸位
    assert "會操作" in SCRIBE_SYS                                      # ② S=會操作(vs K=知道)
    assert "玩笑" in SCRIBE_SYS                                        # ③ 玩笑/比喻不記


def test_pool_attitude_channel_retired():
    # 0028 D3:態度池通道退場——這種 record 一律忽略(不寫、不提議、留守衛痕)
    r = [{"type": "record_attitude_pool", "pool_id": "A01", "quote": "設計案例再設計"}]
    res = _apply(r, employee_texts=["設計案例再設計，很細心"])
    assert res.new_doc is None and res.suggestions == []
    assert any("未知" in g for g in res.guard_log)


def test_direct_writes_marked_pending_suggestions_stay_auto():
    # 低風險直寫(池 K/S/O、set_slot)→ evidence.review='pending';自訂/態度→無 pending
    pool = _apply([{"type": "record_task_pool", "kind": "knowledge", "task": TASK,
                    "pool_id": "K01", "quote": "我要先讀懂需求規格"}])
    assert pool.evidence[0]["review"] == "pending"
    custom = _apply([{"type": "record_task_custom", "kind": "knowledge", "task": TASK,
                      "name": "ERP 知識", "quote": "要懂我們自己的 ERP"}],
                    employee_texts=["要懂我們自己的 ERP"])
    assert custom.evidence[0].get("review", "auto") == "auto"   # 建議路由不標 pending


# ---- 語義守衛:pool_id 必須屬 pools[kind] ----

def test_pool_id_cross_kind_rejected():
    r = [{"type": "record_task_pool", "kind": "skills", "task": TASK,
          "pool_id": "K01", "quote": "我要先讀懂需求規格"}]     # K01 是 knowledge 非 skills
    res = _apply(r)
    assert res.new_doc is None                                  # 沒寫
    assert any("pool_id" in g for g in res.guard_log)


# ---- quote 守衛:不在逐字稿 → unverified(仍記證據,但不直寫) ----

def test_unverified_quote_not_written_but_evidenced():
    r = [{"type": "record_task_pool", "kind": "knowledge", "task": TASK,
          "pool_id": "K01", "quote": "我每天寫一萬行程式碼"}]    # 員工沒說過
    res = _apply(r)
    assert res.evidence[0]["verified"] is False
    assert res.new_doc is None                                  # 未驗證不落地


# ---- 自訂通道:走建議層(附 quote) ----

def test_custom_knowledge_becomes_suggestion():
    r = [{"type": "record_task_custom", "kind": "knowledge", "task": TASK,
          "name": "自家 ERP 領域知識", "quote": "要懂我們自己的 ERP"}]
    res = _apply(r, employee_texts=["要懂我們自己的 ERP 系統"])
    assert res.new_doc is None
    assert res.suggestions[0]["new_value"]["name"] == "自家 ERP 領域知識"


def test_draft_indicator_becomes_suggestion():
    r = [{"type": "draft_indicator", "task": TASK,
          "text": "能在需求變更時整批重審受影響案例", "quote": "需求一改我就整批重審"}]
    res = _apply(r, employee_texts=["需求一改我就整批重審案例"])
    assert res.new_doc is None
    assert res.suggestions[0]["doc_path"].endswith(".indicators")


def test_add_custom_task_becomes_suggestion():
    r = [{"type": "add_custom_task", "unit_ref": UNIT,
          "name": "客戶問題單重現", "quote": "每天都在弄客戶的 ticket"}]
    res = _apply(r, employee_texts=["每天都在弄客戶的 ticket"])
    assert res.suggestions[0]["doc_path"].startswith("add_task:")


# ---- 跨任務:多筆記到各自 task ----

def test_multi_records_land_on_their_tasks():
    doc = {"ocs_content": {"ocu_units": [{"_uid": "U1", "tasks": [
        {"_tid": "C1", "competency_blocks": [{}], "details": {}},
        {"_tid": "C2", "competency_blocks": [{}], "details": {}}]}]},
        "ocs_attitude": {"attitudes": []}}
    t1, t2 = "ocs_content.ocu_units.U1.tasks.C1", "ocs_content.ocu_units.U1.tasks.C2"
    r = [{"type": "record_task_pool", "kind": "knowledge", "task": t1,
          "pool_id": "K01", "quote": "讀需求"},
         {"type": "record_task_pool", "kind": "skills", "task": t2,
          "pool_id": "S01", "quote": "跑工具"}]
    res = apply_scribe(r, doc=doc, pool_items=POOL_ITEMS, pools=POOLS,
                       employee_texts=["讀需求", "跑工具"], human_touched=[])
    units = res.new_doc["ocs_content"]["ocu_units"][0]["tasks"]
    assert units[0]["competency_blocks"][0]["knowledge"] == [{"code": "K01", "name": "測試設計技術"}]
    assert units[1]["competency_blocks"][0]["skills"] == [{"code": "S01", "name": "測試工具使用"}]


# ---- set_slot:重用 executor 通道(human_touched → 建議) ----

def test_set_slot_direct_and_touched_routing():
    slot = f"{TASK}.details.frequency"
    r = [{"type": "set_slot", "path": slot, "value": "每天", "quote": "每天都做"}]
    direct = _apply(r, employee_texts=["每天都做這件事"])
    assert direct.new_doc["ocs_content"]["ocu_units"][0]["tasks"][0]["details"]["frequency"] == "每天"
    touched = _apply(r, employee_texts=["每天都做這件事"], human_touched=[slot])
    assert touched.new_doc is None and touched.suggestions[0]["doc_path"] == slot


def test_none_record_is_noop():
    res = _apply([{"type": "none"}])
    assert res.new_doc is None and res.evidence == [] and res.suggestions == []
