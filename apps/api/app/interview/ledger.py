"""覆蓋帳本(v2;ADR 0027)——**T4(0033)拆分後的過渡層**。

純覆蓋計算已 move-only 搬至 `coverage.py`、議程狀態機(held/boundary/疲勞/attempts)
已搬至 `agenda.py`(此處 re-export 保住下游 import,T8c-A 隨梯子退役時清掉);
本檔僅剩 `next_gap` 線性梯子(**已判死,ADR 0033**:議程決策改顧問議程工具+guardrail,
T8c-A 刪除;在那之前維持 v3 行為不動)。
"""
from app.interview.agenda import (  # noqa: F401 —— T8c move-only:狀態機搬 agenda,re-export 過渡
    add_boundary, in_boundary, is_fatigued, note_attempt, pop_held, push_held,
)
from app.interview.coverage import (  # noqa: F401 —— T4 相容 re-export(T8c-A 清)
    BLOCK_KEYS, CURATION_TASKS, MAX_A, MIN_A, MIN_K, MIN_P, MIN_S,
    ONBOARD_OCCUPATION, SHARE_TOL, STALL_K,
    _gap, _seg, attitudes_missing, blocks_missing, can_finish, checklist,
    coverage, derive_phase, has_occupation, is_stalled, iter_tasks,
    share_sum, should_curate, task_missing, tier,
)
from app.interview.slots import BUDGET_SLOTS, SLOT_DEFS, gate_missing, slot_filled

SOUL_SLOTS = ("wait_points", "exceptions", "standards")   # 顧問味靈魂槽,next_gap 優先


def next_gap(doc: dict, state: dict, skips_by_task: dict[str, set[str]],
             pool_tasks: list[dict] | None = None,
             ref_codes: set[str] | frozenset = frozenset()) -> str | None:
    """下一個該問的縫隙(給顧問的提示,非命令)。優先序:
    ⓪還沒任務→onboarding/curation ⓪′檢查表 unasked→curation(尊重 STALL_K)
    ①未分級任務的預算槽 ②core 靈魂槽 ③core 其餘細項槽 ④core 能力區塊(O+P/K/S)
    ⑤淺掃殘槽 ⑥文件層態度。已飽和(is_stalled)或已 n/a(skips)的縫隙跳過。
    【ADR 0033 已判死:P 排 ④ 在 bulk 勾任務後不可達;T8 刪除,勿再調優先序。】"""
    def open_(tp: str, name: str, skips: set[str]) -> str | None:
        g = _gap(tp, name)
        return None if (name in skips or is_stalled(state, g)
                        or in_boundary(state, g)) else g

    rows = [(tp, t, skips_by_task.get(tp, set())) for u, t, tp in iter_tasks(doc)]
    if not rows:                                                  # ⓪ 還沒任務(不受 stall)
        return ONBOARD_OCCUPATION if not has_occupation(doc, ref_codes) else CURATION_TASKS
    if (pool_tasks and has_occupation(doc, ref_codes)             # ⓪′ 檢查表殘項(受 stall)
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
    if (attitudes_missing(doc) and not is_stalled(state, "ocs_attitude")   # ⑥ 態度
            and not in_boundary(state, "ocs_attitude")):
        return "ocs_attitude"
    return None
