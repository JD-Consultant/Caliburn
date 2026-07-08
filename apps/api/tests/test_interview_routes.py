"""T9:interview 四端點(直呼 route 函式 + 真 DB + StubLlm)。"""
import pytest
from uuid import uuid4

from fastapi import HTTPException

from app.adapters.interview_repo import InterviewRepo
from app.adapters.persistence import DocRepo
from app.adapters.stubs import StubKnowledge, StubLlm
from app.api.routes.interview import (
    get_interview, interview_turn, review_interview, start_interview,
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
async def test_start_requires_tasks(db_session):
    p = await _profile(db_session, with_doc=False)
    with pytest.raises(HTTPException) as e:
        await start_interview(p.id, db=db_session)
    assert e.value.status_code == 409 and e.value.detail["code"] == "no_tasks"


@pytest.mark.asyncio
async def test_start_idempotent_and_inits_focus(db_session):
    p = await _profile(db_session)
    out1 = await start_interview(p.id, db=db_session)
    out2 = await start_interview(p.id, db=db_session)
    assert out1["session_id"] == out2["session_id"]
    assert out1["focus"]["task_path"] == TASK_PATH
    assert out1["progress"] == {"phase": "deep", "task_index": 1, "task_total": 1}
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
    assert view["evidence"][0]["verified"] is True
    assert view["status"] == "active"


@pytest.mark.asyncio
async def test_review_status_only(db_session):
    p = await _profile(db_session)
    await start_interview(p.id, db=db_session)
    repo = InterviewRepo(db_session)
    s = await repo.get_active(p.id)
    await repo.merge_human_touched(s.id, [FREQ])   # 逼建議
    await interview_turn(p.id, {"text": "每兩週跑一次"},
                         db=db_session, llm=StubLlm(select_result=GOOD), knowledge=K)
    view = await get_interview(p.id, db=db_session)
    sug_id = view["suggestions"][0]["id"]
    out = await review_interview(p.id, {"accept": [sug_id]}, db=db_session)
    assert out["accepted"][0]["doc_path"] == FREQ and out["pending"] == 0
    # 只轉狀態,不寫文件(套用是前端的事)
    latest = await DocRepo(db_session).latest(p.id)
    assert "details" not in latest["content"]["ocs_content"]["ocu_units"][0]["tasks"][0]
