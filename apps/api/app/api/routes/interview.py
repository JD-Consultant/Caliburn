"""訪談引擎 REST 端點(T9;spec §3;AIP-136 `:verb`,ADR 0019)。

- `interview:start` 冪等(有 active 回同一個);文件無任務 → 409(先用編輯器選職類/任務
  ——v1 盤點段=既有 widget,引擎軌道從 deep 起跑,spec §0)。
- `interview:turn` 一回合;LLM 未配置 → 503(訪談本體就是 LLM,不同於 /ai/* 的降級)。
- `interview:review` **只轉建議狀態**——套用由前端以既有寫入路徑執行
  (ai-suggestions 不變量 1「提議由前端套用後走 PATCH」;add 類的 renumber 是前端
  ocsDoc 職權;spec §3 後記)。
"""
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.interview_repo import ActiveInterviewExists, InterviewRepo
from app.adapters.llm_openrouter import LlmSchemaError
from app.adapters.persistence import DocRepo
from app.api.deps import get_knowledge
from app.api.routes.ai import get_llm
from app.api.routes.documents import _require_profile
from app.core.domain.ocs_doc import count_pending
from app.core.ports import KnowledgePort, LlmPort
from app.database import get_db
from app.interview import agenda as AG
from app.interview import coverage as CO
from app.interview.diff import STABLE_ID_KEYS
from app.interview.service import NoActiveInterview, run_finish, run_turn
from app.observability import record_review_events

router = APIRouter(prefix="/job-profiles", tags=["interview"])

GREETING = ("你好!我是你的職務說明書顧問。我們會一個任務一個任務聊,"
            "把你實際的做法補進文件——想到什麼說什麼就好,我會幫你整理。")


def _seg_of(item: dict, idx: int) -> str:
    for k in STABLE_ID_KEYS:
        if item.get(k):
            return str(item[k])
    return str(idx)


def _task_paths(doc: dict) -> list[str]:
    out = []
    for ui, unit in enumerate((doc.get("ocs_content") or {}).get("ocu_units") or []):
        useg = _seg_of(unit, ui)
        for ti, task in enumerate(unit.get("tasks") or []):
            out.append(f"ocs_content.ocu_units.{useg}.tasks.{_seg_of(task, ti)}")
    return out


def _progress(doc: dict, session, phase: str) -> dict:
    # v2:進度=覆蓋率(帳本 filled/required;spec §11.1)
    state = getattr(session, "ledger_state", None) or {}
    return {"phase": phase, "coverage": CO.coverage(doc, state)}


def _session_out(s) -> dict:
    return {"session_id": str(s.id), "status": s.status, "phase": s.phase,
            "focus": s.focus, "counters": s.counters}


@router.post("/{profile_id}/interview:start")
async def start_interview(profile_id: UUID, db: AsyncSession = Depends(get_db)):
    await _require_profile(profile_id, db)
    latest = await DocRepo(db).latest(profile_id)
    doc = (latest or {}).get("content") or {}
    paths = _task_paths(doc)
    repo = InterviewRepo(db)
    session = await repo.get_active(profile_id)
    if session is None:
        try:
            session = await repo.create(profile_id)
        except ActiveInterviewExists as e:   # 同毫秒競態(partial unique 兜底)
            session = await repo.get(e.session_id)
    # v2(§16.12):空白 doc 也可起跑——有任務就 deep+焦點,無任務走 survey 讓顧問開場引導
    # 選職類(手動 picker/知識包同步平行保留 ADR 0021);拿掉舊 409 no_tasks 硬阻。
    if paths and not (session.focus or {}).get("task_path"):
        session = await repo.update_session(
            session.id, phase="deep",
            focus={**(session.focus or {}), "task_path": paths[0]})
    elif not paths and session.phase == "survey":
        session = await repo.update_session(session.id, phase="survey")
    greeting = GREETING if paths else (
        "你好!我是你的職務說明書顧問。我們先聊聊你平常做什麼工作,我幫你找到對應的官方"
        "職類、把細節補齊——想到什麼說什麼就好。")
    return {**_session_out(session), "greeting": greeting,
            "progress": _progress(doc, session, session.phase)}


@router.post("/{profile_id}/interview:turn")
async def interview_turn(
    profile_id: UUID,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    llm: LlmPort | None = Depends(get_llm),
    knowledge: KnowledgePort = Depends(get_knowledge),
):
    await _require_profile(profile_id, db)
    if llm is None:
        raise HTTPException(status_code=503, detail={
            "code": "llm_unavailable", "message": "LLM 未配置,訪談暫不可用。"})
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail={"code": "empty_text"})
    try:
        out = await run_turn(profile_id, text, db=db, llm=llm, knowledge=knowledge)
    except NoActiveInterview:
        raise HTTPException(status_code=409, detail={"code": "no_active_interview"})
    except LlmSchemaError as e:
        # 受限解碼失效(0024 保險絲):顯式 502,session 完好可重試
        raise HTTPException(status_code=502, detail={
            "code": "llm_schema_error", "message": str(e)[:200]})
    # 進度=覆蓋率(spec §11.1;帳本 filled/required),取代 v1 task_index/total
    return {"say": out.say, "question": out.question, "widget": out.widget,
            "doc_changed": out.doc_changed,
            "progress": {"phase": out.phase, "coverage": out.coverage},
            "suggest_finish": out.suggest_finish}   # T10 三訊號(側欄顯示收尾鈕,不強制)


