"""議程 agenda.py(ADR 0033 T5)——事件驅動議程的**確定性事實層**。

家規(§2.4 骨架):此層**不做決策**(不決定「下一步問什麼」——那是顧問議程工具
+guardrail)。此層只:①維護 episode 狀態機(open/close/查詢);②由覆蓋+事件狀態
確定性算出訊號(飽和/過長/該開沒開/預算);③把上述組成高訊號 artifact 注入顧問
context(取代退役的 next_gap/ledger_summary 單行 hint)。純函式、零 I/O、零 LLM。

裁決依據(spec 2026-07-14 §3.3/§3.4/§3.6):
- ① 收益=本回合**任何**落地(跨任務落地是 feature,不限事件目標任務)。
- ② 事件開 ≥EPISODE_SOFT_MAX 輪 → 軟提示(不強制;強制只在連續零收益 3 輪)。
- ③ open target 含 "free"(自發話題;HierTOD mixed-initiative)。
"""
from app.interview import coverage as C

TURN_BUDGET = 40             # 硬預算(沿 service.TURN_BUDGET;收尾三訊號之一)
DRY_STALL = 2                # 連續零收益 N 輪 → 飽和提示
DRY_AUTOCLOSE = 3            # 連續零收益 N 輪 → 強制收割換場
EPISODE_SOFT_MAX = 6         # 事件開 ≥N 輪 → 軟提示(T10 驗收:單事件 ≤6 輪)
NO_EPISODE_NUDGE = 2         # 無事件連 N 輪未開 → 強化提示
_BLANK_CANDIDATES = 3        # artifact 列前 N 個空白事件方向


# ---- episode 狀態機(狀態住 sessions.ledger_state;此層純函式回新 state) ----

def episode_state(state: dict) -> dict | None:
    """進行中的事件(None=沒有)。"""
    ep = state.get("episode")
    return ep if isinstance(ep, dict) and ep.get("opened_seq") is not None else None


def open_episode(state: dict, *, target: str, seq: int, note: str = "") -> dict:
    """開一個事件(target=覆蓋空白區 task_path 或 "free")。回新 state。"""
    ep = {"target": target, "opened_seq": seq, "dry_streak": 0}
    if note:
        ep["note"] = note
    return {**state, "episode": ep, "no_episode_streak": 0}


def close_episode(state: dict, *, reason: str, seq: int) -> dict:
    """收一個事件 → 歸檔進 episodes、清進行中。回新 state。reason∈saturated|covered|
    user_shifted|auto(guardrail)。"""
    ep = episode_state(state) or {}
    archived = {**ep, "reason": reason, "closed_seq": seq}
    episodes = list(state.get("episodes") or []) + [archived]
    new = {**state, "episodes": episodes, "no_episode_streak": 0}
    new["episode"] = None
    return new


def episode_yield(ops: list[dict], episode: dict) -> bool:
    """裁決①:本回合是否有收益=**任何** op 落地(不限事件目標任務;跨任務=feature)。"""
    return bool(ops)


def bump_streaks(state: dict, *, has_episode: bool, progressed: bool) -> dict:
    """回合收帳:更新 dry_streak(事件內零收益連數)/ no_episode_streak。回新 state。"""
    new = dict(state)
    ep = episode_state(state)
    if ep is not None:
        streak = 0 if progressed else int(ep.get("dry_streak") or 0) + 1
        new["episode"] = {**ep, "dry_streak": streak}
        new["no_episode_streak"] = 0
    else:
        new["no_episode_streak"] = int(state.get("no_episode_streak") or 0) + 1
    return new


# ---- 訊號(確定性;guardrail 後衛,spec §3.6) ----

def signals(state: dict, turns_n: int) -> dict:
    """回訊號 dict(全確定性;service 據以注入提示/觸發 auto-close)。"""
    ep = episode_state(state)
    dry = int((ep or {}).get("dry_streak") or 0)
    length = (turns_n - int(ep["opened_seq"])) if ep else 0
    return {
        "stalled_episode": ep is not None and dry >= DRY_STALL,
        "auto_close": ep is not None and dry >= DRY_AUTOCLOSE,
        "long_episode": ep is not None and length >= EPISODE_SOFT_MAX,
        "no_episode_nudge": ep is None
            and int(state.get("no_episode_streak") or 0) >= NO_EPISODE_NUDGE,
        "budget": turns_n >= TURN_BUDGET,
    }


# ---- 覆蓋地圖(語意名;candidate 事件方向) ----

def _task_label(task: dict) -> str:
    codes = task.get("task_codes") or []
    return (codes[0].get("name") if codes else None) or "(未命名任務)"


