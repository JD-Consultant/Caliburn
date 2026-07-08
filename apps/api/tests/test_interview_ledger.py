"""T1:覆蓋帳本純函式(ADR 0027;spec 2026-07-08 §1)。黃金範本結構當 fixture;
含「全淺掃職責可收工」回歸守衛(§16.1:不設職責層 P gate)。無 DB 無 LLM。"""
from app.interview import ledger as L
from app.interview.slots import SLOT_DEFS


def _block(outputs=0, p=0, k=0, s=0):
    mk = lambda pre, n: [{"code": f"{pre}{i}", "name": "x"} for i in range(n)]  # noqa: E731
    return {"indicators": [{"code": f"P{i}", "text": "x"} for i in range(p)],
            "outputs": mk("O", outputs), "knowledge": mk("K", k), "skills": mk("S", s)}


def _task(details=None, outputs=0, p=0, k=0, s=0, tid=None):
    t = {"task_codes": [], "competency_blocks": [_block(outputs, p, k, s)],
         "details": details}
    if tid:
        t["_tid"] = tid
    return t


def _unit(tasks, uid=None):
    u = {"tasks": tasks}
    if uid:
        u["_uid"] = uid
    return u


def _doc(units, attitudes=0):
    return {"ocs_content": {"ocu_units": units},
            "ocs_attitude": {"attitudes": [{"code": f"A{i}", "name": "x"}
                                           for i in range(attitudes)]}}


# 全套 core 細項(11 槽填滿、比重=25 → is_core True)
CORE = {d: "x" for d in SLOT_DEFS}
CORE["time_share_pct"] = 25
# 全套 light 細項(比重 5、非高頻 → is_core False;LIGHT_SLOTS 齊)
LIGHT = {"frequency": "每季", "time_share_pct": 5, "standards": "主管簽核"}


def _core_task(pct=25, **kw):
    d = dict(CORE, time_share_pct=pct)
    return _task(d, outputs=1, p=1, k=2, s=2, **kw)


def _light_task(pct=5, **kw):
    d = dict(LIGHT, time_share_pct=pct)
    return _task(d, outputs=1, **kw)


# ---- iter_tasks / task_path ----

def test_iter_tasks_path_uses_stable_ids():
    doc = _doc([_unit([_core_task(tid="T1")], uid="U1")])
    rows = list(L.iter_tasks(doc))
    assert len(rows) == 1
    _, _, tp = rows[0]
    assert tp == "ocs_content.ocu_units.U1.tasks.T1"


def test_iter_tasks_path_falls_back_to_index():
    doc = _doc([_unit([_core_task()])])
    _, _, tp = next(iter(L.iter_tasks(doc)))
    assert tp == "ocs_content.ocu_units.0.tasks.0"


# ---- tier(override 優先;否則 is_core) ----

def test_tier_override_beats_heuristic():
    t = _core_task()                        # is_core True
    doc = _doc([_unit([t], uid="U1")])
    _, _, tp = next(iter(L.iter_tasks(doc)))
    assert L.tier(t, tp, {}) is True
    assert L.tier(t, tp, {"tier_override": {tp: "light"}}) is False


def test_tier_none_until_budget_slots_known():
    t = _task({"frequency": "每週"})         # 缺 time_share_pct
    assert L.tier(t, "p", {}) is None


# ---- share_sum ----

def test_share_sum():
    doc = _doc([_unit([_core_task(pct=60), _light_task(pct=40)])])
    assert L.share_sum(doc) == 100


# ---- blocks_missing / task_missing ----

def test_blocks_missing_thresholds():
    assert L.blocks_missing(_block(p=1, k=2, s=2) and _task(outputs=1, p=1, k=2, s=2)) == []
    assert L.blocks_missing(_task(p=0, k=1, s=2)) == ["indicators", "knowledge"]


def test_task_missing_core_needs_blocks_light_does_not():
    core_no_k = _task(dict(CORE), outputs=1, p=1, k=0, s=2, tid="T")
    miss = L.task_missing(core_no_k, "ocs_content.ocu_units.0.tasks.T", {}, set())
    assert "knowledge" in miss
    light = _light_task()
    assert L.task_missing(light, "p", {}, set()) == []       # 淺掃不要求 P/K/S


def test_task_missing_respects_skips():
    core_no_wait = _task({k: "x" for k in SLOT_DEFS if k != "wait_points"} | {"time_share_pct": 25},
                         outputs=1, p=1, k=2, s=2)
    tp = "p"
    assert "wait_points" in L.task_missing(core_no_wait, tp, {}, set())
    assert "wait_points" not in L.task_missing(core_no_wait, tp, {}, {"wait_points"})


# ---- next_gap 優先序 ----

