"""Executor(T6):把 LLM 的 TurnOutput 確定性地落到文件/建議/證據(ADR 0023/0025)。

信任機制全在這,LLM 一件都繞不過:
- **通道分流**(0025):set/correct 的目標 path ∈ human_touched → 建議層;否則直改。
  add_task/add_duty **一律建議化**(編碼/renumber 是前端 ocsDoc.renumber 的職權,
  server 不重編——人核准後由前端套用,走同一條 PATCH)。
- **quote 驗證**:NFKC+空白摺疊後必須是「員工發言逐字稿」子串;失敗標 unverified
  (retry 由回合服務層負責,executor 只判定)。
- **三重保險**:ask 超每槽預算 → 擋下記 guard;advance 未過覆蓋門檻(扣除 justified
  skip)→ 拒絕回缺口。

Path 文法與 diff.py 同族:段以 `.` 連接;list 段用穩定 id(_tid/_uid/_id)或 index。
純函式:輸入 doc 不變,回新 doc(deep copy)。
"""
import copy
import re
import unicodedata
from dataclasses import dataclass, field

from app.interview.commands import TurnOutput
from app.interview.diff import STABLE_ID_KEYS
from app.interview.slots import gate_missing

ASK_BUDGET_PER_SLOT = 2   # v0 出廠值(校準後修)

_WS = re.compile(r"\s+")


def normalize(s: str) -> str:
    return _WS.sub("", unicodedata.normalize("NFKC", s or ""))


def quote_verified(quote: str, employee_texts: list[str]) -> bool:
    q = normalize(quote)
    if not q:
        return False
    hay = normalize("\n".join(employee_texts))
    return q in hay


# --- path 解析(與 diff.py 同文法) ---

def _step(node, seg: str):
    if isinstance(node, dict):
        return node.get(seg)
    if isinstance(node, list):
        for i, item in enumerate(node):
            if isinstance(item, dict) and any(str(item.get(k)) == seg for k in STABLE_ID_KEYS):
                return item
        if seg.isdigit() and int(seg) < len(node):
            return node[int(seg)]
    return None


def resolve(doc: dict, path: str):
    """回 (parent, last_seg) 供讀寫;走不到 → (None, None)。"""
    segs = path.split(".")
    node = doc
    for seg in segs[:-1]:
        node = _step(node, seg)
        if node is None:
            return None, None
    return node, segs[-1]


def get_at(doc: dict, path: str):
    parent, last = resolve(doc, path)
    if parent is None:
        return None
    return _step(parent, last) if not isinstance(parent, dict) else parent.get(last)


def set_at(doc: dict, path: str, value) -> bool:
    """葉寫入;task 段存在但 `details` 尚無 → 自動建殼。成功回 True。"""
    parent, last = resolve(doc, path)
    if parent is None:
        # 容許 …<task>.details.<slot> 的 details 缺殼:找 task(= "details" 的 parent)建殼
        segs = path.split(".")
        if len(segs) >= 2 and segs[-2] == "details":
            tparent, tlast = resolve(doc, ".".join(segs[:-1]))
            if isinstance(tparent, dict) and tlast == "details":
                tparent.setdefault("details", {})[segs[-1]] = value
                return True
        return False
    if isinstance(parent, dict):
        parent[last] = value
        return True
    return False


# --- 執行結果 ---

@dataclass
class ExecResult:
    new_doc: dict | None = None            # None = 文件無直改
    suggestions: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    say: str = ""
    question: dict | None = None           # {text, target_path}
    widget: dict | None = None             # ask_choice payload
    advanced_to: str | None = None
    counters_delta: dict = field(default_factory=dict)
    skipped_add: list[str] = field(default_factory=list)
    guard_log: list[str] = field(default_factory=list)


def _task_at(doc: dict, task_path: str) -> dict | None:
    node = get_at(doc, task_path)
    return node if isinstance(node, dict) else None


