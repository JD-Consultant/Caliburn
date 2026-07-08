"""覆蓋帳本(v2;ADR 0027、spec 2026-07-08 §1)。單任務判準沿用 slots.gate_missing;
本模組補文件層:OPKS 門檻、比重加總、態度、next_gap 優先序、飽和、完成閘門。

純函式、零 I/O。不可重算的狀態(attempts 計數、tier 覆寫、probe 設定)住
sessions.ledger_state(T2),其餘一律由 doc 重算(12-Factor F5/F12)。

門檻常數=ADR 0027 門檻 v1;§16.1:數字可校準(T14),碼形不變。
"""
from app.interview.slots import (
    BUDGET_SLOTS, SLOT_DEFS, gate_missing, is_core, slot_filled,
)

SHARE_TOL = 5          # 比重加總 100±5(§14;T14 校準)
STALL_K = 2            # 同一縫隙連續 K 次追問無進帳 → 飽和(iCAP 資料飽和)
MIN_P, MIN_K, MIN_S = 1, 2, 2      # core 任務 indicators/knowledge/skills 下限
MIN_A, MAX_A = 2, 4                # 文件層 attitudes 2–4(iCAP A01–A14 池)
SOUL_SLOTS = ("wait_points", "exceptions", "standards")   # 顧問味靈魂槽,next_gap 優先
BLOCK_KEYS = ("outputs", "indicators", "knowledge", "skills")   # 能力區塊族(gap kind=blocks)

# onboarding/curation 縫(§16.16、0028 D6):文件還沒任務時先引導,**不掉態度**。
# 無任務時這兩縫**不受 is_stalled 影響**(選職類/挑任務前不許 fall through 到態度);
# 有任務後的 curation(檢查表成組反問)**尊重 STALL_K**(問兩輪無進帳讓路 deep,避免審訊)。
ONBOARD_OCCUPATION = "onboarding:occupation"   # 無 ocs_code:先問他做什麼→查職類→請他選
CURATION_TASKS = "curation:tasks"              # 有 ocs_code:AI 預勾裁剪/官方檢查表反問


def _seg(item, idx: int) -> str:            # 沿 diff._seg:_tid/_uid/_id 或 index
    if isinstance(item, dict):
        for k in ("_tid", "_uid", "_id"):
            if item.get(k):
                return str(item[k])
    return str(idx)


def iter_tasks(doc: dict):
    """yield (unit, task, task_path);task_path = executor 可解析的全路徑
    (ocs_content.ocu_units.<seg>.tasks.<seg>,與 v1 focus.task_path 同源)。"""
    units = (doc.get("ocs_content") or {}).get("ocu_units") or []
    for ui, u in enumerate(units):
        for ti, t in enumerate(u.get("tasks") or []):
            yield u, t, f"ocs_content.ocu_units.{_seg(u, ui)}.tasks.{_seg(t, ti)}"


def tier(task: dict, task_path: str, state: dict) -> bool | None:
    """深問級別:人工覆寫(ledger_state.tier_override)優先,否則 v1 is_core 啟發。
    回 True(core)/False(light)/None(預算槽未齊,未定)。§16.1:is_core 是否改
    比重×頻率複合判準 = T14 校準,T1 不動 v1。"""
    ov = (state.get("tier_override") or {}).get(task_path)
    if ov in ("core", "light"):
        return ov == "core"
    return is_core(task)


def share_sum(doc: dict) -> float:
    return sum((t.get("details") or {}).get("time_share_pct") or 0
               for _, t, _ in iter_tasks(doc))


def blocks_missing(task: dict) -> list[str]:
    """core P/K/S 缺口(O 由 gate_missing 的 outputs 虛擬 key 承載,不在此重複)。"""
    blocks = task.get("competency_blocks") or []

    def n(field: str) -> int:
        return sum(len(b.get(field) or []) for b in blocks)

    out = []
    if n("indicators") < MIN_P:
        out.append("indicators")
    if n("knowledge") < MIN_K:
        out.append("knowledge")
    if n("skills") < MIN_S:
        out.append("skills")
    return out


