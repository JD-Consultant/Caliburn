"""T5(v3;ADR 0030):議程四態(held/boundary)+疲勞偵測+喚醒閘+四態視圖。純函式。"""
from app.interview import agenda as AG
from app.interview import ledger as L
from app.interview.scribe import worth_scribing
from app.interview.tools import document_view

DOC = {"ocs_content": {"ocu_units": [
    {"_uid": "u1", "ocu_name": "測試",
     "tasks": [{"_tid": "t1",
                "task_codes": [{"code": "T1.1", "name": "回歸測試"}],
                "competency_blocks": [
                    {"knowledge": [{"code": "K01", "name": "官方知識",
                                    "_pending": {"op": "add", "by": "ai", "turn_id": 3}}]}],
                "details": {"frequency": "每週",
                            "_pending": {"frequency": {"op": "mod", "by": "ai",
                                                       "turn_id": 4, "prev": "每月"}}}}]}]},
    "ocs_attitude": {"attitudes": [{"code": "A01", "name": "謹慎"}]},
    "ocs_profile": {"ocs_code": "X",
                    "_pending": {"ocs_code": {"op": "mod", "by": "ai", "turn_id": 5,
                                              "prev": "X", "value": "Y"}}}}


# ---- held(待問清單:FIFO、去重) ----

def test_held_push_dedupe_and_fifo_pop():
    s = AG.push_held({}, "問題A?", 3)
    s = AG.push_held(s, "問題A?", 4)          # 去重
    s = AG.push_held(s, "問題B?", 5)
    assert [h["q"] for h in s["held"]] == ["問題A?", "問題B?"]
    q, s2 = AG.pop_held(s)
    assert q == "問題A?" and [h["q"] for h in s2["held"]] == ["問題B?"]


# ---- boundary(劃線:硬遮罩、無自動解除路徑) ----

def test_boundary_masks_next_gap_and_never_auto_clears():
    task_gap_prefix = "ocs_content.ocu_units.u1.tasks.t1"
    s = AG.add_boundary({}, task_gap_prefix, quote="這塊先不談", since_turn=2)
    assert AG.in_boundary(s, f"{task_gap_prefix}.details.tools")
    assert not AG.in_boundary(s, "ocs_attitude")
    # 硬遮罩:note_attempt/pop_held 等任何狀態演化都不得移除 boundary
    s2 = AG.note_attempt(s, "ocs_attitude", True)
    assert s2.get("boundary") == s["boundary"]


def test_boundary_on_attitudes_suppresses_gap():
    doc = {"ocs_content": {"ocu_units": [
        {"_uid": "u1", "tasks": [{"_tid": "t1", "task_codes": [{"name": "x"}],
                                  "details": {"frequency": "每週", "time_share_pct": 50,
                                              "standards": "s", "duration": "d",
                                              "volume": "v", "trigger": "t", "inputs": "i",
                                              "tools": "o", "collaborators": "c",
                                              "wait_points": "w", "exceptions": "e"},
                                  "competency_blocks": [
                                      {"outputs": [{"name": "o"}],
                                       "indicators": [{"text": "p"}],
                                       "knowledge": [{"name": "k"}, {"name": "k2"}],
                                       "skills": [{"name": "s"}, {"name": "s2"}]}]}]}]},
        "ocs_profile": {"ocs_code": "X"}, "ocs_attitude": {"attitudes": []}}
    assert L.next_gap(doc, {}, {}) == "ocs_attitude"
    s = AG.add_boundary({}, "ocs_attitude")
    assert L.next_gap(doc, s, {}) != "ocs_attitude"


# ---- 疲勞(確定性:敷衍短語 / 長度銳減) ----

def test_fatigue_on_dismissive_phrases():
    assert AG.is_fatigued(["我們每天要對三條產線做首件檢查……(長回答)", "就這樣"])


def test_fatigue_on_shrinking_answers():
    long = "這是一段很長的回答" * 8
    assert AG.is_fatigued([long, long, long, "嗯", "喔", "好"])


def test_no_fatigue_on_healthy_conversation():
    healthy = ["第一段完整回答的內容說明", "第二段也講得很多細節喔", "第三段繼續補充說明流程"]
    assert not AG.is_fatigued(healthy)


# ---- 喚醒閘(確定性前濾:只擋明顯無素材) ----

def test_worth_scribing_gate():
    assert not worth_scribing("跳過")
    assert not worth_scribing("好")
    assert not worth_scribing("ok")
    assert not worth_scribing("")
    assert worth_scribing("30%")                      # 有數字=可能是比重
    assert worth_scribing("每天要對三條產線做首件檢查")
    assert worth_scribing("不是,是品保部負責")        # 否定+資訊


# ---- 四態視圖(顧問 read_document 工具) ----

def test_document_view_reports_four_states():
    view = document_view(DOC)
    row = view["tasks"][0]
    assert row["task"] == "回歸測試" and row["status"] == "confirmed"
    kinds = {p["kind"]: p["status"] for p in row["pending_items"]}
    assert kinds["knowledge"] == "pending_add"
    assert kinds["details.frequency"] == "pending_mod"
    assert view["attitudes"][0]["status"] == "confirmed"
    assert view["header_pending"]["ocs_code"] == {"status": "pending_mod", "proposed": "Y"}
