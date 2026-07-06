"""T6:executor 分流/守門/quote 驗證(純函式,無 DB 無 LLM)。"""
import copy

from app.interview.commands import TurnOutput
from app.interview.executor import ASK_BUDGET_PER_SLOT, apply, get_at

TASK_PATH = "ocs_content.ocu_units.u1.tasks.t1"
FREQ = f"{TASK_PATH}.details.frequency"


def _doc(details=None, outputs=({"code": "O1", "name": "測試計畫"},)):
    return {
        "ocs_profile": {"ocs_code": "X", "job_description": ""},
        "ocs_content": {"ocu_units": [{
            "_uid": "u1", "ocu_name": "測試",
            "tasks": [{
                "_tid": "t1",
                "task_codes": [{"code": "T1.1", "name": "回歸測試"}],
                "competency_blocks": [{"outputs": list(outputs)}],
                **({"details": dict(details)} if details is not None else {}),
            }],
        }]},
    }


def _turn(*cmds, saturation=False):
    return TurnOutput.model_validate({"commands": list(cmds), "saturation": saturation})


def _set(path=FREQ, value="每雙週", quote="每兩週跑一次"):
    return {"type": "set_slot", "path": path, "value": value, "quote": quote}


EMP = ["我們每兩週跑一次回歸,大概三百多條"]