def task_missing(task: dict, task_path: str, state: dict, skips: set[str]) -> list[str]:
    """單任務全部缺口=槽(gate_missing,含 outputs 虛擬 key)+ P/K/S(core 才要);
    skips=合法 n/a。"""
    miss = [m for m in gate_missing(task) if m not in skips]
    if tier(task, task_path, state):
        miss += [m for m in blocks_missing(task) if m not in skips]
    return miss


def has_occupation(doc: dict) -> bool:
    return bool((doc.get("ocs_profile") or {}).get("ocs_code"))


def checklist(doc: dict, state: dict, pool_tasks: list[dict]) -> dict[str, list[dict]]:
    """官方任務檢查表三態(0028 D6):covered/declined/unasked。
    pool_tasks=[{key,name,unit,ocs_code,task_code}](service 由 knowledge 組;純函式吃參數)。
    身分對位:doc 任務 task_codes[].code == task_code(主)、名稱相等(備援,編輯器改碼場景)。
    declined 住 ledger_state["declined"](員工明說不做;文件無此任務、不可重算)。"""
    declined = set(state.get("declined") or [])
    doc_codes: set[str] = set()
    doc_names: set[str] = set()
    for _, t, _ in iter_tasks(doc):
        for tc in (t.get("task_codes") or []):
            if tc.get("code"):
                doc_codes.add(str(tc["code"]))
            if tc.get("name"):
                doc_names.add(tc["name"])
    out: dict[str, list[dict]] = {"covered": [], "declined": [], "unasked": []}
    for pt in pool_tasks:
        if pt.get("key") in declined:
            out["declined"].append(pt)
        elif str(pt.get("task_code") or "") in doc_codes or pt.get("name") in doc_names:
            out["covered"].append(pt)
        else:
            out["unasked"].append(pt)
    return out


def derive_phase(doc: dict, state: dict) -> str:
    """議程階段(0028 D2;顯示/引導用,非 gate——由 doc 推導、不落庫,12-Factor F5)。
    onboarding_occupation → task_curation → opks_deep → attitudes_wrapup。"""
    if not has_occupation(doc):
        return "onboarding_occupation"
    rows = list(iter_tasks(doc))
    if not rows:
        return "task_curation"
    if any(task_missing(t, tp, state, set()) for _, t, tp in rows):
        return "opks_deep"
    return "attitudes_wrapup"


def attitudes_missing(doc: dict) -> bool:
    return len((doc.get("ocs_attitude") or {}).get("attitudes") or []) < MIN_A


def _gap(task_path: str, name: str) -> str:
    kind = "blocks" if name in BLOCK_KEYS else "details"
    return f"{task_path}.{kind}.{name}"     # 文件層態度固定字串 "ocs_attitude"


