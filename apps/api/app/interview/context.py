"""回合 context 組裝(T8;spec §4②)。

原則(輪 4 記憶體研究):**結構化狀態優先、逐字稿只取近窗**——不整卷重播。
組出:顧問角色 + 焦點任務現況(已填/缺口/預算/已跳過)+ 槽位問法提示 + 可用 path 清單
+ 指令使用規則 + 近 N 回合對話。純函式。
"""
from app.interview.executor import get_at
from app.interview.slots import SLOT_DEFS, gate_missing, is_core

RECENT_TURNS = 12   # v1 近窗(spec §4②)

ROLE_HEADER = """你是 iCAP 職能顧問,正在訪談一位不熟專業術語的員工,幫他完成職務說明書。
語氣友善、一次只問一件事、用員工的話追細節(頻率/數量/工具/等待/例外)。
規則:
- 填槽(set_slot/correct_slot)必附 quote=員工「這次對話中逐字說過」的原話片段。
- 員工提到清單外的工作 → add_task/add_duty(一樣附 quote),不要硬塞進現有槽。
- 對同一槽最多追問 2 次;員工答不出 → skip(附理由)。
- 該任務缺口都處理完才 advance。saturation=true 表示「當前焦點再問也無新資訊」。"""


def _fmt_task_state(doc: dict, task_path: str) -> str:
    task = get_at(doc, task_path)
    if not isinstance(task, dict):
        return "(找不到焦點任務)"
    name = ""
    codes = task.get("task_codes") or []
    if codes:
        name = f"{codes[0].get('code', '')} {codes[0].get('name', '')}"
    details = task.get("details") or {}
    filled = [f"  - {SLOT_DEFS[k].label}({k})= {v!r}"
              for k, v in details.items() if k in SLOT_DEFS and v not in (None, "")]
    missing = gate_missing(task)
    lvl = {True: "core(全套細項)", False: "light(淺掃)", None: "未分級(先問頻率+比重)"}[is_core(task)]
    hints = [f"  - {k}:{SLOT_DEFS[k].label}——{SLOT_DEFS[k].hint}"
             for k in missing if k in SLOT_DEFS]
    return (f"焦點任務:{name}(path={task_path};深問級別:{lvl})\n"
            f"已填:\n" + ("\n".join(filled) or "  (無)") + "\n"
            f"缺口(依序處理):\n" + ("\n".join(hints) or "  (無)") +
            ("\n  - outputs:此任務尚無產出(用 ask 問「做完會產出什麼?」,"
             "產出項走 add 建議)" if "outputs" in missing else ""))


def build_prompt(*, doc: dict, phase: str, focus: dict, counters: dict,
                 recent_turns: list[tuple[str, str]], user_text: str) -> tuple[str, list[str] | None]:
    """回 (prompt, choice_ids)。choice_ids 非 None 才會開放 ask_choice。"""
    task_path = (focus or {}).get("task_path") or ""
    skipped = (focus or {}).get("skipped") or []
    budget_lines = [f"  - {k}:已問 {v} 次" for k, v in (counters or {}).items() if v]
    convo = "\n".join(f"{'員工' if r == 'employee' else '顧問'}:{t}"
                      for r, t in recent_turns[-RECENT_TURNS:])
    slot_paths = (f"槽位 path 格式:{task_path}.details.<槽key>;"
                  f"工作摘要 path:ocs_profile.job_description") if task_path else ""
    parts = [
        ROLE_HEADER,
        f"\n【階段】{phase}",
        f"\n【任務現況】\n{_fmt_task_state(doc, task_path)}" if task_path else "",
        f"\n【追問預算已用】\n" + "\n".join(budget_lines) if budget_lines else "",
        f"\n【已 skip】{skipped}" if skipped else "",
        f"\n【{slot_paths}】" if slot_paths else "",
        f"\n【近期對話】\n{convo}" if convo else "",
        f"\n【員工剛說】{user_text}",
        "\n請輸出這一回合的指令(填得到就填,附原話 quote;然後問下一個缺口)。",
    ]
    return "".join(p for p in parts if p), None   # v1 deep 階段不開 ask_choice
