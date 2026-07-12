"""T10(ADR 0030):收尾對帳——三訊號 suggest_finish、態度走 `_pending` 不直寫、
結構化總結回讀(lines=本場 pending;accepted 由 review-events 計)。"""
import pytest
from uuid import uuid4

from app.adapters.interview_repo import InterviewRepo
from app.adapters.persistence import DocRepo
from app.adapters.stubs import StubKnowledge, StubLlm
from app.api.routes.interview import finish_interview, interview_turn, start_interview
from app.interview import service as S
from app.models import JobProfile, User

TASK_PATH = "ocs_content.ocu_units.u1.tasks.t1"
FREQ = f"{TASK_PATH}.details.frequency"
K = StubKnowledge()
NOOP = {"records": []}
GOOD = {"records": [
    {"type": "set_slot", "path": FREQ, "value": "每雙週", "quote": "每兩週跑一次"}]}


def _doc():
    return {
        "ocs_profile": {"ocs_code": "X", "job_description": ""},
        "ocs_content": {"ocu_units": [{
            "_uid": "u1", "ocu_name": "測試",
            "tasks": [{"_tid": "t1",
                       "task_codes": [{"code": "T1.1", "name": "回歸測試"}],
                       "competency_blocks": [{"outputs": [{"code": "O1", "name": "報告"}]}]}],
        }]},
    }


async def _profile(db):
    u = User(email=f"{uuid4()}@x.com", name="n"); db.add(u); await db.flush()
    p = JobProfile(user_id=u.id, job_title="工程師"); db.add(p); await db.flush()
    await DocRepo(db).save(p.id, _doc())
    return p


# ---- 三訊號 → suggest_finish ----

@pytest.mark.asyncio
async def test_no_signal_no_suggest(db_session):
    p = await _profile(db_session)
    await start_interview(p.id, db=db_session)
    out = await interview_turn(p.id, {"text": "我們每兩週跑一次回歸"},
                               db=db_session, llm=StubLlm(select_result=GOOD), knowledge=K)
    assert out["suggest_finish"] is False


@pytest.mark.asyncio
async def test_fatigue_triggers_suggest(db_session):
    p = await _profile(db_session)
    await start_interview(p.id, db=db_session)
    await interview_turn(p.id, {"text": "我們每天要對三條產線做首件檢查,流程很長很細"},
                         db=db_session, llm=StubLlm(select_result=NOOP), knowledge=K)
    out = await interview_turn(p.id, {"text": "就這樣"},
                               db=db_session, llm=StubLlm(select_result=NOOP), knowledge=K)
    assert out["suggest_finish"] is True       # 疲勞訊號(敷衍短語)


@pytest.mark.asyncio
async def test_turn_budget_triggers_suggest(db_session, monkeypatch):
    monkeypatch.setattr(S, "TURN_BUDGET", 1)
    p = await _profile(db_session)
    await start_interview(p.id, db=db_session)
    out = await interview_turn(p.id, {"text": "我們每兩週跑一次回歸"},
                               db=db_session, llm=StubLlm(select_result=NOOP), knowledge=K)
    assert out["suggest_finish"] is True       # 輪數預算


# ---- run_finish:態度走 op→verify→_pending(不建議化、不直寫) ----

@pytest.mark.asyncio
async def test_finish_lands_attitudes_as_pending(db_session):
    p = await _profile(db_session)
    await start_interview(p.id, db=db_session)
    quote = "每批我一定重秤一次才放行,慢也認了"
    await interview_turn(p.id, {"text": quote},
                         db=db_session, llm=StubLlm(select_result=NOOP), knowledge=K)
    att_llm = StubLlm(select_result={"attitudes": [
        {"pool_id": "A01", "quote": quote, "rationale": "反覆重秤=謹慎"}]})
    out = await finish_interview(p.id, db=db_session, llm=att_llm, knowledge=K)
    assert out["phase"] == "review"
    latest = await DocRepo(db_session).latest(p.id)
    atts = latest["content"]["ocs_attitude"]["attitudes"]
    assert atts[-1]["code"] == "A01" and atts[-1]["name"] == "細心負責"
    mark = atts[-1]["_pending"]
    assert mark["op"] == "add" and mark["src"]["ref_urn"] == "A01"
    assert mark["src"]["quote"]["text"] == quote
    # 不建議化(建議層退場)
    repo = InterviewRepo(db_session)
    sess = await repo.latest_session(p.id)
    assert await repo.list_suggestions(sess.id) == []
    # 總結回讀含態度綠字
    assert out["summary"]["pending_count"] >= 1
    assert any("細心負責" in ln for ln in out["summary"]["lines"])


@pytest.mark.asyncio
async def test_finish_summary_lists_session_pendings(db_session):
    p = await _profile(db_session)
    await start_interview(p.id, db=db_session)
    await interview_turn(p.id, {"text": "每兩週跑一次"},
                         db=db_session, llm=StubLlm(select_result=GOOD), knowledge=K)
    out = await finish_interview(p.id, db=db_session, llm=None)
    assert any("頻率" in ln for ln in out["summary"]["lines"])
    assert out["summary"]["pending_count"] >= 1
    assert out["summary"]["accepted_count"] == 0