def blank_candidates(doc: dict, state: dict,
                     ref_codes: frozenset = frozenset()) -> list[dict]:
    """覆蓋空白區 → 候選事件方向(前 N;語意標籤,id=task_path 穩定)。
    缺口越多越前(深挖收益最大)。"""
    rows = []
    for _, t, tp in C.iter_tasks(doc):
        miss = C.task_missing(t, tp, state, set())
        if miss:
            rows.append((len(miss), tp, _task_label(t)))
    rows.sort(reverse=True)
    # ref=短穩定索引(c1/c2…):artifact 與 open_episode enum 共用,零 UUID 外洩;
    # id=task_path(含 _tid),供 T6 建 ref→target 對照,**不進 artifact 文字**。
    return [{"ref": f"c{i+1}", "id": tp, "label": f"{label} 最近一次實際發生的事",
             "gaps": n}
            for i, (n, tp, label) in enumerate(rows[:_BLANK_CANDIDATES])]


def _coverage_line(doc: dict, state: dict) -> str:
    rows = list(C.iter_tasks(doc))
    total = len(rows)
    fed = sum(1 for _, t, tp in rows if not C.task_missing(t, tp, state, set()))
    return f"已餵飽 {fed}/{total} 個任務"


# ---- artifact(注入顧問 context;spec §3.3) ----

def agenda_view(doc: dict, state: dict, *, pool_tasks: list[dict],
                ref_codes: frozenset = frozenset(), turns_n: int = 0) -> str:
    """高訊號議程區塊。語意名(不外洩 UUID/裸 path);20 任務地圖壓縮成計數+前 N 名單。"""
    lines: list[str] = []
    ep = episode_state(state)
    if ep is not None:
        length = (turns_n - int(ep["opened_seq"])) if turns_n else "?"
        name = ep.get("note") or (
            _episode_target_label(doc, ep["target"]) if ep["target"] != "free" else "自發話題")
        lines.append(f"進行中事件:「{name}」(第 {length} 輪)")
    else:
        lines.append("目前沒有進行中事件(可開新事件)")

    lines.append("覆蓋:" + _coverage_line(doc, state))

    cands = blank_candidates(doc, state, ref_codes)
    if cands:
        lines.append("候選事件方向(空白最多優先;open_episode 用 ref):")
        lines += [f"  - {c['ref']}. {c['label']}" for c in cands]

    sig = signals(state, turns_n) if turns_n else {}
    active = [k for k in ("stalled_episode", "long_episode", "no_episode_nudge", "budget")
              if sig.get(k)]
    if active:
        hint = {"stalled_episode": "事件已問不出新東西,考慮 close_episode",
                "long_episode": "事件偏長,考慮收割換場",
                "no_episode_nudge": "還沒開事件,請請員工講一件最近實際發生的事",
                "budget": "輪數接近上限,可準備收尾"}
        lines.append("訊號:" + "、".join(hint[k] for k in active))

    return "<議程>\n" + "\n".join(lines) + "\n</議程>"


def _episode_target_label(doc: dict, target: str) -> str:
    for _, t, tp in C.iter_tasks(doc):
        if tp == target:
            return _task_label(t)
    return "(某任務)"


# ---- 議程工具(T6;掛進顧問 chat_with_tools 同一迴圈;決策=tool call,§2.4 骨架②) ----

def agenda_tools(candidates: list[dict]) -> list[dict]:
    """本回合議程工具定義(target enum 動態=候選 ref+free;書記 schema 同款動態組)。
    描述 1–2 句(GPT-5.6/Anthropic Writing tools 紀律)。"""
    targets = [c["ref"] for c in candidates] + ["free"]
    return [
        {"type": "function", "function": {
            "name": "open_episode",
            "description": "開始深挖一個具體事件——請員工講一件最近實際發生的事。"
                           "target 從議程候選 ref 挑;員工自己起頭的話題用 free。",
            "parameters": {"type": "object", "properties": {
                "target": {"type": "string", "enum": targets,
                           "description": "候選事件 ref(如 c1)或 free(自發話題)"},
                "note": {"type": "string", "description": "free 時給這個事件起個短名"}},
                "required": ["target"]}}},
        {"type": "function", "function": {
            "name": "close_episode",
            "description": "這個事件已問透(細節、完成標準、驗收方式都有了)或員工明顯換"
                           "話題時呼叫;系統會把事件內容編碼進文件。",
            "parameters": {"type": "object", "properties": {
                "reason": {"type": "string",
                           "enum": ["saturated", "covered", "user_shifted"],
                           "description": "問不出新東西/已覆蓋足夠/員工換話題"}},
                "required": ["reason"]}}},
    ]


def resolve_target(candidates: list[dict], ref: str) -> str | None:
    """議程工具的 ref → task_path(free 原樣回;未知 ref 回 None)。"""
    if ref == "free":
        return "free"
    return next((c["id"] for c in candidates if c["ref"] == ref), None)
