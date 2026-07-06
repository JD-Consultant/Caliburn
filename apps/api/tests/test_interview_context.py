"""RC3(2026-07-06):context 狀態組裝 + ROLE_HEADER 資深動作守則。純函式、無 I/O。

驗的是「餵對狀態」(skipped 扣除、已填回述、pending 帶入)與 prompt 不退化
(四個 senior 動作錨點)——對話品質研究紀錄 2026-07-06。
"""
from app.interview.context import ROLE_HEADER, build_prompt

TASK_PATH = "ocs_content.ocu_units.u1.tasks.t1"


def _doc(details=None):
    return {
        "ocs_profile": {"ocs_code": "X", "job_description": ""},
        "ocs_content": {"ocu_units": [{
            "_uid": "u1", "ocu_name": "測試",
            "tasks": [{"_tid": "t1",
                       "task_codes": [{"code": "T1.1", "name": "回歸測試"}],
                       "competency_blocks": [{"outputs": [{"code": "O1", "name": "報告"}]}],
                       **({"details": dict(details)} if details else {})}],
        }]},
    }


def _build(*, focus, counters=None, recent=None, user_text="嗯", pending=None,
           details=None):
    return build_prompt(doc=_doc(details if details is not None else {"frequency": "每天"}),
                        phase="deep", focus=focus, counters=counters or {},
                        recent_turns=recent or [], user_text=user_text, pending=pending)


def test_skipped_slot_not_shown_as_gap():
    # frequency 已填 → gate_missing=[time_share_pct];再把它 skip → 缺口清單應為空
    skipped = f"{TASK_PATH}.details.time_share_pct"
    prompt, _ = _build(focus={"task_path": TASK_PATH, "skipped": [skipped]})
    gap_section = prompt.split("缺口")[1] if "缺口" in prompt else ""
    assert "工作比重" not in gap_section          # 已跳過的槽不再被列為待問


def test_filled_slot_shown_for_reflection():
    prompt, _ = _build(focus={"task_path": TASK_PATH})
    assert "每天" in prompt                        # 已填值回述,支撐「連舊答」


def test_pending_suggestion_surfaced():
    prompt, _ = _build(focus={"task_path": TASK_PATH}, pending=["新任務「處理床位滿」"])
    assert "處理床位滿" in prompt and "建議" in prompt   # 員工可能問到建議卡


def test_role_header_has_senior_moves():
    # 四個資深動作錨點(措辭可調,錨點防退化):回述/追問/修復/建議卡
    for anchor in ("回述", "追問", "剛剛", "套用"):
        assert anchor in ROLE_HEADER


def test_no_focus_task_no_crash():
    prompt, choice = build_prompt(doc=_doc(), phase="deep", focus={}, counters={},
                                  recent_turns=[], user_text="hi", pending=None)
    assert isinstance(prompt, str) and choice is None
