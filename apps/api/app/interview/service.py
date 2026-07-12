"""回合服務 v2(ADR 0027 §5;spec §5):載入 → **書記 pass** → 帳本 → **顧問 chat_with_tools**
→ 保底 → 寫回。書記與顧問是兩次獨立呼叫(顧問說話零格式負擔、書記受限抽取,兩邊都安全)。

寫回走 DocRepo.upsert_draft 帶雙 token(ADR 0015/0023):409 → 重讀重放 apply_scribe 同
records(不重呼 LLM)一次;再衝突 → 直改降級(零覆蓋人)。書記失敗不擋顧問回覆
(fail-open 對話、fail-closed 寫入)。
"""
import logging
import time
from dataclasses import dataclass, field
from uuid import UUID

from app.adapters.interview_repo import InterviewRepo
from app.adapters.llm_openrouter import model_for_role
from app.adapters.persistence import DocConflictError, DocRepo
from app.interview import consultant as C
from app.interview import ledger as L
from app.interview.attitudes import attitudes_pass
from app.interview.backstop import SWEEP_EVERY, backstop_sweep
from app.interview.curation import curation_pass
from app.interview.scribe import (
    _doc_ocs_codes, build_pool_inputs, land_ops, scribe_pass, worth_scribing,
)
from app.models import JobProfile
from app.interview.slots import SLOT_DEFS
from app.interview.tools import CONSULTANT_TOOLS, dispatch_tool, document_view

logger = logging.getLogger("caliburn")


class NoActiveInterview(Exception):
    """無 active session(route 轉 409/404)。"""


# 收尾三訊號之三:輪數預算(§6.5 設計③;coverage 全綠/疲勞/預算,先到即建議收尾)
TURN_BUDGET = 40


@dataclass
class TurnResult:
    say: str = ""
    question: dict | None = None
    widget: dict | None = None
    doc_changed: bool = False
    pending_suggestions: int = 0
    phase: str = "deep"
    focus: dict = field(default_factory=dict)
    guard_log: list[str] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)   # {filled,required}(進度=覆蓋率)
    suggest_finish: bool = False                   # T10 三訊號任一成立(不強制)


def _pending_label(s) -> str:
    """待核准建議的短標籤(給顧問 context;員工可能問到卡片)。"""
    dp = s.doc_path or ""
    if dp.startswith("add_task:") or dp.startswith("add_duty:"):
        name = (s.new_value or {}).get("name") if isinstance(s.new_value, dict) else None
        kind = "新任務" if dp.startswith("add_task:") else "新職責"
        return f"{kind}「{name or dp.split(':', 1)[1]}」"
    leaf = dp.split(".")[-1]
    return f"更新 {SLOT_DEFS[leaf].label if leaf in SLOT_DEFS else leaf}"


async def build_task_pool(knowledge, doc: dict) -> list[dict]:
    """官方任務池(聯集;0028 D6 檢查表/裁剪的候選盤)。key=`ocs_code:task_code`。
    fail-open:knowledge 掛 → 空池 → curation/檢查表縫自然不開,對話照走。"""
    out: list[dict] = []
    seen: set[str] = set()
    for code in _doc_ocs_codes(doc):
        try:
            ot = await knowledge.occupation_tasks(code)
        except Exception as exc:  # noqa: BLE001
            logger.warning("build_task_pool:occupation_tasks(%s) 失敗:%s", code, str(exc)[:120])
            continue
        for u in (getattr(ot, "units", None) or []):
            for t in (u.tasks or []):
                key = f"{code}:{t.task_code}"
                if key in seen:
                    continue
                seen.add(key)
                out.append({"key": key, "name": t.task_name, "unit": u.ocu_name,
                            "ocs_code": code, "task_code": t.task_code})
    return out


