"""Executor(T6):把 LLM 的 TurnOutput 確定性地落到文件/建議/證據(ADR 0023/0025)。

信任機制全在這,LLM 一件都繞不過:
- **通道分流**(0025):set/correct 的目標 path ∈ human_touched → 建議層;否則直改。
  add_task/add_duty **一律建議化**(編碼/renumber 是前端 ocsDoc.renumber 的職權,
  server 不重編——人核准後由前端套用,走同一條 PATCH)。
- **quote 驗證**:NFKC+空白摺疊後必須是「員工發言逐字稿」子串;失敗標 unverified
  (retry 由回合服務層負責,executor 只判定)。
- **三重保險**:ask 超每槽預算 → 自動 justified-skip 該槽(政策的確定性收尾);
  advance 未過覆蓋門檻(扣除 justified skip)→ 拒絕回缺口。
- **保底輸出**:回合恆有 say/question/widget——模型漏 reply/ask 或 ask 被擋時,
  確定性補確認語+下一缺口模板題(真人試訪 2026-07-06:靜默回合=頭號死穴)。

Path 文法與 diff.py 同族:段以 `.` 連接;list 段用穩定 id(_tid/_uid/_id)或 index。
純函式:輸入 doc 不變,回新 doc(deep copy)。
"""
import copy
from dataclasses import dataclass, field

from app.interview.commands import TurnOutput
# 螺絲已搬家(ADR 0030 T3):path 解析住 docpath、quote 驗證住 verify。
# 此處轉口 re-export 供 v1 測試沿用;本檔其餘為 v1 死碼,T12 隨檔退場。
from app.interview.docpath import get_at, resolve, set_at, step as _step  # noqa: F401
from app.interview.slots import SLOT_DEFS, gate_missing
from app.interview.verify import normalize, quote_verified  # noqa: F401

ASK_BUDGET_PER_SLOT = 2   # v0 出廠值(校準後修)

# set/correct 可寫的非槽位路徑(其餘一律 <task>.details.<SLOT_DEFS key>)
WRITE_WHITELIST = ("ocs_profile.job_description",)


def writable_path(path: str) -> bool:
    """寫入白名單(defense-in-depth:schema enum 之外的第二道)。"""
    if path in WRITE_WHITELIST:
        return True
    segs = path.split(".")
    return len(segs) >= 3 and segs[-2] == "details" and segs[-1] in SLOT_DEFS


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
    written: list[tuple[str, object]] = []   # 保底確認語素材

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
            if not writable_path(cmd.path):
                res.guard_log.append(f"drop:{cmd.path}(未知槽,白名單擋下)")
                continue
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
                    written.append((cmd.path, cmd.value))
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
                res.guard_log.append(
                    f"budget:{key}(≥{ASK_BUDGET_PER_SLOT},ask 擋下→自動 skip)")
                if cmd.target_path not in skipped:      # 政策收尾:問到頂=跳過往前走
                    res.skipped_add.append(cmd.target_path)
                    skipped.add(cmd.target_path)
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
    _ensure_visible(res, doc=work or doc, focus=focus, counters=counters,
                    skipped=skipped, written=written)
    return res


# --- 保底輸出(回合恆有可見產出;純函式的最後一道) ---

def _leaf_label(path: str) -> str:
    leaf = path.split(".")[-1]
    return SLOT_DEFS[leaf].label if leaf in SLOT_DEFS else leaf


def _next_gap_question(task: dict, task_path: str, skipped: set,
                       counters: dict, delta: dict) -> tuple[str, str | None]:
    """(題目, path) 或 (收尾語, None)。缺口依 gate_missing 序,跳過 skipped/預算耗盡。"""
    remaining = []
    for k in gate_missing(task):
        p = f"{task_path}.outputs" if k == "outputs" else f"{task_path}.details.{k}"
        if p not in skipped:
            remaining.append((k, p))
    for k, p in remaining:
        used = max(int((counters or {}).get(p, 0)), int((delta or {}).get(p, 0)))
        if used >= ASK_BUDGET_PER_SLOT:
            continue
        text = ("做完這個任務會產出什麼?(報表、文件或成品之類)" if k == "outputs"
                else SLOT_DEFS[k].hint)
        return text, p
    return ("這個任務的缺口都補齊了,可以往下一個任務走。" if not remaining
            else "剩下的先跳過,我們繼續。"), None


def _ensure_visible(res: ExecResult, *, doc: dict, focus: dict, counters: dict,
                    skipped: set, written: list[tuple[str, object]]) -> None:
    """回合恆有『可見 say』+『前進動作』。模型漏 ask(只 set+reply)也補下一缺口題,
    避免側欄只回話卻不問、對話停在原地(校準#2 dump 實證)。"""
    # 已有問題/選單 = 前進動作齊備,不動
    if res.question is not None or res.widget is not None:
        return
    task_path = (focus or {}).get("task_path")
    task = _task_at(doc, task_path) if task_path else None
    # 補前進問題:非 advance 收尾、有焦點任務、還有缺口 → 問下一個
    if not res.advanced_to and task is not None:
        text, qpath = _next_gap_question(task, task_path, skipped,
                                         counters, res.counters_delta)
        if qpath:
            used = max(int((counters or {}).get(qpath, 0)),
                       int(res.counters_delta.get(qpath, 0)))
            res.question = {"text": text, "target_path": qpath}
            res.counters_delta[qpath] = used + 1
    # 補確認語:模型連 reply 都沒給時(有 reply 就尊重模型的話,不疊加)
    if not res.say:
        bits: list[str] = []
        if written:
            bits.append("已記下:" + "、".join(f"{_leaf_label(p)}={v}" for p, v in written))
        if res.suggestions:
            names = "、".join(
                (s["new_value"].get("name") if isinstance(s["new_value"], dict)
                 else f"{_leaf_label(s['doc_path'])}={s['new_value']}")
                for s in res.suggestions)
            bits.append(f"「{names}」我先放進上方的建議卡片,你核准後才會寫進文件。")
        if res.advanced_to:
            bits.append("這個任務先到這裡,我們繼續下一個。")
        elif res.question is None:
            bits.append("這個任務的細節都補齊了,我們可以往下一個任務走。")
        res.say = "\n".join(bits) or "收到。"
