"""覆蓋計算(ADR 0033 T4;自 ledger.py move-only 拆出)。

**純函式、零 I/O、零決策**——只回答「文件現在覆蓋到哪、還缺什麼、能不能收工」;
「下一步問什麼」的決策不在此層(0033:議程決策=顧問議程工具+guardrail)。
單任務判準沿用 slots.gate_missing;門檻常數=ADR 0027 門檻 v1(§16.1:數字可校準,
碼形不變)。attempts 計數等 session 狀態的**寫入**在 agenda 層;此處只讀。
"""
from app.interview.slots import SLOT_DEFS, gate_missing, is_core

SHARE_TOL = 5          # 比重加總 100±5(§14;T14 校準)
STALL_K = 2            # 同一縫隙連續 K 次追問無進帳 → 飽和(iCAP 資料飽和)
MIN_P, MIN_K, MIN_S = 1, 2, 2      # core 任務 indicators/knowledge/skills 下限
MIN_A, MAX_A = 2, 4                # 文件層 attitudes 2–4(iCAP A01–A14 池)
BLOCK_KEYS = ("outputs", "indicators", "knowledge", "skills")   # 能力區塊族


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
    回 True(core)/False(light)/None(預算槽未齊,未定)。"""
    ov = (state.get("tier_override") or {}).get(task_path)
    if ov in ("core", "light"):
        return ov == "core"
    return is_core(task)


def share_sum(doc: dict) -> float:
    """比重加總。非數值(舊資料/使用者手填「25%」字串)防禦跳過——crash 比漏算糟。"""
    total = 0.0
    for _, t, _ in iter_tasks(doc):
        v = (t.get("details") or {}).get("time_share_pct")
        if isinstance(v, (int, float)):
            total += v
    return total


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


def has_occupation(doc: dict, ref_codes: set[str] | frozenset = frozenset()) -> bool:
    """有沒有可用的官方基準:文件主基準 **或** 參考集合(profile.selected_ocs_codes)。
    0029 脫鉤後選職類只寫 profile——只看文件會鬼打牆(session 6f807f1e 事故)。"""
    return bool((doc.get("ocs_profile") or {}).get("ocs_code") or ref_codes)


def checklist(doc: dict, state: dict, pool_tasks: list[dict]) -> dict[str, list[dict]]:
    """官方任務檢查表三態(0028 D6):covered/declined/unasked。
    身分對位:doc 任務 **provenance{ocs_code,task_code}**(主)、名稱相等(備援)。
    **不用 task_codes.code**——web renumber 會把它重寫成位置碼(T1.1),
    與官方碼撞格式會誤判 covered。declined 住 ledger_state["declined"]。"""
    declined = set(state.get("declined") or [])
    doc_prov: set[tuple[str, str]] = set()
    doc_names: set[str] = set()
    for _, t, _ in iter_tasks(doc):
        pv = t.get("provenance") or {}
        if pv.get("ocs_code") and pv.get("task_code"):
            doc_prov.add((str(pv["ocs_code"]), str(pv["task_code"])))
        for tc in (t.get("task_codes") or []):
            if tc.get("name"):
                doc_names.add(tc["name"])
    out: dict[str, list[dict]] = {"covered": [], "declined": [], "unasked": []}
    for pt in pool_tasks:
        if pt.get("key") in declined:
            out["declined"].append(pt)
        elif ((str(pt.get("ocs_code") or ""), str(pt.get("task_code") or "")) in doc_prov
              or pt.get("name") in doc_names):
            out["covered"].append(pt)
        else:
            out["unasked"].append(pt)
    return out


def derive_phase(doc: dict, state: dict,
                 ref_codes: set[str] | frozenset = frozenset()) -> str:
    """議程階段(0028 D2;顯示/引導用,非 gate——由 doc 推導、不落庫,12-Factor F5)。
    onboarding_occupation → task_curation → opks_deep → attitudes_wrapup。"""
    if not has_occupation(doc, ref_codes):
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
