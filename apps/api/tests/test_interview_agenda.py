"""T5(0033):議程 agenda.py 純函式——episode 狀態機 + 訊號 + artifact。
無 DB 無 LLM。裁決依據見 spec 2026-07-14 §3.3/§3.4/§3.6。"""
from app.interview import agenda as A


def _block(p=0, k=0, s=0, o=0):
    mk = lambda pre, n: [{"code": f"{pre}{i}", "name": "x"} for i in range(n)]  # noqa: E731
    return {"indicators": [{"code": f"P{i}", "text": "x"} for i in range(p)],
            "outputs": mk("O", o), "knowledge": mk("K", k), "skills": mk("S", s)}


def _task(name, details=None, p=0, k=0, s=0, o=0, tid=None):
    t = {"task_codes": [{"code": None, "name": name}],
         "competency_blocks": [_block(p, k, s, o)], "details": details}
    if tid:
        t["_tid"] = tid
    return t


def _doc(tasks):
    return {"ocs_profile": {"ocs_code": "X"},                # 有職類 → 走正常議程視圖
            "ocs_content": {"ocu_units": [{"_uid": "U1", "ocu_name": "規劃",
                                           "tasks": tasks}]},
            "ocs_attitude": {"attitudes": []}}


def _blank_doc():                                            # 無職類 → onboarding 分支
    return {"ocs_profile": {}, "ocs_content": {"ocu_units": []},
            "ocs_attitude": {"attitudes": []}}


_POOL = [{"key": "X:T1", "name": "需求訪談", "ocs_code": "X", "task_code": "T1"},
         {"key": "X:T9", "name": "自動化腳本維護", "ocs_code": "X", "task_code": "T9"}]


# ---- episode 狀態機 ----

def test_open_episode_records_state():
    s = A.open_episode({}, target="ocs_content.ocu_units.U1.tasks.T1", seq=7)
    ep = A.episode_state(s)
    assert ep["target"] == "ocs_content.ocu_units.U1.tasks.T1"
    assert ep["opened_seq"] == 7


def test_open_free_episode():
    """裁決③:free 自發話題也能登記(只寫議程狀態)。"""
    s = A.open_episode({}, target="free", seq=3, note="盲測拖曳上傳")
    ep = A.episode_state(s)
    assert ep["target"] == "free" and ep["note"] == "盲測拖曳上傳"


def test_close_episode_archives_and_clears():
    s = A.open_episode({}, target="free", seq=3)
    s = A.close_episode(s, reason="saturated", seq=9)
    assert A.episode_state(s) is None                       # 進行中事件已清
    assert s["episodes"][-1]["reason"] == "saturated"
    assert s["episodes"][-1]["closed_seq"] == 9


def test_episode_state_none_when_no_open():
    assert A.episode_state({}) is None
    assert A.episode_state({"episodes": [{"target": "x", "closed_seq": 2}]}) is None


# ---- episode_yield(裁決①:任何落地都算收益,不限目標任務) ----

def test_episode_yield_true_for_any_landing():
    ep = {"target": "ocs_content.ocu_units.U1.tasks.T1", "opened_seq": 5}
    ops_other = [{"target_path": "ocs_content.ocu_units.U1.tasks.T2.details.tools"}]
    assert A.episode_yield(ops_other, ep) is True          # 跨任務落地=收益(feature)


def test_episode_yield_false_when_no_ops():
    ep = {"target": "ocs_content.ocu_units.U1.tasks.T1", "opened_seq": 5}
    assert A.episode_yield([], ep) is False


# ---- signals(三訊號;spec §3.6) ----

def test_signal_saturated_at_two_then_autoclose_at_three():
    """開著事件、連續零收益回合累積:2→提示,3→auto_close。"""
    ep = {"target": "t", "opened_seq": 5, "dry_streak": 2}
    sig = A.signals({"episode": ep}, turns_n=10)
    assert sig["stalled_episode"] is True and sig["auto_close"] is False
    ep3 = {"target": "t", "opened_seq": 5, "dry_streak": 3}
    sig3 = A.signals({"episode": ep3}, turns_n=11)
    assert sig3["auto_close"] is True


