"""回合服務(T8;spec §4 ①–⑦):載入 → 組脈絡 → 一呼 → 驗 → 執 → 寫回 → 回應。

寫回走 DocRepo.upsert_draft 帶雙 token(編輯器同一條 seam,ADR 0015/0023):
409 → 重讀最新重放一次;再衝突 → **建議化降級**(把本回合直改路由成建議,零覆蓋人)。
LLM 輸出結構由受限解碼保證;語義違規(pydantic 拒)→ 帶錯誤重問一次 → 仍壞 raise
LlmSchemaError(route 轉 502;session 不毀)。
"""
import logging
from dataclasses import dataclass, field
from uuid import UUID

from pydantic import ValidationError

from app.adapters.interview_repo import InterviewRepo
from app.adapters.llm_openrouter import LlmSchemaError
from app.adapters.persistence import DocConflictError, DocRepo
from app.interview import executor as ex
from app.interview.commands import TurnOutput, turn_output_schema
from app.interview.context import build_prompt

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


async def _llm_turn(llm, prompt: str, schema: dict) -> TurnOutput:
    data = await llm.select_schema(prompt, schema, schema_name="turn_output")
    try:
        return TurnOutput.model_validate(data)
    except ValidationError as e:
        logger.warning("turn output 語義違規,重問一次:%s", str(e)[:200])
        data2 = await llm.select_schema(
            prompt + f"\n(上次輸出不合法:{str(e)[:150]}——請修正後重出)", schema,
            schema_name="turn_output")
        try:
            return TurnOutput.model_validate(data2)
        except ValidationError as e2:
            raise LlmSchemaError(f"turn output invalid twice: {e2}") from e2


async def run_turn(profile_id: UUID, user_text: str, *, db, llm) -> TurnResult:
    repo = InterviewRepo(db)
    doc_repo = DocRepo(db)

    session = await repo.get_active(profile_id)
    if session is None:
        raise NoActiveInterview(str(profile_id))

    latest = await doc_repo.latest(profile_id)
    doc = (latest or {}).get("content") or {}
    prev_turns = await repo.list_turns(session.id)
    employee_texts = [t.text for t in prev_turns if t.role == "employee"] + [user_text]
    recent = [(t.role, t.text) for t in prev_turns] + [("employee", user_text)]
    emp_turn = await repo.append_turn(session.id, role="employee", text=user_text)

    prompt, choice_ids = build_prompt(
        doc=doc, phase=session.phase, focus=session.focus or {},
        counters=session.counters or {}, recent_turns=recent, user_text=user_text)
    turn = await _llm_turn(llm, prompt, turn_output_schema(choice_ids))

    res = ex.apply(turn, doc=doc, human_touched=list(session.human_touched or []),
                   counters=dict(session.counters or {}), focus=dict(session.focus or {}),
                   employee_texts=employee_texts)

    # 寫回文件(同一條 seam,雙 token;409 → 重讀重放一次;再衝突 → 建議化)
    doc_changed = False
    if res.new_doc is not None:
        try:
            await doc_repo.upsert_draft(
                profile_id, res.new_doc,
                expected_version=(latest or {}).get("version"),
                expected_revision=(latest or {}).get("revision"))
            doc_changed = True
        except DocConflictError:
            fresh = await doc_repo.latest(profile_id)
            fdoc = (fresh or {}).get("content") or {}
            res = ex.apply(turn, doc=fdoc, human_touched=list(session.human_touched or []),
                           counters=dict(session.counters or {}),
                           focus=dict(session.focus or {}), employee_texts=employee_texts)
            if res.new_doc is not None:
                try:
                    await doc_repo.upsert_draft(
                        profile_id, res.new_doc,
                        expected_version=fresh.get("version"),
                        expected_revision=fresh.get("revision"))
                    doc_changed = True
                except DocConflictError:
                    # 二度衝突:全部直改降級為建議(零覆蓋人;ADR 0025)
                    write_paths = [c.path for c in turn.commands
                                   if c.type in ("set_slot", "correct_slot")]
                    res = ex.apply(turn, doc=fdoc,
                                   human_touched=list(session.human_touched or []) + write_paths,
                                   counters=dict(session.counters or {}),
                                   focus=dict(session.focus or {}),
                                   employee_texts=employee_texts)
                    res.guard_log.append("conflict×2:直改全數建議化")

    # 持久化副作用(evidence/suggestions/counters/skips/advance)
    for ev in res.evidence:
        await repo.add_evidence(session.id, doc_path=ev["doc_path"], quote=ev["quote"],
                                turn_seq=emp_turn.seq, verified=ev["verified"])
    for sug in res.suggestions:
        await repo.add_suggestion(session.id, doc_path=sug["doc_path"],
                                  old_value=sug["old_value"], new_value=sug["new_value"],
                                  reason=sug["reason"], turn_seq=emp_turn.seq)

    counters = dict(session.counters or {})
    for k, v in res.counters_delta.items():
        counters[k] = v
    focus = dict(session.focus or {})
    if res.skipped_add:
        focus["skipped"] = list(dict.fromkeys((focus.get("skipped") or []) + res.skipped_add))
    phase = session.phase
    if res.advanced_to:
        if res.advanced_to == "review":
            phase = "review"
        else:
            focus["task_path"] = res.advanced_to
    await repo.update_session(session.id, counters=counters, focus=focus, phase=phase)

    # 顧問回合落逐字稿(say + 問題文字)
    consultant_text = "\n".join(x for x in [
        res.say, (res.question or {}).get("text"), (res.widget or {}).get("question"),
    ] if x)
    if consultant_text:
        await repo.append_turn(session.id, role="consultant", text=consultant_text,
                               commands=[c.model_dump() for c in turn.commands])

    pending = await repo.list_pending(session.id)
    return TurnResult(say=res.say, question=res.question, widget=res.widget,
                      doc_changed=doc_changed, pending_suggestions=len(pending),
                      phase=phase, focus=focus, guard_log=res.guard_log)
