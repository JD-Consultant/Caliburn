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
        pending=["新任務「客戶問題重現」"], employee_text="每雙週寫一次案例")
    assert msgs[0]["role"] == "system" and "顧問" in msgs[0]["content"]
    # 對話映射:employee→user、consultant→assistant
    roles = [m["role"] for m in msgs]
    assert "assistant" in roles and "user" in roles
    assert msgs[-1]["role"] == "user" and "每雙週寫一次案例" in msgs[-1]["content"]
    # 帳本摘要 + 待核准注入(context block)
    joined = "\n".join(m["content"] for m in msgs)
    assert "客戶問題重現" in joined                          # pending 注入
    assert "測試案例設計" in joined                          # 帳本缺口注入


def test_first_turn_uses_disclosure():
    doc = _doc()
    msgs = C.build_consultant_messages(doc=doc, ledger_state={}, recent_turns=[],
                                       pending=[], employee_text="")
    joined = "\n".join(m["content"] for m in msgs)
    assert "AI" in joined and "開始" in joined               # 空對話 → 開場揭露