async def _persist_scribe_doc(doc_repo, profile_id, latest, scribe_res, *,
                              turns, header_codes) -> tuple[bool, list[str]]:
    """書記 pending 寫回(雙 token;409→重讀後 land_ops 重放同 ops 一次——對 fresh doc
    **重新 verify**,防重複/漂移;再衝突→放棄,人的編輯優先 ADR 0025)。"""
    if scribe_res.new_doc is None:
        return False, []
    try:
        await doc_repo.upsert_draft(profile_id, scribe_res.new_doc,
                                    expected_version=(latest or {}).get("version"),
                                    expected_revision=(latest or {}).get("revision"))
        return True, []
    except DocConflictError:
        fresh = await doc_repo.latest(profile_id)
        fdoc = (fresh or {}).get("content") or {}
        new_doc, guard, _ = land_ops(scribe_res.ops, doc=fdoc, turns=turns,
                                     ref_codes=set(scribe_res.pool_items),
                                     header_codes=header_codes,
                                     pool_items=scribe_res.pool_items)
        if new_doc is None:
            return False, ["conflict:重放後無落地"] + guard
        try:
            await doc_repo.upsert_draft(profile_id, new_doc,
                                        expected_version=fresh.get("version"),
                                        expected_revision=fresh.get("revision"))
            return True, ["conflict:重放成功"]
        except DocConflictError:
            return False, ["conflict×2:放棄落地(人的編輯優先)"]


