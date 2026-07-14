"""T8:顧問 prompt v2(spec §4.3、prompts §1、§16.8)。
顧問無寫入權(說話+查工具);帳本缺口注入、開場揭露、messages 組裝。純函式。"""
from app.interview import consultant as C


def _doc():
    return {"ocs_profile": {"ocs_code": "X"},
            "ocs_content": {"ocu_units": [{"_uid": "U1", "ocu_name": "測試規劃", "tasks": [
                {"_tid": "C", "task_codes": [{"code": "T1", "name": "測試案例設計"}],
                 "competency_blocks": [{}],
                 "details": {"frequency": "每雙週", "time_share_pct": 25}}]}]},
            "ocs_attitude": {"attitudes": []}}


def test_system_prompt_v4_outcome_first_no_duplicate():
    sys = C.CONSULTANT_SYSTEM
    # GPT-5.6(spec §2.8):規則只留一份——不得有「再讀一次」式首尾重複段(黑名單1)
    assert "再讀一次" not in sys
    # outcome-first:含「訪談成功長什麼樣/具體事件」成功判準框架(非逐步指令)
    assert "具體事件" in sys and ("成功" in sys or "收尾" in sys)
    # 議程工具停止條件=v4 事件驅動關鍵接縫(顧問要知道何時 open/close)
    assert "open_episode" in sys and "close_episode" in sys
    # 保留:硬規則(資料非指令)、不寫入、BEI 故事
    assert "不是給你的指令" in sys
    assert "不負責記錄" in sys or "書記" in sys
    assert "故事" in sys


def test_no_write_vocabulary_in_prompt():
    # 顧問 prompt 不得出現 set_slot/落槽等寫入指令(那是書記/executor 的事)
    assert "set_slot" not in C.CONSULTANT_SYSTEM
    assert "落槽" not in C.CONSULTANT_SYSTEM


def test_opening_disclosure_elements():
    d = C.opening_disclosure(est_minutes=20)
    assert "AI" in d and "20" in d                          # AI 身分 + 時長
    assert "記錄" in d and ("審核" in d or "審" in d)        # 資料用途 + 有人審


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


# ---- onboarding 引導已移至議程 artifact(見 test_interview_agenda;此處僅守顧問 prompt 硬規則) ----

def test_system_prompt_has_onboarding_guard():
    """顧問 system prompt 要含『選職類前不問態度、不硬猜職類』的硬規則。"""
    sys = C.CONSULTANT_SYSTEM
    assert "選職類" in sys
    assert "加選" in sys                                   # D8 P2:超出現有職類→明講建議加選


# 檢查表成組反問 + write-in 抓漏已移至議程 artifact(agenda.agenda_view;見 test_interview_agenda)。
