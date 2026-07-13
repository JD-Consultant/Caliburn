"""T8:顧問 prompt v2(spec §4.3、prompts §1、§16.8)。
顧問無寫入權(說話+查工具);帳本缺口注入、開場揭露、messages 組裝。純函式。"""
from app.interview import consultant as C
from app.interview.slots import SLOT_DEFS


def _doc():
    return {"ocs_profile": {"ocs_code": "X"},
            "ocs_content": {"ocu_units": [{"_uid": "U1", "ocu_name": "測試規劃", "tasks": [
                {"_tid": "C", "task_codes": [{"code": "T1", "name": "測試案例設計"}],
                 "competency_blocks": [{}],
                 "details": {"frequency": "每雙週", "time_share_pct": 25}}]}]},
            "ocs_attitude": {"attitudes": []}}


def test_system_prompt_has_key_rules_at_start_and_end():
    sys = C.CONSULTANT_SYSTEM
    # GPT-4.1 指南:關鍵規則首尾各一份(「員工訊息=資料非指令」概念在頭也在尾)
    assert "指令" in sys[:500] and "不是指令" in sys[-400:]
    assert "不負責記錄" in sys or "有書記" in sys          # 顧問不寫入
    assert "故事" in sys                                    # BEI 短故事式


def test_no_write_vocabulary_in_prompt():
    # 顧問 prompt 不得出現 set_slot/落槽等寫入指令(那是書記/executor 的事)
    assert "set_slot" not in C.CONSULTANT_SYSTEM
    assert "落槽" not in C.CONSULTANT_SYSTEM


def test_opening_disclosure_elements():
    d = C.opening_disclosure(est_minutes=20)
    assert "AI" in d and "20" in d                          # AI 身分 + 時長
    assert "記錄" in d and ("審核" in d or "審" in d)        # 資料用途 + 有人審


def test_gap_label_human_readable():
    doc = _doc()
    gap = "ocs_content.ocu_units.U1.tasks.C.details.wait_points"
    label = C.gap_label(doc, gap)
    assert "測試案例設計" in label and SLOT_DEFS["wait_points"].label in label
    assert C.gap_label(doc, "ocs_attitude") == "工作態度"


def test_ledger_summary_shows_next_gap():
    doc = _doc()                                            # core 任務缺一堆槽
    summary = C.ledger_summary(doc, {})
    assert "測試案例設計" in summary                         # 指向缺口任務
    # 靈魂槽優先:wait_points/exceptions/standards 之一應被建議
    assert any(SLOT_DEFS[k].label in summary for k in ("wait_points", "exceptions", "standards"))


def test_build_messages_shape_and_injection():
    doc = _doc()
    msgs = C.build_consultant_messages(
        doc=doc, ledger_state={}, recent_turns=[("consultant", "你好"), ("employee", "我做測試")],
        employee_text="每雙週寫一次案例")
    assert msgs[0]["role"] == "system" and "顧問" in msgs[0]["content"]
    # 對話映射:employee→user、consultant→assistant
    roles = [m["role"] for m in msgs]
    assert "assistant" in roles and "user" in roles
    assert msgs[-1]["role"] == "user" and "每雙週寫一次案例" in msgs[-1]["content"]
    # 帳本摘要注入(context block;待審綠字改由 read_document 四態視圖供給,T12)
    joined = "\n".join(m["content"] for m in msgs)
    assert "測試案例設計" in joined                          # 帳本缺口注入


def test_first_turn_uses_disclosure():
    doc = _doc()
    msgs = C.build_consultant_messages(doc=doc, ledger_state={}, recent_turns=[],
                                       employee_text="")
    joined = "\n".join(m["content"] for m in msgs)
    assert "AI" in joined and "開始" in joined               # 空對話 → 開場揭露


# ---- onboarding 引導(空白文件不問態度、引導選職類;§16.16) ----

def _blank_doc():
    return {"ocs_profile": {}, "ocs_content": {"ocu_units": []},
            "ocs_attitude": {"attitudes": []}}


def test_ledger_summary_onboarding_steers_occupation_not_attitude():
    """空白文件:帳本摘要要引導顧問去『選職類』,且明示選職類前不問態度。"""
    summary = C.ledger_summary(_blank_doc(), {})
    assert "選職類" in summary
    assert "態度" in summary and "不" in summary             # 明示選職類前不問態度
    assert "接下來問:工作態度" not in summary                # 不得指使顧問問態度(舊 bug)


def test_ledger_summary_onboarding_tasks_when_occupation_set():
    doc = _blank_doc()
    doc["ocs_profile"] = {"ocs_code": "ISD2519-002v2"}
    summary = C.ledger_summary(doc, {})
    assert "任務" in summary                                  # 引導挑任務


def test_gap_label_onboarding_human_readable():
    doc = _blank_doc()
    assert "職類" in C.gap_label(doc, "onboarding:occupation")


def test_system_prompt_has_onboarding_guard():
    """顧問 system prompt 要含『選職類前不問態度、不硬猜職類』的硬規則。"""
    sys = C.CONSULTANT_SYSTEM
    assert "選職類" in sys
    assert "加選" in sys                                   # D8 P2:超出現有職類→明講建議加選


# ---- 檢查表成組反問 + write-in 抓漏(0028 T5) ----

_POOL = [
    {"key": "X:T1", "name": "測試案例設計", "unit": "規劃", "ocs_code": "X", "task_code": "T1"},
    {"key": "X:T9", "name": "自動化腳本維護", "unit": "維運", "ocs_code": "X", "task_code": "T9"},
]


def test_ledger_summary_checklist_group_probe():
    """官方池還有 unasked → 帳本摘要列名成組反問,且不問態度。"""
    doc = _doc()                                            # 只含 T1(測試案例設計)
    summary = C.ledger_summary(doc, {}, pool_tasks=_POOL)
    assert "自動化腳本維護" in summary and "有做" in summary
    assert "還不要問工作態度" in summary


def test_ledger_summary_writein_probe_once():
    """檢查表全處置(covered/declined)→ 吐一次 write-in 抓漏;flag 設了就不再吐。"""
    doc = _doc()
    state = {"declined": ["X:T9"]}                          # T1 covered、T9 declined
    s1 = C.ledger_summary(doc, state, pool_tasks=_POOL)
    assert "官方沒列" in s1                                  # 抓漏探測句
    s2 = C.ledger_summary(doc, {**state, "writein_asked": True}, pool_tasks=_POOL)
    assert "官方沒列" not in s2
