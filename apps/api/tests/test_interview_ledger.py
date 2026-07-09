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


# ---- 檢查表三態 / phase 推導 / curation 縫(0028 T1;D2/D6) ----

def _pool():
    return [
        {"key": "ISD:T1", "name": "需求訪談", "unit": "規劃", "ocs_code": "ISD", "task_code": "T1"},
        {"key": "ISD:T2", "name": "介面設計", "unit": "規劃", "ocs_code": "ISD", "task_code": "T2"},
        {"key": "ISD:T3", "name": "上線部署", "unit": "維運", "ocs_code": "ISD", "task_code": "T3"},
    ]


def _doc_with_codes(codes_or_names, provenance=None):
    """一個任務,task_codes/provenance 指定(供身分對位測試)。"""
    t = _core_task(tid="X")
    t["task_codes"] = codes_or_names
    if provenance:
        t["provenance"] = provenance
    doc = _doc([_unit([t], uid="U1")])
    doc["ocs_profile"] = {"ocs_code": "ISD"}
    return doc


def test_checklist_three_states():
    """身分=provenance(taskFromPool 寫入的官方身分),非 task_codes.code(位置碼)。"""
    doc = _doc_with_codes([{"code": "T1.1", "name": "客戶需求討論會"}],   # 改過名
                          provenance={"ocs_code": "ISD", "task_code": "T1"})
    cl = L.checklist(doc, {"declined": ["ISD:T3"]}, _pool())
    assert [t["key"] for t in cl["covered"]] == ["ISD:T1"]
    assert [t["key"] for t in cl["declined"]] == ["ISD:T3"]
    assert [t["key"] for t in cl["unasked"]] == ["ISD:T2"]


def test_checklist_name_fallback():
    """無 provenance(自訂/舊資料)用名稱備援對位。"""
    doc = _doc_with_codes([{"code": "X9", "name": "介面設計"}])
    cl = L.checklist(doc, {}, _pool())
    assert "ISD:T2" in [t["key"] for t in cl["covered"]]


def test_checklist_positional_code_not_mistaken_for_official():
    """回歸守衛:web renumber 的位置碼(T1)撞官方碼格式,**不得**誤判 covered
    (§T7 發現:task_codes.code=位置碼非官方身分)。"""
    doc = _doc_with_codes([{"code": "T1", "name": "完全不同的自訂任務"}])
    cl = L.checklist(doc, {}, _pool())
    assert [t["key"] for t in cl["unasked"]] == [p["key"] for p in _pool()]


def test_derive_phase_progression():
    blank = _doc([])
    assert L.derive_phase(blank, {}) == "onboarding_occupation"
    blank["ocs_profile"] = {"ocs_code": "ISD"}
    assert L.derive_phase(blank, {}) == "task_curation"
    gaps = _doc([_unit([_task({"frequency": "每週"}, tid="X")], uid="U1")])
    gaps["ocs_profile"] = {"ocs_code": "ISD"}
    assert L.derive_phase(gaps, {}) == "opks_deep"
    done = _finishable()
    done["ocs_profile"] = {"ocs_code": "ISD"}
    assert L.derive_phase(done, {}) == "attitudes_wrapup"


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


def test_coverage_ratio():
    empty = _doc([_unit([_core_task(pct=100, tid="C")], uid="U1")], attitudes=0)
    cov = L.coverage(empty, {})
    assert cov["required"] == (len(SLOT_DEFS) + 1 + 3) + L.MIN_A   # core 15 + 態度 2
    # 全填任務 + 態度足 → filled == required
    full = _finishable()
    fc = L.coverage(full, {})
    assert fc["filled"] == fc["required"]


def test_can_finish_stalled_gap_does_not_block():
    doc = _doc([_unit([_task({k: "x" for k in SLOT_DEFS if k != "exceptions"}
                             | {"time_share_pct": 100}, outputs=1, p=1, k=2, s=2, tid="C")],
                      uid="U1")], attitudes=L.MIN_A)
    gap = "ocs_content.ocu_units.U1.tasks.C.details.exceptions"
    ok0, _ = L.can_finish(doc, {}, {})
    assert not ok0                                          # 缺 exceptions → 擋
    ok1, _ = L.can_finish(doc, {"attempts": {gap: L.STALL_K}}, {})
    assert ok1                                              # 飽和標記 → 放行(留痕交人審)
