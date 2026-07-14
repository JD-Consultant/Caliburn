"""槽位定義與覆蓋率門檻(T4;黃金範本 v0 §8.3 定版,ADR 0023 三重保險之「覆蓋率」)。

- SLOT_DEFS:11 個任務細項槽(契約 task.details;outputs 另由能力區塊承載)。
- 深問預算(O*NET core/supplemental 判準的 v0 實作):先便宜問到「頻率+比重」,
  兩者已知才分級——core(全套 11 槽+outputs)/ light(頻率/比重/完成標準/outputs)。
- `gate_missing(task)` 是 executor 放行 `advance` 的唯一依據(缺口清單;空=放行)。
- 門檻數字為 v0 出廠值,校準(plan T14)後修——改數字不改碼形。純函式、零 I/O。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SlotDef:
    key: str
    label: str
    hint: str   # 給 LLM 的問法提示(prompt 素材;出處=黃金範本/勞動部五面向)


SLOT_DEFS: dict[str, SlotDef] = {d.key: d for d in [
    SlotDef("frequency", "頻率", "多久做一次?固定週期還是遇到什麼才做?"),
    SlotDef("time_share_pct", "工作比重", "這件事大概佔你工作時間的幾成?(全部任務加總約 100%)"),
    SlotDef("duration", "單次耗時", "做一輪大概要多久?"),
    SlotDef("volume", "數量批次", "一次處理多少?(幾件/幾條/多少量)"),
    SlotDef("trigger", "觸發條件", "什麼情況下會開始做?(排程/有人指派/事件發生)"),
    SlotDef("inputs", "準備材料", "開始前要準備什麼?(材料/文件/資料來源)"),
    SlotDef("tools", "工具系統", "用什麼工具或系統做?"),
    SlotDef("collaborators", "協作對象", "誰給你輸入?產出交給誰?要會簽誰?"),
    SlotDef("wait_points", "等待瓶頸", "過程中會卡在等誰/等什麼嗎?通常等多久?"),
    SlotDef("exceptions", "例外處理", "常見的困難或例外?遇到怎麼處理?"),
    SlotDef("standards", "完成標準", "怎樣算做完、做好?(誰驗收/什麼條件)"),
]}

# 深問預算槽(最先問;分級依據)
BUDGET_SLOTS = ("frequency", "time_share_pct")
# 淺掃門檻槽(supplemental 任務只要求這些;outputs 另計)
LIGHT_SLOTS = ("frequency", "time_share_pct", "standards")

# v0 出廠門檻(T14 校準後修數字)
CORE_TIME_SHARE_PCT = 15          # 比重 ≥15% → core
HIGH_FREQ_MARKERS = ("每日", "每天", "每週", "每周")   # 高頻 → core

# 數值槽(契約上是數;書記 schema 允許 string|number → 寫入前必經 coerce_slot_value)
_PCT_RE = __import__("re").compile(r"(\d+(?:\.\d+)?)")


def coerce_slot_value(key: str, value):
    """槽值正規化(寫入路徑唯一入口):time_share_pct「25%」/「約 25」→ 25.0;
    抽不出數字就保留原值(slot_filled 仍視為已答;數值消費端各自防禦跳過)。"""
    if key == "time_share_pct" and isinstance(value, str):
        m = _PCT_RE.search(value)
        if m:
            return float(m.group(1))
    return value


def slot_filled(details: dict | None, key: str) -> bool:
    v = (details or {}).get(key)
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    return True   # 數值(含 0)視為已答


def outputs_filled(task: dict) -> bool:
    for block in task.get("competency_blocks") or []:
        if block.get("outputs"):
            return True
    return False


def is_core(task: dict) -> bool | None:
    """core/supplemental 分級;頻率+比重未齊 → None(未定,先問預算槽)。"""
    details = task.get("details") or {}
    if not (slot_filled(details, "frequency") and slot_filled(details, "time_share_pct")):
        return None
    pct = details.get("time_share_pct")
    if isinstance(pct, (int, float)) and pct >= CORE_TIME_SHARE_PCT:
        return True
    freq = str(details.get("frequency") or "")
    return any(m in freq for m in HIGH_FREQ_MARKERS)


def gate_missing(task: dict) -> list[str]:
    """`advance` 放行判準:回缺口槽 key 清單(`outputs` 為虛擬 key);空 = 放行。"""
    details = task.get("details") or {}
    lvl = is_core(task)
    if lvl is None:
        return [k for k in BUDGET_SLOTS if not slot_filled(details, k)]
    keys = tuple(SLOT_DEFS) if lvl else LIGHT_SLOTS
    missing = [k for k in keys if not slot_filled(details, k)]
    if not outputs_filled(task):
        missing.append("outputs")
    return missing