def test_next_gap_budget_first():
    undecided = _task({"frequency": "每週"}, tid="U")        # 缺比重
    core_soul = _core_task(tid="C")
    doc = _doc([_unit([undecided, core_soul], uid="U1")])
    gap = L.next_gap(doc, {}, {})
    assert gap.endswith("tasks.U.details.time_share_pct")


def test_next_gap_soul_before_rest():
    core_missing_soul = _task({k: "x" for k in SLOT_DEFS if k not in ("wait_points", "volume")}
                              | {"time_share_pct": 25}, outputs=1, p=1, k=2, s=2, tid="C")
    doc = _doc([_unit([core_missing_soul], uid="U1")])
    gap = L.next_gap(doc, {}, {})
    assert gap.endswith("details.wait_points")               # 靈魂槽優先於 volume


def test_next_gap_skips_stalled_and_advances():
    core_missing_soul = _task({k: "x" for k in SLOT_DEFS if k not in ("wait_points", "volume")}
                              | {"time_share_pct": 25}, outputs=1, p=1, k=2, s=2, tid="C")
    doc = _doc([_unit([core_missing_soul], uid="U1")])
    stalled_gap = "ocs_content.ocu_units.U1.tasks.C.details.wait_points"
    state = {"attempts": {stalled_gap: L.STALL_K}}
    gap = L.next_gap(doc, state, {})
    assert gap.endswith("details.volume")                    # 飽和的 wait_points 被跳過


def test_next_gap_attitudes_last():
    doc = _doc([_unit([_core_task(pct=100, tid="C")], uid="U1")], attitudes=0)
    assert L.next_gap(doc, {}, {}) == "ocs_attitude"
    doc2 = _doc([_unit([_core_task(pct=100, tid="C")], uid="U1")], attitudes=L.MIN_A)
    assert L.next_gap(doc2, {}, {}) is None                  # 全滿


# ---- note_attempt / is_stalled ----

def test_note_attempt_increments_and_resets():
    s0 = {}
    s1 = L.note_attempt(s0, "g", progressed=False)
    s2 = L.note_attempt(s1, "g", progressed=False)
    assert s2["attempts"]["g"] == 2 and L.is_stalled(s2, "g")
    s3 = L.note_attempt(s2, "g", progressed=True)
    assert s3["attempts"]["g"] == 0 and not L.is_stalled(s3, "g")
    assert L.note_attempt(s2, None, False) is s2            # gap None = 原樣


# ---- can_finish ----

def _finishable():
    # light 任務比重須 <15(否則 is_core 正確判為 core → 要全套槽);core 90 + light 10 = 100
    return _doc([_unit([_core_task(pct=90, tid="C"), _light_task(pct=10, tid="Lt")], uid="U1")],
                attitudes=L.MIN_A)


def test_can_finish_happy():
    ok, blk = L.can_finish(_finishable(), {}, {})
    assert ok and blk == []


def test_can_finish_blocks_on_share_and_attitude_and_slot():
    doc = _finishable()
    doc["ocs_attitude"]["attitudes"] = []                   # 態度不足
    ok, blk = L.can_finish(doc, {}, {})
    assert not ok and "ocs_attitude" in blk

    doc2 = _doc([_unit([_core_task(pct=50, tid="C")], uid="U1")], attitudes=L.MIN_A)  # 比重 50≠100
    ok2, blk2 = L.can_finish(doc2, {}, {})
    assert not ok2 and any("share_sum" in b for b in blk2)


def test_can_finish_all_light_duty_ok():
    """§16.1 回歸守衛:全淺掃職責(黃金範本 R3)不因缺 core P 而卡關。"""
    doc = _doc([_unit([_core_task(pct=90, tid="C")], uid="U1"),
                _unit([_light_task(pct=5, tid="L1"), _light_task(pct=5, tid="L2")], uid="U2")],
               attitudes=L.MIN_A)
    ok, blk = L.can_finish(doc, {}, {})
    assert ok, blk


def test_can_finish_stalled_gap_does_not_block():
    doc = _doc([_unit([_task({k: "x" for k in SLOT_DEFS if k != "exceptions"}
                             | {"time_share_pct": 100}, outputs=1, p=1, k=2, s=2, tid="C")],
                      uid="U1")], attitudes=L.MIN_A)
    gap = "ocs_content.ocu_units.U1.tasks.C.details.exceptions"
    ok0, _ = L.can_finish(doc, {}, {})
    assert not ok0                                          # 缺 exceptions → 擋
    ok1, _ = L.can_finish(doc, {"attempts": {gap: L.STALL_K}}, {})
    assert ok1                                              # 飽和標記 → 放行(留痕交人審)