def apply(turn: TurnOutput, *, doc: dict, human_touched: list[str],
          counters: dict, focus: dict, employee_texts: list[str]) -> ExecResult:
    """一回合指令 → 確定性效果。輸入不變;文件有直改才產 new_doc(deep copy)。"""
    res = ExecResult()
    work: dict | None = None   # lazy deep copy
    wrote_any = False          # set 失敗不算直改(new_doc 保持 None)
    touched = set(human_touched or [])
    skipped = set((focus or {}).get("skipped") or [])
    says: list[str] = []

    def _doc() -> dict:
        nonlocal work
        if work is None:
            work = copy.deepcopy(doc)
        return work

    for cmd in turn.commands:
        t = cmd.type
        if t == "reply":
            says.append(cmd.text)

        elif t in ("set_slot", "correct_slot"):
            verified = quote_verified(cmd.quote, employee_texts)
            res.evidence.append({"doc_path": cmd.path, "quote": cmd.quote,
                                 "verified": verified})
            if cmd.path in touched:
                res.suggestions.append({
                    "doc_path": cmd.path, "old_value": get_at(doc, cmd.path),
                    "new_value": cmd.value,
                    "reason": f"{'更正' if t == 'correct_slot' else '訪談'}(quote:{cmd.quote[:30]})",
                })
                res.guard_log.append(f"suggest:{cmd.path}(human_touched)")
            else:
                if set_at(_doc(), cmd.path, cmd.value):
                    wrote_any = True
                    res.guard_log.append(f"write:{cmd.path}")
                else:
                    res.guard_log.append(f"drop:{cmd.path}(path 不存在)")

        elif t in ("add_task", "add_duty"):
            payload = ({"unit_ref": cmd.unit_ref, "name": cmd.name} if t == "add_task"
                       else {"name": cmd.name})
            verified = quote_verified(cmd.quote, employee_texts)
            res.evidence.append({"doc_path": f"{t}:{cmd.name}", "quote": cmd.quote,
                                 "verified": verified})
            res.suggestions.append({
                "doc_path": f"{t}:{cmd.name}", "old_value": None,
                "new_value": payload, "reason": "抓漏(公版外,一律人核准)",
            })
            res.guard_log.append(f"suggest:{t}:{cmd.name}")

        elif t == "ask":
            key = cmd.target_path or "_open"
            used = int((counters or {}).get(key, 0))
            if cmd.target_path and used >= ASK_BUDGET_PER_SLOT:
                res.guard_log.append(f"budget:{key}(≥{ASK_BUDGET_PER_SLOT},ask 擋下)")
                continue
            if res.question is None:      # 一回合只出一題(多的丟 guard_log)
                res.question = {"text": cmd.question, "target_path": cmd.target_path}
                res.counters_delta[key] = used + 1
            else:
                res.guard_log.append(f"drop:多餘 ask({cmd.question[:20]})")

        elif t == "ask_choice":
            if res.widget is None:
                res.widget = {"question": cmd.question, "options": cmd.options,
                              "target_path": cmd.target_path}
            else:
                res.guard_log.append("drop:多餘 ask_choice")

        elif t == "skip":
            res.skipped_add.append(cmd.path)
            skipped.add(cmd.path)
            res.guard_log.append(f"skip:{cmd.path}({cmd.reason})")

        elif t == "advance":
            task_path = (focus or {}).get("task_path")
            task = _task_at(work or doc, task_path) if task_path else None
            if task is not None:
                missing = [k for k in gate_missing(task)
                           if f"{task_path}.details.{k}" not in skipped and k != "outputs"
                           or (k == "outputs" and f"{task_path}.outputs" not in skipped)]
                if missing:
                    res.guard_log.append(f"advance 拒絕:缺 {missing}")
                    continue
            res.advanced_to = cmd.next_focus
            res.guard_log.append(f"advance:{cmd.next_focus}")

    res.say = "\n".join(says)
    res.new_doc = work if wrote_any else None
    return res