async def run_turn(profile_id: UUID, user_text: str, *, db, llm, knowledge) -> TurnResult:
    """v2 一回合(ADR 0027 §5)。knowledge=KnowledgePort(書記建池 + 顧問工具)。"""
    repo = InterviewRepo(db)
    doc_repo = DocRepo(db)

    session = await repo.get_active(profile_id)
    if session is None:
        raise NoActiveInterview(str(profile_id))

    latest = await doc_repo.latest(profile_id)
    doc = (latest or {}).get("content") or {}
    prev_turns = await repo.list_turns(session.id)
    employee_texts = [t.text for t in prev_turns if t.role == "employee"] + [user_text]
    recent = [(t.role, t.text) for t in prev_turns]
    human_touched = list(session.human_touched or [])
    emp_turn = await repo.append_turn(session.id, role="employee", text=user_text)

    # v3 回合序(ADR 0030 T5):顧問先說話 → 確定性喚醒閘 → 書記 op→verify→_pending
    # → backstop sweep → 帳本更新。顧問吃**回合前**的文件/帳本(綠字自己會浮現,不用等)。
    turns_map = {t.seq: t.text for t in prev_turns if t.role == "employee"}
    turns_map[emp_turn.seq] = user_text
    profile = await db.get(JobProfile, profile_id)
    header_codes = set(getattr(profile, "selected_ocs_codes", None) or [])
    work_doc = doc

    # ①½ 官方任務池(0028 D6:檢查表/裁剪候選盤;fail-open,掛了縫不開)
    pool_tasks = await build_task_pool(knowledge, work_doc)

    # ② 帳本(回合前視角):上一輪 gap 是否進帳的評定移到書記跑完後
    state = dict(session.ledger_state or {})
    state["last_gap"] = L.next_gap(work_doc, state, {}, pool_tasks)

    # ②½ 裁剪 pass(0028 D1/D4):curation 縫 → AI 對 unasked 官方任務預勾/排除;
    #    precheck → widget 指令(picker 人確認才落文件);declined → ledger_state(不再反問)
    widget: dict | None = None
    curation_guard: list[str] = []
    if state["last_gap"] == L.CURATION_TASKS and pool_tasks:
        unasked = L.checklist(work_doc, state, pool_tasks)["unasked"]
        if unasked:
            t_cur = time.perf_counter()
            cur = await curation_pass(llm, pool_tasks=unasked, employee_texts=employee_texts)
            cur_ms = int((time.perf_counter() - t_cur) * 1000)
            curation_guard = list(cur.guard_log)
            if cur.declined:
                state["declined"] = list(dict.fromkeys(
                    (state.get("declined") or []) + [d["key"] for d in cur.declined]))
            if cur.precheck:
                # D9:widget 只帶 AI 疊加層(precheck);清單本身=前端知識包(ADR 0021)
                widget = {"kind": "open_picker", "picker": "task",
                          "precheck": cur.precheck}
            await repo.add_llm_call(session.id, turn_seq=emp_turn.seq, role="select",
                                    model=model_for_role("select"), duration_ms=cur_ms,
                                    guard_verdicts=curation_guard[:30])

    # ③ 顧問 chat_with_tools(說話 + READ 工具;無寫入權)——v3:顧問先於書記
    pending_labels = [_pending_label(s) for s in await repo.list_pending(session.id)]
    rejected_labels = [e.doc_path.split(".")[-1] if "." in e.doc_path else e.doc_path
                       for e in await repo.list_review_events(session.id,
                                                              decision="rejected")][-10:]
    messages = C.build_consultant_messages(
        doc=work_doc, ledger_state=state, recent_turns=recent,
        pending=pending_labels, employee_text=user_text, pool_tasks=pool_tasks,
        rejected=rejected_labels)
    # write-in 抓漏只吐一次(0028 D6):摘要已含探測句 → 消費 flag
    if (pool_tasks and not state.get("writein_asked")
            and not L.checklist(work_doc, state, pool_tasks)["unasked"]):
        state["writein_asked"] = True
    # dispatch 包一層截職類搜尋命中(D8 P2)+ read_document 四態視圖(doc 在此層)
    occ_searches: list[dict] = []

    async def dispatch(name: str, arguments: dict):
        if name == "read_document":
            return document_view(work_doc)
        res = await dispatch_tool(name, arguments, knowledge=knowledge)
        if name == "knowledge_search_occupations" and isinstance(res, dict):
            occ_searches.append({"query": (arguments or {}).get("query") or "",
                                 "hits": res.get("occupations") or []})
        return res

    t_chat = time.perf_counter()
    chat = await llm.chat_with_tools(role="interview", messages=messages,
                                     tools=CONSULTANT_TOOLS, dispatch=dispatch)
    chat_ms = int((time.perf_counter() - t_chat) * 1000)

    # ③¾ 書記(v3:顧問後、確定性喚醒閘;fail-open 對話、fail-closed 寫入)
    scribe_ms = 0
    doc_changed, extra_guard = False, []
    from app.interview.scribe import ScribeResult as _SR
    scribe_res = _SR()
    if worth_scribing(user_text):
        t_scribe = time.perf_counter()
        scribe_res = await scribe_pass(llm, knowledge, doc=doc, turns=turns_map,
                                       turn_id=emp_turn.seq, header_codes=header_codes)
        scribe_ms = int((time.perf_counter() - t_scribe) * 1000)
        doc_changed, extra_guard = await _persist_scribe_doc(
            doc_repo, profile_id, latest, scribe_res,
            turns=turns_map, header_codes=header_codes)
    else:
        extra_guard = ["scribe:skip(meta/寒暄回合,喚醒閘)"]

    # ③⅞ backstop sweep(每 N 員工回合;確定性撿漏 → held 待問;§6.4 禁 LLM)
    last_swept = int(state.get("backstop_last_seq") or 0)
    if emp_turn.seq - last_swept >= SWEEP_EVERY:
        texts_since = [t for s_, t in sorted(turns_map.items()) if s_ > last_swept]
        unasked_now = (L.checklist(work_doc, state, pool_tasks)["unasked"]
                       if pool_tasks else [])
        for q in backstop_sweep(doc=work_doc, texts_since=texts_since,
                                unasked_tasks=unasked_now,
                                pool_items=scribe_res.pool_items):
            state = L.push_held(state, q, emp_turn.seq)
        state["backstop_last_seq"] = emp_turn.seq

    # ④′ 帳本收帳:上一輪 gap 進帳評定(飽和偵測)+ 疲勞訊號
    state = L.note_attempt(state, state.get("last_gap"), scribe_res.progressed)
    state["fatigued"] = L.is_fatigued([t for _, t in sorted(turns_map.items())])

    # ④″ 收尾三訊號(T10;任一成立→建議收尾,不強制):coverage 全綠/疲勞/輪數預算
    ok_finish, _ = L.can_finish(work_doc, state, {})
    suggest_finish = bool(ok_finish or state.get("fatigued")
                          or len(employee_texts) >= TURN_BUDGET)

    # ③½ occupation widget(0028 D1 + D8 P2 統一):顧問本回合搜過職類且 **top-1 不在
    #    現有 codes** → 開 picker 預填該搜尋詞。涵蓋開場(codes 空)與中途加選
    #    (全端聊到後端:top-1=互補職類 ∉ codes → 彈;查參考 top-1=已選 → 不彈不騷擾)。
    if widget is None and occ_searches:
        codes = set(_doc_ocs_codes(work_doc))
        for s_ in occ_searches:
            top = (s_["hits"] or [{}])[0]
            if top.get("ocs_code") and top["ocs_code"] not in codes and s_["query"]:
                widget = {"kind": "open_picker", "picker": "occupation",
                          "query": str(s_["query"])[:120]}
                break

    # ④ 保底:顧問恆有可見回覆 + 往前的問題(靜默回合=實戰死穴)
    say = (chat.text or "").strip()
    if not say:
        nxt = state.get("last_gap")
        say = (f"我們接著聊「{C.gap_label(work_doc, nxt)}」吧?" if nxt
               else "謝謝你,我這邊先整理一下——還有想補充的嗎?")

    await repo.update_session(session.id, ledger_state=state)
    await repo.append_turn(session.id, role="consultant", text=say,
                           commands=[{"tool_trace": chat.tool_trace, "stopped": chat.stopped}])

    # 稽核落庫(T13;每回合書記+顧問各一列;§13 收編5 多租戶 observability)
    await repo.add_llm_call(session.id, turn_seq=emp_turn.seq, role="select",
                            model=model_for_role("select"), duration_ms=scribe_ms,
                            guard_verdicts=list(scribe_res.guard_log)[:30])
    await repo.add_llm_call(session.id, turn_seq=emp_turn.seq, role="interview",
                            model=model_for_role("interview"), duration_ms=chat_ms,
                            tool_calls=chat.tool_trace)

    pending = await repo.list_pending(session.id)
    guard = list(scribe_res.guard_log) + extra_guard + curation_guard
    if scribe_res.records_failed:
        guard.append("scribe:抽取重試仍敗(交 backstop)")
    return TurnResult(say=say, question=None, widget=widget, doc_changed=doc_changed,
                      pending_suggestions=len(pending),
                      phase=L.derive_phase(work_doc, state),
                      focus=dict(session.focus or {}), guard_log=guard,
                      coverage=L.coverage(work_doc, state),
                      suggest_finish=suggest_finish)


