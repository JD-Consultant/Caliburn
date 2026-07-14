"""T1(v2)→ T4(0033)瘦身:僅剩 next_gap 梯子(已判死,T8 隨梯子退役)
與 attempts 狀態;覆蓋計算測試已 move-only 搬至 test_interview_coverage.py。"""
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


CORE = {d: "x" for d in SLOT_DEFS}
CORE["time_share_pct"] = 25


def _core_task(pct=25, **kw):
    d = dict(CORE, time_share_pct=pct)
    return _task(d, outputs=1, p=1, k=2, s=2, **kw)


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


# ---- onboarding(空白文件先引導選職類,不掉態度;§16.16 production bug 8ba32711) ----

def test_next_gap_onboarding_occupation_when_blank():
    """無任務、無職類 → onboarding:occupation(不是態度)。"""
    doc = _doc([])
    assert L.next_gap(doc, {}, {}) == L.ONBOARD_OCCUPATION


def test_next_gap_curation_when_occupation_but_no_tasks():
    """有職類、還沒挑任務 → curation:tasks(0028:AI 預勾裁剪,升級原 onboarding:tasks)。"""
    doc = _doc([])
    doc["ocs_profile"] = {"ocs_code": "ISD2519-002v2"}
    assert L.next_gap(doc, {}, {}) == L.CURATION_TASKS


def test_next_gap_blank_never_asks_attitude():
    """回歸守衛:空白文件即使態度不足,也**絕不**回態度(否則顧問開場問態度→幻覺職類)。"""
    doc = _doc([], attitudes=0)
    assert L.next_gap(doc, {}, {}) != "ocs_attitude"
    # 即使 onboarding 縫被記為「飽和」,也不許掉進態度(onboarding 不受 is_stalled 影響)
    state = {"attempts": {L.ONBOARD_OCCUPATION: L.STALL_K + 5}}
    assert L.next_gap(doc, state, {}) != "ocs_attitude"


def _pool():
    return [
        {"key": "ISD:T1", "name": "需求訪談", "unit": "規劃", "ocs_code": "ISD", "task_code": "T1"},
        {"key": "ISD:T2", "name": "介面設計", "unit": "規劃", "ocs_code": "ISD", "task_code": "T2"},
        {"key": "ISD:T3", "name": "上線部署", "unit": "維運", "ocs_code": "ISD", "task_code": "T3"},
    ]


def _doc_with_codes(codes_or_names, provenance=None):
    t = _core_task(tid="X")
    t["task_codes"] = codes_or_names
    if provenance:
        t["provenance"] = provenance
    doc = _doc([_unit([t], uid="U1")])
    doc["ocs_profile"] = {"ocs_code": "ISD"}
    return doc


def test_next_gap_curation_before_budget_and_stall_fallthrough():
    """有任務但官方池還有 unasked → curation 縫優先(在預算槽前);飽和後讓路 deep。"""
    doc = _doc_with_codes([{"code": "T1", "name": "需求訪談"}])
    doc["ocs_content"]["ocu_units"][0]["tasks"][0]["details"] = {"frequency": "每週"}  # 缺比重
    gap = L.next_gap(doc, {}, {}, pool_tasks=_pool())
    assert gap == L.CURATION_TASKS
    stalled = {"attempts": {L.CURATION_TASKS: L.STALL_K}}
    gap2 = L.next_gap(doc, stalled, {}, pool_tasks=_pool())
    assert gap2.endswith("details.time_share_pct")           # 讓路預算槽


def test_next_gap_no_pool_keeps_v2_behavior():
    """不帶 pool(舊呼叫端)→ 行為同 §16.16(有任務直接走任務縫)。"""
    doc = _doc([_unit([_task({"frequency": "每週"}, tid="X")], uid="U1")])
    doc["ocs_profile"] = {"ocs_code": "ISD"}
    assert L.next_gap(doc, {}, {}).endswith("details.time_share_pct")


# ---- note_attempt / is_stalled ----

def test_note_attempt_increments_and_resets():
    s0 = {}
    s1 = L.note_attempt(s0, "g", progressed=False)
    s2 = L.note_attempt(s1, "g", progressed=False)
    assert s2["attempts"]["g"] == 2 and L.is_stalled(s2, "g")
    s3 = L.note_attempt(s2, "g", progressed=True)
    assert s3["attempts"]["g"] == 0 and not L.is_stalled(s3, "g")
    assert L.note_attempt(s2, None, False) is s2            # gap None = 原樣
