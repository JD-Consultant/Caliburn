"""T9:interview 四端點(直呼 route 函式 + 真 DB + StubLlm)。"""
import pytest
from uuid import uuid4

from fastapi import HTTPException

from app.adapters.persistence import DocRepo
from app.adapters.stubs import StubKnowledge, StubLlm
from app.api.routes.interview import (
    finish_interview, get_interview, interview_turn, start_interview,
)
from app.models import JobProfile, User

TASK_PATH = "ocs_content.ocu_units.u1.tasks.t1"
FREQ = f"{TASK_PATH}.details.frequency"


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


async def _profile(db, *, with_doc=True):
    u = User(email=f"{uuid4()}@x.com", name="n"); db.add(u); await db.flush()
    p = JobProfile(user_id=u.id, job_title="工程師"); db.add(p); await db.flush()
    if with_doc:
        await DocRepo(db).save(p.id, _doc())
    return p


# v2:書記 records(非 v1 turn commands)
GOOD = {"records": [
    {"type": "set_slot", "path": FREQ, "value": "每雙週", "quote": "每兩週跑一次"}]}
K = StubKnowledge()


@pytest.mark.asyncio
async def test_start_allows_blank_doc(db_session):
    # v2(§16.12):空白 doc 也可起跑(survey 階段,顧問開場引導選職類)
    p = await _profile(db_session, with_doc=False)
    out = await start_interview(p.id, db=db_session)
    assert out["status"] == "active" and out["phase"] == "survey"
    assert out["progress"]["coverage"]["required"] >= 1
    assert "職類" in out["greeting"]


@pytest.mark.asyncio
async def test_blank_doc_turn_does_not_crash(db_session):
    # 空白 doc 一回合:無任務→書記 no-op、顧問照樣開場引導(不炸)
    p = await _profile(db_session, with_doc=False)
    await start_interview(p.id, db=db_session)
    out = await interview_turn(
        p.id, {"text": "我幫公司修設備"}, db=db_session,
        llm=StubLlm(select_result={"records": []}, chat_text="好,你主要修哪類設備?"),
        knowledge=K)
    assert out["say"] == "好,你主要修哪類設備?" and out["doc_changed"] is False


@pytest.mark.asyncio
async def test_start_idempotent_and_inits_focus(db_session):
    p = await _profile(db_session)
    out1 = await start_interview(p.id, db=db_session)
    out2 = await start_interview(p.id, db=db_session)
    assert out1["session_id"] == out2["session_id"]
    assert out1["focus"]["task_path"] == TASK_PATH
    assert out1["progress"]["phase"] == "deep"
    assert out1["progress"]["coverage"]["required"] > 0        # v2 覆蓋率進度
    assert "顧問" in out1["greeting"]


@pytest.mark.asyncio
async def test_turn_full_loop_and_errors(db_session):
    p = await _profile(db_session)
    # 未 start → 409
    with pytest.raises(HTTPException) as e:
        await interview_turn(p.id, {"text": "hi"}, db=db_session,
                             llm=StubLlm(select_result=GOOD), knowledge=K)
    assert e.value.status_code == 409
    # llm 未配置 → 503
    await start_interview(p.id, db=db_session)
    with pytest.raises(HTTPException) as e2:
        await interview_turn(p.id, {"text": "hi"}, db=db_session, llm=None, knowledge=K)
    assert e2.value.status_code == 503
    # happy path:書記寫槽 + 顧問回覆 + 覆蓋率進度
    out = await interview_turn(p.id, {"text": "我們每兩週跑一次回歸"},
                               db=db_session, llm=StubLlm(select_result=GOOD), knowledge=K)
    assert out["doc_changed"] is True and out["say"].strip()
    assert out["progress"]["coverage"]["required"] > 0


@pytest.mark.asyncio
async def test_get_interview_full_view(db_session):
    p = await _profile(db_session)
    await start_interview(p.id, db=db_session)
    await interview_turn(p.id, {"text": "我們每兩週跑一次回歸"},
                         db=db_session, llm=StubLlm(select_result=GOOD), knowledge=K)
    view = await get_interview(p.id, db=db_session)
    assert [t["role"] for t in view["turns"]] == ["employee", "consultant"]
    assert view["pending_count"] == 1                 # v3:寫入=文件內 _pending(evidence 退場)
    assert "evidence" not in view and "suggestions" not in view   # T12:兩層退場
    assert view["status"] == "active"
    # T9 議程三態:任務缺口未清=in_progress(next_gap 落此)或 pending;末列=態度
    agenda = view["agenda"]
    assert agenda[0]["label"] == "回歸測試" and agenda[0]["state"] == "in_progress"
    assert agenda[-1] == {"key": "ocs_attitude", "label": "工作態度", "state": "pending"}


@pytest.mark.asyncio
async def test_finish_no_llm_backstop_still_transitions_review(db_session):
    """v3(ADR 0030 T5):LLM 收尾複查退場(撿漏=每 N 回合確定性 sweep);
    finish 不再吃 backstop 結果,照樣轉 review、附結構化總結。"""
    p = await _profile(db_session)
    await start_interview(p.id, db=db_session)
    await interview_turn(p.id, {"text": "我們每兩週跑一次回歸"},
                         db=db_session, llm=StubLlm(select_result=GOOD), knowledge=K)
    out = await finish_interview(p.id, db=db_session, llm=None)
    assert out["phase"] == "review" and "summary" in out


@pytest.mark.asyncio
async def test_finish_without_llm_still_transitions(db_session):
    p = await _profile(db_session)
    await start_interview(p.id, db=db_session)
    out = await finish_interview(p.id, db=db_session, llm=None)   # backstop 略過,仍收尾
    assert out["phase"] == "review"


# interview:review(建議層批審)已退場(T12):✓/✗ 走前端 acceptPending/rejectPending
# + PATCH + review-events;端點測試見 test_interview_review_events.py。