async def run_curation(profile_id: UUID, *, db, llm, knowledge) -> dict:
    """隨叫裁剪(D8 P1a;D9):選完職類**立刻**鋪任務盤,零打字。
    只回 **AI 疊加層** precheck(依至今發言預勾+引文)——清單本身由前端知識包組
    (ADR 0021:pack=所有選單的資料源;已加入/全量照列都在前端)。
    declined 落 ledger_state(顧問不再反問;同 turn 路徑);
    llm 缺/敗或無發言 → precheck 空(fail-open:前端盤照開)。"""
    repo = InterviewRepo(db)
    session = await repo.get_active(profile_id)
    if session is None:
        raise NoActiveInterview(str(profile_id))
    doc = ((await DocRepo(db).latest(profile_id)) or {}).get("content") or {}
    pool_tasks = await build_task_pool(knowledge, doc)
    state = dict(session.ledger_state or {})
    unasked = L.checklist(doc, state, pool_tasks)["unasked"]

    precheck: list[dict] = []
    if unasked and llm is not None:
        turns = await repo.list_turns(session.id)
        emp = [t.text for t in turns if t.role == "employee"]
        if emp:
            cur = await curation_pass(llm, pool_tasks=unasked, employee_texts=emp)
            precheck = cur.precheck
            if cur.declined:
                state["declined"] = list(dict.fromkeys(
                    (state.get("declined") or []) + [d["key"] for d in cur.declined]))
                await repo.update_session(session.id, ledger_state=state)

    return {"precheck": precheck}


