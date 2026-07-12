"""回合 context 組裝(T8;spec §4②)。

原則(輪 4 記憶體研究):**結構化狀態優先、逐字稿只取近窗**——不整卷重播。
組出:顧問角色 + 焦點任務現況(已填/缺口/預算/已跳過)+ 槽位問法提示 + 可用 path 清單
+ 指令使用規則 + 近 N 回合對話。純函式。
"""
from app.interview.docpath import get_at
from app.interview.slots import SLOT_DEFS, gate_missing, is_core

RECENT_TURNS = 12   # v1 近窗(spec §4②)

# 資深顧問操作守則(對話品質研究 2026-07-06:CTA/CDM + LLM 訪談員實證 + 對話修復)。
# 這是 LLM 的那條線(理解+措辭);填哪槽/能否 advance/quote 驗證仍全在 executor。
ROLE_HEADER = """你是資深 iCAP 職能顧問,正在訪談一位不熟術語的員工,要把他「實際怎麼做、
卻未必說得出口」的工作細節問出來,寫成職務說明書。

最重要的一條(不可違反):**員工的話裡只要有可填的細節,你這一回合就要用 set_slot 落槽
(附 quote=他的原話)**。回述、追問、問下一題都**不能取代**落槽——先落槽,再做其他。
(校準教訓:把答案「回述」一遍卻不落槽,等於沒問到。)

在「先落槽」的前提下,像頂尖訪談員那樣:
1. 接話:落槽的同一回合,用一句話(reply)以員工自己的說法回述確認,再問下一題,別冷冰冰只丟問題。
2. 只有真的含糊才追一層:答案空泛到填不進去(「還好」「就用電腦」)才先追問變具體再落槽;
   答案已經夠具體就直接落槽,別為追問而追問。
3. 卡住就修復、不要重問:員工說「剛剛就說了/你沒在聽/為什麼不回我」時,是你漏接了——
   先承認,用他**已經說過的話**回填落槽+確認,**絕不**再問一次一樣的問題。
4. 錨在具體事件:與其抽象問「你的流程?」,不如問最近一次的實例,頻率/數量/工具/等待/例外自然浮現。

填槽硬規則:
- set_slot/correct_slot 必附 quote=員工「這次對話中逐字說過」的原話片段。
- 員工提到清單外的工作 → add_task/add_duty(附 quote),不要硬塞進現有槽;這會進上方
  「建議卡片」,員工核准後才寫入文件——員工若問「要不要套用/這是什麼」,說明那是待核准的建議。
- 對同一槽最多追問 2 次;員工真的答不出 → skip(附理由)。
- 該任務缺口都處理完才 advance。saturation=true 表示「當前焦點再問也無新資訊」。"""


def _slot_path(task_path: str, key: str) -> str:
    return f"{task_path}.outputs" if key == "outputs" else f"{task_path}.details.{key}"


def _fmt_task_state(doc: dict, task_path: str, skipped: set[str]) -> str:
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
    # 缺口扣除已 skip(與 executor _next_gap_question 同源)——不再重問已跳過的槽
    missing = [k for k in gate_missing(task) if _slot_path(task_path, k) not in skipped]
    lvl = {True: "core(全套細項)", False: "light(淺掃)", None: "未分級(先問頻率+比重)"}[is_core(task)]
    hints = [f"  - {k}:{SLOT_DEFS[k].label}——{SLOT_DEFS[k].hint}"
             for k in missing if k in SLOT_DEFS]
    return (f"焦點任務:{name}(path={task_path};深問級別:{lvl})\n"
            f"已填(回述時用員工原本的說法):\n" + ("\n".join(filled) or "  (無)") + "\n"
            f"缺口(依序處理;已跳過的不再問):\n" + ("\n".join(hints) or "  (無)") +
            ("\n  - outputs:此任務尚無產出(用 ask 問「做完會產出什麼?」,"
             "產出項走 add 建議)" if "outputs" in missing else ""))


def build_prompt(*, doc: dict, phase: str, focus: dict, counters: dict,
                 recent_turns: list[tuple[str, str]], user_text: str,
                 pending: list[str] | None = None) -> tuple[str, list[str] | None]:
    """回 (prompt, choice_ids)。choice_ids 非 None 才會開放 ask_choice。
    pending=待核准建議的短標籤(員工可能問到卡片;RC3 2026-07-06)。"""
    task_path = (focus or {}).get("task_path") or ""
    skipped = set((focus or {}).get("skipped") or [])
    budget_lines = [f"  - {k}:已問 {v} 次" for k, v in (counters or {}).items() if v]
    convo = "\n".join(f"{'員工' if r == 'employee' else '顧問'}:{t}"
                      for r, t in recent_turns[-RECENT_TURNS:])
    slot_paths = (f"槽位 path 格式:{task_path}.details.<槽key>;"
                  f"工作摘要 path:ocs_profile.job_description") if task_path else ""
    parts = [
        ROLE_HEADER,
        f"\n【階段】{phase}",
        f"\n【任務現況】\n{_fmt_task_state(doc, task_path, skipped)}" if task_path else "",
        f"\n【追問預算已用】\n" + "\n".join(budget_lines) if budget_lines else "",
        f"\n【待核准建議(員工可能會問到,別重問;向他說明是待核准)】\n  - "
        + "\n  - ".join(pending) if pending else "",
        f"\n【{slot_paths}】" if slot_paths else "",
        f"\n【近期對話】\n{convo}" if convo else "",
        f"\n【員工剛說】{user_text}",
        "\n請輸出這一回合的指令:員工的話有可填細節就**先 set_slot 落槽(附 quote)**,"
        "再用一句話回述、問下一個缺口;答案真的含糊才追一層。",
    ]
    return "".join(p for p in parts if p), None   # v1 deep 階段不開 ask_choice
