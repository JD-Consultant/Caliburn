"""覆蓋帳本(v2;ADR 0027)——**T4(0033)拆分後的過渡層**。

純覆蓋計算已 move-only 搬至 `coverage.py`(此處 re-export 保住下游 import,
T8 隨梯子退役時清掉);本檔暫留:
- `next_gap` 線性梯子(**已判死,ADR 0033**:議程決策改顧問議程工具+guardrail,
  T8 刪除;在那之前維持 v3 行為不動)。
- session 狀態寫入:attempts(note_attempt)/held(待問)/boundary(劃線)/
  疲勞偵測——T8 改造進 agenda.py(episode 粒度)。
"""
from app.interview.coverage import (  # noqa: F401 —— T4 相容 re-export(T8 清)
    BLOCK_KEYS, MAX_A, MIN_A, MIN_K, MIN_P, MIN_S, SHARE_TOL, STALL_K,
    _gap, _seg, attitudes_missing, blocks_missing, can_finish, checklist,
    coverage, derive_phase, has_occupation, is_stalled, iter_tasks,
    share_sum, task_missing, tier,
)
from app.interview.slots import BUDGET_SLOTS, SLOT_DEFS, gate_missing, slot_filled

SOUL_SLOTS = ("wait_points", "exceptions", "standards")   # 顧問味靈魂槽,next_gap 優先

# onboarding/curation 縫(§16.16、0028 D6):文件還沒任務時先引導,**不掉態度**。
ONBOARD_OCCUPATION = "onboarding:occupation"   # 無 ocs_code:先問他做什麼→查職類→請他選
CURATION_TASKS = "curation:tasks"              # 有 ocs_code:AI 裁剪/官方檢查表反問


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


# --- 議程四態擴充(ADR 0030 T5):covered/refused(=declined)/held/boundary ---
# refused 沿用既有 state["declined"](鍵名不動,語意=受訪者明說不做/不答)。

def push_held(state: dict, question: str, since_turn: int) -> dict:
    """好問題時機不對→存待問清單(去重;backstop 撿漏也走這)。回新 state。"""
    held = list(state.get("held") or [])
    if not any(h.get("q") == question for h in held):
        held.append({"q": question, "since": since_turn})
    return {**state, "held": held}


def pop_held(state: dict) -> tuple[str | None, dict]:
    """取出最早的待問題(FIFO)。回 (question|None, 新 state)。"""
    held = list(state.get("held") or [])
    if not held:
        return None, state
    first = held.pop(0)
    return first.get("q"), {**state, "held": held}


def add_boundary(state: dict, topic: str, *, quote: str = "", since_turn: int = 0) -> dict:
    """受訪者劃線(「這塊不談」)→ 硬遮罩。**無任何程式路徑自動解除**(§6.5):
    只有使用者自己重提該話題、由人/前端明確移除。回新 state。"""
    boundary = list(state.get("boundary") or [])
    if not any(b.get("topic") == topic for b in boundary):
        boundary.append({"topic": topic, "quote": quote, "since": since_turn})
    return {**state, "boundary": boundary}


def in_boundary(state: dict, gap: str | None) -> bool:
    """gap 是否落在劃線區(path 前綴比對;ocs_attitude/curation 等固定串同樣適用)。"""
    if not gap:
        return False
    return any(gap.startswith(str(b.get("topic") or "\x00"))
               for b in (state.get("boundary") or []))


# --- 疲勞偵測(ADR 0030 T5;確定性,收尾三訊號之一) ---

FATIGUE_WINDOW = 3          # 滑動視窗:最近 N 則員工回答
FATIGUE_RATIO = 0.4         # 視窗均長 < 前段均長 × ratio → 疲勞
FATIGUE_PHRASES = ("就這樣", "沒了", "沒有了", "差不多", "就醬", "大概就這些", "先這樣")


def is_fatigued(employee_texts: list[str]) -> bool:
    """回答長度滑動平均連降+敷衍短語(任一成立)。純函式,不用 LLM 判。"""
    if not employee_texts:
        return False
    tail = employee_texts[-FATIGUE_WINDOW:]
    if any(p in (t or "") for p in FATIGUE_PHRASES for t in tail[-2:]):
        return True
    if len(employee_texts) < FATIGUE_WINDOW * 2:
        return False
    head = employee_texts[:-FATIGUE_WINDOW]
    avg = lambda xs: sum(len(x or "") for x in xs) / max(1, len(xs))  # noqa: E731
    return avg(tail) < avg(head) * FATIGUE_RATIO


def note_attempt(state: dict, gap: str | None, progressed: bool) -> dict:
    """回新 state(不就地改):progressed=歸零;否則 +1(供 is_stalled)。"""
    if gap is None:
        return state
    attempts = dict(state.get("attempts") or {})
    attempts[gap] = 0 if progressed else attempts.get(gap, 0) + 1
    return {**state, "attempts": attempts}