def _finish_summary(doc: dict, accepted_paths: list[str]) -> dict:
    """結構化總結回讀(T10;§6.5 設計③):本場寫入清單=文件 `_pending`(綠字未審)
    ∪已 accept 事件;按任務條列,指著表格對帳。純函式,零 LLM。"""
    view = document_view(doc)
    lines: list[str] = []
    n_pending = 0
    kind_label = {"outputs": "產出", "indicators": "指標", "knowledge": "知識",
                  "skills": "技能"}
    for row in view["tasks"]:
        for p in (row.get("pending_items") or []):
            n_pending += 1
            k = p["kind"]
            label = kind_label.get(k, SLOT_DEFS[k.split(".")[-1]].label
                                   if k.startswith("details.")
                                   and k.split(".")[-1] in SLOT_DEFS else k)
            lines.append(f"「{row['task']}」{label}:{p.get('value') or ''}(待審)")
        if row.get("status") != "confirmed":
            n_pending += 1
            lines.append(f"任務「{row['task']}」(待審)")
    for a in view["attitudes"]:
        if a.get("status") != "confirmed":
            n_pending += 1
            lines.append(f"態度「{a.get('value') or ''}」(待審)")
    for slot, info in (view.get("header_pending") or {}).items():
        n_pending += 1
        lines.append(f"表頭 {slot}:{info.get('proposed') or ''}(待審)")
    return {"lines": lines, "pending_count": n_pending,
            "accepted_count": len(accepted_paths)}


def _quote_turn(quote: str, turns_map: dict[int, str]) -> int:
    """quote 所在回合(verify 同款正規化;attitudes_pass 已驗過,必有解;保底 0)。"""
    from app.interview.verify import normalize
    q = normalize(quote)
    for seq, text in sorted(turns_map.items()):
        if q and q in normalize(text):
            return seq
    return 0


async def run_finish(profile_id: UUID, *, db, llm, knowledge) -> dict:
    """收尾對帳(T10;ADR 0030):態度收尾 pass 走 **op→verify→`_pending`**(態度綠標,
    與書記同軌;建議層退場)→ 結構化總結回讀 → phase=review。
    fail-open:llm 缺仍可收尾(不編態度);knowledge 掛 → 略過態度。"""
    repo = InterviewRepo(db)
    doc_repo = DocRepo(db)
    session = await repo.get_active(profile_id)
    if session is None:
        raise NoActiveInterview(str(profile_id))
    latest = await doc_repo.latest(profile_id)
    doc = (latest or {}).get("content") or {}
    state = session.ledger_state or {}
    _, blockers = L.can_finish(doc, state, {})
    guard: list[str] = []

    if llm is not None:
        turns = await repo.list_turns(session.id)
        emp_rows = [(t.seq, t.text) for t in turns if t.role == "employee"]
        emp = [t for _, t in emp_rows]
        turns_map = dict(emp_rows)
        # 態度收尾整體編碼(0028 D3;一呼、跨故事主題編碼)
        try:
            pools, pool_items = await build_pool_inputs(knowledge, doc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("run_finish:態度池組建失敗(略過):%s", str(exc)[:120])
            pools, pool_items = {}, {}
        existing = [a.get("code") for a in
                    ((doc.get("ocs_attitude") or {}).get("attitudes") or []) if a.get("code")]
        att = await attitudes_pass(llm, pool=pools.get("attitudes") or [],
                                   pool_items=pool_items, employee_texts=emp,
                                   existing=existing)
        guard.extend(att.guard_log)
        if att.proposals:
            import copy
            base = copy.deepcopy(doc)
            base.setdefault("ocs_attitude", {}).setdefault("attitudes", [])
            ops = [{"target_path": "ocs_attitude.attitudes", "op": "add",
                    "value": p["name"],
                    "src": {"ref_urn": p["pool_id"],
                            "quote": {"turn_id": _quote_turn(p["quote"], turns_map),
                                      "text": p["quote"]}}}
                   for p in att.proposals]
            new_doc, land_guard, landed = land_ops(
                ops, doc=base, turns=turns_map, ref_codes=set(pool_items),
                header_codes=set(), pool_items=pool_items)
            guard.extend(land_guard)
            if new_doc is not None and landed:
                try:
                    await doc_repo.upsert_draft(
                        profile_id, new_doc,
                        expected_version=(latest or {}).get("version"),
                        expected_revision=(latest or {}).get("revision"))
                    doc = new_doc
                except DocConflictError:
                    guard.append("conflict:態度落地放棄(人的編輯優先)")

    accepted = [e.doc_path for e in
                await repo.list_review_events(session.id, decision="accepted")]
    summary = _finish_summary(doc, accepted)
    await repo.update_session(session.id, phase="review")
    pending = await repo.list_pending(session.id)
    return {"phase": "review", "blockers": len(blockers),
            "pending_suggestions": len(pending),
            "summary": summary, "guard_log": guard[:30]}