def test_signal_episode_too_long_soft():
    """裁決②:事件開 ≥6 輪 → 軟提示 long_episode(不強制)。"""
    ep = {"target": "t", "opened_seq": 5, "dry_streak": 0}
    sig = A.signals({"episode": ep}, turns_n=11)           # 11-5=6 輪
    assert sig["long_episode"] is True and sig["auto_close"] is False


def test_signal_no_episode_nudge_after_two_turns():
    sig = A.signals({"no_episode_streak": 2}, turns_n=8)
    assert sig["no_episode_nudge"] is True


def test_signal_budget():
    assert A.signals({}, turns_n=A.TURN_BUDGET)["budget"] is True
    assert A.signals({}, turns_n=3)["budget"] is False


# ---- agenda_view(artifact;spec §3.3) ----

def test_agenda_view_shows_episode_and_coverage_map():
    doc = _doc([_task("需求訪談", tid="T1"),                # 全空
                _task("介面設計", {"frequency": "每週", "time_share_pct": 25},
                      p=1, k=2, s=2, o=1, tid="T2")])       # 較完整
    ep = {"target": "ocs_content.ocu_units.U1.tasks.T1", "opened_seq": 5}
    view = A.agenda_view(doc, {"episode": ep}, pool_tasks=[], ref_codes=frozenset())
    assert "<議程>" in view and "</議程>" in view
    assert "需求訪談" in view                                # 語意名,非裸碼(Anthropic Writing tools)


def test_agenda_view_lists_blank_candidates_when_no_episode():
    doc = _doc([_task("需求訪談", tid="T1")])                # 空白 → 候選事件方向
    view = A.agenda_view(doc, {}, pool_tasks=[], ref_codes=frozenset())
    assert "需求訪談" in view                                # 候選方向以任務語意名呈現


def test_agenda_view_no_uuid_leak():
    """artifact 不外洩內部 UUID/裸 path(高訊號語意名原則)。"""
    doc = _doc([_task("需求訪談", tid="abc-123-uuid")])
    view = A.agenda_view(doc, {}, pool_tasks=[], ref_codes=frozenset())
    assert "abc-123-uuid" not in view


# ---- artifact onboarding/curation/writein 分支(T8c-A:吸收退役的 ledger_summary/_ONBOARD_STEER) ----

def test_agenda_view_onboarding_steers_occupation():
    """無職類(文件空白)→ artifact 引導選職類,且明示選職類前不問態度(取代 _ONBOARD_STEER)。"""
    view = A.agenda_view(_blank_doc(), {}, pool_tasks=[], ref_codes=frozenset())
    assert "選職類" in view
    assert "態度" in view                                    # 明示選職類前不問態度
    assert "接下來問:工作態度" not in view                   # 不得指使問態度(BUG-3 舊病)


def test_agenda_view_curation_group_probe():
    """有職類、官方池仍有 unasked → artifact 列名成組反問,且不問態度(取代 ledger_summary curation)。"""
    doc = _doc([_task("需求訪談", tid="C")])                  # 覆蓋 X:T1(名稱對位)
    view = A.agenda_view(doc, {}, pool_tasks=_POOL, ref_codes=frozenset({"X"}))
    assert "自動化腳本維護" in view and "有做" in view          # unasked=X:T9 成組反問
    assert "態度" in view


def test_agenda_view_writein_probe_once():
    """檢查表全處置 → artifact 吐一次 write-in 抓漏;writein_asked 設了就不吐(取代 ledger_summary writein)。"""
    doc = _doc([_task("需求訪談", tid="C")])                  # 覆蓋 X:T1
    state = {"declined": ["X:T9"]}                           # X:T9 declined → 無 unasked
    s1 = A.agenda_view(doc, state, pool_tasks=_POOL, ref_codes=frozenset({"X"}))
    assert "官方沒列" in s1
    s2 = A.agenda_view(doc, {**state, "writein_asked": True},
                       pool_tasks=_POOL, ref_codes=frozenset({"X"}))
    assert "官方沒列" not in s2