# interview:curation(隨叫裁剪,盤預勾疊加層)已退役(ADR 0032):盤=乾淨自取;
# quote-backed 判斷改在 run_turn 裁剪縫直落 `_pending` 綠字(web 從未接上此端點)。


@router.post("/{profile_id}/interview:finish")
async def finish_interview(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    llm: LlmPort | None = Depends(get_llm),
    knowledge: KnowledgePort = Depends(get_knowledge),
):
    """收尾對帳(T10):態度收尾 pass 走 op→verify→`_pending` + 結構化總結回讀
    → 轉 review。編排在 service.run_finish(use-case 層);fail-open。"""
    await _require_profile(profile_id, db)
    try:
        return await run_finish(profile_id, db=db, llm=llm, knowledge=knowledge)
    except NoActiveInterview:
        raise HTTPException(status_code=409, detail={"code": "no_active_interview"})


def _agenda(doc: dict, state: dict) -> list[dict]:
    """議程三態清單(0033 T8c;由 doc/agenda 狀態推導不落庫):
    completed(缺口清空)/in_progress(=當前進行中事件的目標任務)/pending;boundary=劃線不談。
    in_progress 由 `next_gap` 梯子改為**當前 episode target**(v4 事件驅動;梯子已退役)。"""
    ep = AG.episode_state(state)
    target = ep["target"] if ep and ep.get("target") != "free" else None
    rows: list[dict] = []
    for _, t, tp in CO.iter_tasks(doc):
        codes = t.get("task_codes") or []
        name = (codes[0].get("name") if codes else "") or "(未命名任務)"
        if AG.in_boundary(state, tp):
            st = "boundary"
        elif not CO.task_missing(t, tp, state, set()):
            st = "completed"
        elif target == tp:
            st = "in_progress"
        else:
            st = "pending"
        rows.append({"key": tp, "label": name, "state": st})
    att = ("boundary" if AG.in_boundary(state, "ocs_attitude")
           else "completed" if not CO.attitudes_missing(doc) else "pending")
    rows.append({"key": "ocs_attitude", "label": "工作態度", "state": att})
    return rows


@router.get("/{profile_id}/interview")
async def get_interview(profile_id: UUID, db: AsyncSession = Depends(get_db)):
    """session 全貌:續談入口 + 顧問稽核視圖(逐字稿)+議程三態+待審計數。
    v3(T12):evidence/suggestions 層退場——溯源住 `_pending.src`、審閱住 review-events。"""
    await _require_profile(profile_id, db)
    repo = InterviewRepo(db)
    session = await repo.latest_session(profile_id)
    if session is None:
        raise HTTPException(status_code=404, detail={"code": "no_interview"})
    turns = await repo.list_turns(session.id)
    draft = await DocRepo(db).latest(profile_id)
    doc = (draft or {}).get("content") or {}
    return {
        **_session_out(session),
        "pending_count": count_pending(draft or {}),  # _pending 待審筆數(ADR 0030)
        "agenda": _agenda(doc, dict(session.ledger_state or {})),
        "turns": [{"seq": t.seq, "role": t.role, "text": t.text} for t in turns],
    }


# interview:review(建議層批審)已退場(T12):✓/✗ 走前端 acceptPending/rejectPending
# + PATCH + interview:review-events(無聲記帳)。

# occupation_dismissed:他關掉職類建議卡(0031)/task_board_dismissed:他婉拒任務盤
# 邀請卡「用聊的就好」(0032)——都只記帳;下回合顧問知情換話術
_REVIEW_DECISIONS = {"accepted", "rejected", "batch_rejected", "occupation_dismissed",
                     "task_board_dismissed"}


@router.post("/{profile_id}/interview:review-events")
async def add_review_events(
    profile_id: UUID,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """審閱事件無聲記帳(ADR 0030 §6.3):✓/✗/批量拒絕只記不觸發 AI。

    文件變換(去標/還原/renumber/PATCH)由前端執行(0025 不變量);
    本端點僅落 `interview_review_events`,供 ledger 下回合讀「被拒清單」。
    body = {"events": [{"doc_path", "decision", "op_meta"?}, ...]}
    """
    await _require_profile(profile_id, db)
    repo = InterviewRepo(db)
    session = await repo.latest_session(profile_id)
    if session is None:
        raise HTTPException(status_code=404, detail={"code": "no_interview"})
    events = body.get("events") or []
    if not events:
        raise HTTPException(status_code=422, detail={"code": "empty_events"})
    for e in events:
        if not e.get("doc_path") or e.get("decision") not in _REVIEW_DECISIONS:
            raise HTTPException(status_code=422, detail={"code": "bad_event", "event": e})
    n = await repo.add_review_events(session.id, events)
    record_review_events(events)
    return {"recorded": n}