def test_untouched_path_direct_write_and_input_unmutated():
    doc = _doc()
    before = copy.deepcopy(doc)
    res = apply(_turn(_set()), doc=doc, human_touched=[], counters={},
                focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert doc == before                              # 純函式:輸入不變
    assert get_at(res.new_doc, FREQ) == "每雙週"        # details 缺殼自動建
    assert res.evidence[0]["verified"] is True
    assert res.suggestions == []


def test_human_touched_path_routes_to_suggestion():
    doc = _doc(details={"frequency": "每月"})
    res = apply(_turn(_set()), doc=doc, human_touched=[FREQ], counters={},
                focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert res.new_doc is None                        # 零直改
    assert len(res.suggestions) == 1
    s = res.suggestions[0]
    assert s["doc_path"] == FREQ and s["old_value"] == "每月" and s["new_value"] == "每雙週"


def test_quote_unverified_value_still_lands():
    doc = _doc()
    res = apply(_turn(_set(quote="這句話員工沒說過")), doc=doc, human_touched=[],
                counters={}, focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert res.evidence[0]["verified"] is False       # 標記降級,不阻塞
    assert get_at(res.new_doc, FREQ) == "每雙週"


def test_add_task_always_suggestion():
    doc = _doc()
    res = apply(_turn({"type": "add_task", "unit_ref": "u1",
                       "name": "客戶問題單重現", "quote": "大概三百多條"}),
                doc=doc, human_touched=[], counters={},
                focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert res.new_doc is None
    assert res.suggestions[0]["new_value"]["name"] == "客戶問題單重現"


def test_ask_budget_enforced():
    # RC2 行為變更(2026-07-06 真人試訪):預算擋下不再靜默死路——
    # 自動 justified-skip 該槽 + 確定性改問下一缺口(訪談持續前進)。
    doc = _doc()
    ask = {"type": "ask", "question": "多久一次?", "target_path": FREQ}
    res = apply(_turn(ask), doc=doc, human_touched=[],
                counters={FREQ: ASK_BUDGET_PER_SLOT},
                focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert any("budget" in g for g in res.guard_log)
    assert FREQ in res.skipped_add                     # 預算耗盡=自動跳過
    assert res.question["target_path"].endswith("time_share_pct")   # 改問下一缺口
    # 預算內 → 照模型的題出並記 delta
    res2 = apply(_turn(ask), doc=doc, human_touched=[], counters={FREQ: 1},
                 focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert res2.question["target_path"] == FREQ and res2.counters_delta[FREQ] == 2


def test_advance_blocked_until_gate_then_skip_unblocks_light_task():
    # light 任務(每季 5%):缺 standards → 擋;justified skip 後 → 放行
    doc = _doc(details={"frequency": "每季", "time_share_pct": 5})
    adv = {"type": "advance", "next_focus": "review"}
    res = apply(_turn(adv), doc=doc, human_touched=[], counters={},
                focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert res.advanced_to is None and any("advance 拒絕" in g for g in res.guard_log)

    skip = {"type": "skip", "path": f"{TASK_PATH}.details.standards",
            "reason": "受訪者表示無明確標準"}
    res2 = apply(_turn(skip, adv), doc=doc, human_touched=[], counters={},
                 focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert res2.advanced_to == "review"
    assert f"{TASK_PATH}.details.standards" in res2.skipped_add


def test_unknown_path_dropped_not_crash():
    doc = _doc()
    res = apply(_turn(_set(path="ocs_content.ocu_units.u9.tasks.t9.details.frequency")),
                doc=doc, human_touched=[], counters={},
                focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert res.new_doc is None and any(g.startswith("drop:") for g in res.guard_log)


def test_unknown_slot_key_dropped_fail_closed():
    # 實戰回歸:gpt-4o-mini 發明過 details.process/tool/exception(2026-07-06 訪談)
    # → 寫進垃圾 key、真槽永遠缺 → 重問迴圈。白名單擋下(evidence 照記供稽核)。
    doc = _doc()
    res = apply(_turn(_set(path=f"{TASK_PATH}.details.process", value="打電話登記")),
                doc=doc, human_touched=[], counters={},
                focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert res.new_doc is None
    assert any("未知槽" in g for g in res.guard_log)
    assert len(res.evidence) == 1                     # 模型宣稱過什麼要留稽核軌跡
    assert res.suggestions == []                      # 垃圾 path 連建議層也不進


def test_job_description_whitelisted_writable():
    doc = _doc()
    res = apply(_turn(_set(path="ocs_profile.job_description", value="負責回歸測試")),
                doc=doc, human_touched=[], counters={},
                focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert res.new_doc["ocs_profile"]["job_description"] == "負責回歸測試"


# --- 保底輸出(RC2:回合恆有可見輸出;實戰三次靜默回合的回歸網) ---

def test_silent_set_slot_synthesizes_confirmation_and_next_question():
    doc = _doc()
    res = apply(_turn(_set()), doc=doc, human_touched=[], counters={},
                focus={"task_path": TASK_PATH}, employee_texts=EMP)
    # 模型只發 set_slot、漏 reply/ask → 保底:確認語 + 下一缺口模板題
    assert "頻率" in res.say and "每雙週" in res.say
    assert res.question["target_path"].endswith("time_share_pct")
    assert res.counters_delta[f"{TASK_PATH}.details.time_share_pct"] == 1


def test_silent_add_task_mentions_suggestion_card():
    doc = _doc()
    res = apply(_turn({"type": "add_task", "unit_ref": "u1", "name": "處理床位滿",
                       "quote": "大概三百多條"}),
                doc=doc, human_touched=[], counters={},
                focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert "建議" in res.say and "處理床位滿" in res.say    # 指引核准卡片,別讓員工猜
    assert res.question is not None                        # 不冷場,繼續問

def test_empty_commands_still_visible_output():
    doc = _doc(details={"frequency": "每季", "time_share_pct": 5, "standards": "主管確認"})
    res = apply(_turn(), doc=doc, human_touched=[], counters={},
                focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert res.say                                         # light 全齊 → 收尾語,仍有輸出


def test_advance_turn_says_transition_not_old_task_question():
    doc = _doc(details={"frequency": "每季", "time_share_pct": 5, "standards": "主管確認"})
    res = apply(_turn({"type": "advance", "next_focus": "ocs_content.ocu_units.u1.tasks.t2"}),
                doc=doc, human_touched=[], counters={},
                focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert res.advanced_to and res.say                     # 過場語
    assert res.question is None                            # 不回頭問舊任務


def test_reply_without_ask_still_gets_forward_question():
    # 校準#2:模型給了 reply/set 卻漏 ask → 保底補下一缺口題,不讓對話停在原地
    doc = _doc()
    res = apply(_turn(_set(), {"type": "reply", "text": "了解,每雙週一次。"}),
                doc=doc, human_touched=[], counters={},
                focus={"task_path": TASK_PATH}, employee_texts=EMP)
    assert res.say == "了解,每雙週一次。"                    # 尊重模型的話,不覆寫
    assert res.question["target_path"].endswith("time_share_pct")   # 但仍補前進
