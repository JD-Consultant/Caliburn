"""回合服務 v2(ADR 0027 §5;spec §5):載入 → **書記 pass** → 帳本 → **顧問 chat_with_tools**
→ 保底 → 寫回。書記與顧問是兩次獨立呼叫(顧問說話零格式負擔、書記受限抽取,兩邊都安全)。

寫回走 DocRepo.upsert_draft 帶雙 token(ADR 0015/0023):409 → 重讀重放 apply_scribe 同
records(不重呼 LLM)一次;再衝突 → 直改降級(零覆蓋人)。書記失敗不擋顧問回覆
(fail-open 對話、fail-closed 寫入)。
"""
import logging
import time
from dataclasses import dataclass, field
from functools import partial
from uuid import UUID

from app.adapters.interview_repo import InterviewRepo
from app.adapters.llm_openrouter import model_for_role
from app.adapters.persistence import DocConflictError, DocRepo
from app.interview import consultant as C
from app.interview import ledger as L
from app.interview.scribe import apply_scribe, scribe_pass
from app.interview.slots import SLOT_DEFS
from app.interview.tools import CONSULTANT_TOOLS, dispatch_tool

logger = logging.getLogger("caliburn")


class NoActiveInterview(Exception):
    """無 active session(route 轉 409/404)。"""


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


def _pending_label(s) -> str:
    """待核准建議的短標籤(給顧問 context;員工可能問到卡片)。"""
    dp = s.doc_path or ""
    if dp.startswith("add_task:") or dp.startswith("add_duty:"):
        name = (s.new_value or {}).get("name") if isinstance(s.new_value, dict) else None
        kind = "新任務" if dp.startswith("add_task:") else "新職責"
        return f"{kind}「{name or dp.split(':', 1)[1]}」"
    leaf = dp.split(".")[-1]
    return f"更新 {SLOT_DEFS[leaf].label if leaf in SLOT_DEFS else leaf}"


async def _persist_scribe_doc(doc_repo, profile_id, latest, scribe_res, *,
                              employee_texts, human_touched) -> tuple[bool, list[str]]:
    """書記直改寫回(雙 token;409→重讀重放同 records 一次;再衝突→放棄直改,保留
    evidence/suggestions,人的編輯優先 ADR 0025)。回 (doc_changed, extra_guard)。"""
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
        replay = apply_scribe(scribe_res.records, doc=fdoc,
                              pool_items=scribe_res.pool_items, pools=scribe_res.pools,
                              employee_texts=employee_texts, human_touched=human_touched)
        if replay.new_doc is None:
            return False, ["conflict:重放後無直改"]
        try:
            await doc_repo.upsert_draft(profile_id, replay.new_doc,
                                        expected_version=fresh.get("version"),
                                        expected_revision=fresh.get("revision"))
            return True, ["conflict:重放成功"]
        except DocConflictError:
            return False, ["conflict×2:放棄直改(人的編輯優先)"]


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

    # ① 書記 pass(便宜、序列先行;失敗不擋顧問——fail-open 對話、fail-closed 寫入)
    t_scribe = time.perf_counter()
    scribe_res = await scribe_pass(llm, knowledge, doc=doc, employee_texts=employee_texts,
                                   human_touched=human_touched)
    scribe_ms = int((time.perf_counter() - t_scribe) * 1000)
    doc_changed, extra_guard = await _persist_scribe_doc(
        doc_repo, profile_id, latest, scribe_res,
        employee_texts=employee_texts, human_touched=human_touched)
    for ev in scribe_res.evidence:
        await repo.add_evidence(session.id, doc_path=ev["doc_path"], quote=ev["quote"],
                                turn_seq=emp_turn.seq, verified=ev["verified"],
                                review=ev.get("review", "auto"))
    for sug in scribe_res.suggestions:
        await repo.add_suggestion(session.id, doc_path=sug["doc_path"],
                                  old_value=sug["old_value"], new_value=sug["new_value"],
                                  reason=sug["reason"], turn_seq=emp_turn.seq)

    work_doc = (await doc_repo.latest(profile_id) or {}).get("content") or doc

    # ② 帳本:先評上一輪 gap 是否進帳(飽和偵測),再算本輪 next_gap(給顧問當提示)
    state = dict(session.ledger_state or {})
    state = L.note_attempt(state, state.get("last_gap"), scribe_res.progressed)
    state["last_gap"] = L.next_gap(work_doc, state, {})

    # ③ 顧問 chat_with_tools(說話 + READ 工具;無寫入權)
    pending_labels = [_pending_label(s) for s in await repo.list_pending(session.id)]
    messages = C.build_consultant_messages(
        doc=work_doc, ledger_state=state, recent_turns=recent,
        pending=pending_labels, employee_text=user_text)
    dispatch = partial(dispatch_tool, knowledge=knowledge)
    t_chat = time.perf_counter()
    chat = await llm.chat_with_tools(role="interview", messages=messages,
                                     tools=CONSULTANT_TOOLS, dispatch=dispatch)
    chat_ms = int((time.perf_counter() - t_chat) * 1000)

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
    guard = list(scribe_res.guard_log) + extra_guard
    if scribe_res.records_failed:
        guard.append("scribe:抽取重試仍敗(交 backstop)")
    return TurnResult(say=say, question=None, widget=None, doc_changed=doc_changed,
                      pending_suggestions=len(pending), phase=session.phase,
                      focus=dict(session.focus or {}), guard_log=guard,
                      coverage=L.coverage(work_doc, state))