def next_gap(doc: dict, state: dict, skips_by_task: dict[str, set[str]],
             pool_tasks: list[dict] | None = None) -> str | None:
    """下一個該問的縫隙(給顧問的提示,非命令)。優先序:
    ⓪還沒任務→onboarding/curation(選職類/AI 預勾裁剪,不掉態度;§16.16、0028)
    ⓪′有任務但官方檢查表還有 unasked → curation 成組反問(尊重 STALL_K,飽和讓路;D6)
    ①未分級任務的預算槽 ②core 靈魂槽 ③core 其餘細項槽 ④core 能力區塊(O+P/K/S)
    ⑤淺掃殘槽 ⑥文件層態度。已飽和(is_stalled)或已 n/a(skips)的縫隙跳過。"""
    def open_(tp: str, name: str, skips: set[str]) -> str | None:
        g = _gap(tp, name)
        return None if name in skips or is_stalled(state, g) else g

    rows = [(tp, t, skips_by_task.get(tp, set())) for u, t, tp in iter_tasks(doc)]
    if not rows:                                                  # ⓪ 還沒任務(不受 stall)
        return ONBOARD_OCCUPATION if not has_occupation(doc) else CURATION_TASKS
    if (pool_tasks and has_occupation(doc)                        # ⓪′ 檢查表殘項(受 stall)
            and not is_stalled(state, CURATION_TASKS)
            and checklist(doc, state, pool_tasks)["unasked"]):
        return CURATION_TASKS
    for tp, t, sk in rows:                                        # ① 預算槽(分級前提)
        if tier(t, tp, state) is None:
            for k in BUDGET_SLOTS:
                if not slot_filled(t.get("details"), k) and (g := open_(tp, k, sk)):
                    return g
    cores = [(tp, t, sk) for tp, t, sk in rows if tier(t, tp, state)]
    rest = tuple(k for k in SLOT_DEFS if k not in SOUL_SLOTS)
    for phase in (SOUL_SLOTS, rest):                              # ②③ core 細項(靈魂優先)
        for tp, t, sk in cores:
            gm = gate_missing(t)
            for k in phase:
                if k in gm and (g := open_(tp, k, sk)):
                    return g
    for tp, t, sk in cores:                                       # ④ core 能力區塊
        block_gaps = [m for m in gate_missing(t) if m == "outputs"] + blocks_missing(t)
        for name in block_gaps:
            if (g := open_(tp, name, sk)):
                return g
    for tp, t, sk in rows:                                        # ⑤ 淺掃殘槽
        if tier(t, tp, state) is False:
            for k in gate_missing(t):
                if (g := open_(tp, k, sk)):
                    return g
    if attitudes_missing(doc) and not is_stalled(state, "ocs_attitude"):   # ⑥ 態度
        return "ocs_attitude"
    return None


def note_attempt(state: dict, gap: str | None, progressed: bool) -> dict:
    """回新 state(不就地改):progressed=歸零;否則 +1(供 is_stalled)。"""
    if gap is None:
        return state
    attempts = dict(state.get("attempts") or {})
    attempts[gap] = 0 if progressed else attempts.get(gap, 0) + 1
    return {**state, "attempts": attempts}


def is_stalled(state: dict, gap: str) -> bool:
    return (state.get("attempts") or {}).get(gap, 0) >= STALL_K


def coverage(doc: dict, state: dict,
             skips_by_task: dict[str, set[str]] | None = None) -> dict:
    """進度=覆蓋率 {filled, required}(spec §11.1)。required 依 tier 定該任務應填數,
    filled=required−當前缺口;文件層態度計 MIN_A。純顯示用,非閘門。"""
    skips_by_task = skips_by_task or {}
    core_req = len(SLOT_DEFS) + 1 + 3          # 11 細項 + outputs + P/K/S
    filled = required = 0
    for _, t, tp in iter_tasks(doc):
        tr = tier(t, tp, state)
        req = 2 if tr is None else (core_req if tr else len(("frequency",
              "time_share_pct", "standards")) + 1)
        required += req
        filled += req - len(task_missing(t, tp, state, skips_by_task.get(tp, set())))
    n_att = len((doc.get("ocs_attitude") or {}).get("attitudes") or [])
    required += MIN_A
    filled += min(n_att, MIN_A)
    return {"filled": max(0, filled), "required": max(1, required)}


def can_finish(doc: dict, state: dict,
               skips_by_task: dict[str, set[str]]) -> tuple[bool, list[str]]:
    """完成閘門。blockers 全空才放行(飽和縫隙=attempted-insufficient,不擋收工但
    必入人審佇列——「放行≠合格」,標記留痕)。§16.1:P 由每個 core 任務的
    blocks_missing 承載,不設職責層 P gate(否則拒絕黃金範本全淺掃的 R3)。"""
    blockers: list[str] = []
    if abs(share_sum(doc) - 100) > SHARE_TOL:
        blockers.append(f"share_sum={share_sum(doc):g}(需 100±{SHARE_TOL})")
    for _, t, tp in iter_tasks(doc):
        sk = skips_by_task.get(tp, set())
        for m in task_missing(t, tp, state, sk):
            g = _gap(tp, m)
            if not is_stalled(state, g):
                blockers.append(g)
    if attitudes_missing(doc):
        blockers.append("ocs_attitude")
    return (not blockers, blockers)
