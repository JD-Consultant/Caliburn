"""T9:回合服務 v2 整合(真 DB + StubLlm + StubKnowledge)。
管線:書記 pass(set_slot 直寫/建議)→ 帳本 → 顧問 chat_with_tools → 保底。"""
import pytest
from uuid import uuid4

from app.adapters.interview_repo import InterviewRepo
from app.adapters.persistence import DocRepo
from app.adapters.stubs import StubKnowledge, StubLlm
from app.interview.service import NoActiveInterview, run_turn
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


async def _setup(db, *, human_touched=None):
    u = User(email=f"{uuid4()}@x.com", name="n"); db.add(u); await db.flush()
    p = JobProfile(user_id=u.id, job_title="工程師"); db.add(p); await db.flush()
    await DocRepo(db).save(p.id, _doc())
    repo = InterviewRepo(db)
    s = await repo.create(p.id)
    await repo.update_session(s.id, phase="deep", focus={"task_path": TASK_PATH})
    if human_touched:
        await repo.merge_human_touched(s.id, human_touched)
    return p, s, repo


# 書記記一個細項槽(v2 是 scribe records,非 v1 turn commands)
SCRIBE_SLOT = {"records": [
    {"type": "set_slot", "path": FREQ, "value": "每雙週", "quote": "每兩週跑一次"}]}


async def _run(db, text, *, select_result, human_touched=None, chat_text=None):
    p, s, repo = await _setup(db, human_touched=human_touched)
    kw = {"chat_text": chat_text} if chat_text is not None else {}
    llm = StubLlm(select_result=select_result, **kw)
    out = await run_turn(p.id, text, db=db, llm=llm, knowledge=StubKnowledge())
    return p, s, repo, out, llm


@pytest.mark.asyncio
async def test_scribe_writes_slot_and_consultant_replies(db_session):
    p, s, repo, out, _ = await _run(db_session, "我們每兩週跑一次回歸", select_result=SCRIBE_SLOT)
    assert out.doc_changed is True
    latest = await DocRepo(db_session).latest(p.id)
    task = latest["content"]["ocs_content"]["ocu_units"][0]["tasks"][0]
    assert task["details"]["frequency"] == "每雙週"
    ev = await repo.list_evidence(s.id)
    assert len(ev) == 1 and ev[0].verified is True and ev[0].review == "pending"   # 直寫標 pending
    turns = await repo.list_turns(s.id)
    assert [t.role for t in turns] == ["employee", "consultant"]
    assert out.say and turns[1].text == out.say                    # 顧問回覆落逐字稿
    assert out.coverage["required"] > 0                            # 覆蓋率進度


@pytest.mark.asyncio
async def test_human_touched_routes_to_suggestion(db_session):
    p, s, repo, out, _ = await _run(db_session, "每兩週跑一次",
                                    select_result=SCRIBE_SLOT, human_touched=[FREQ])
    assert out.doc_changed is False and out.pending_suggestions == 1
    latest = await DocRepo(db_session).latest(p.id)
    assert "details" not in latest["content"]["ocs_content"]["ocu_units"][0]["tasks"][0]


@pytest.mark.asyncio
async def test_scribe_failure_does_not_block_consultant(db_session):
    bad = {"records": [{"type": "set_slot"}]}                      # 缺欄→pydantic 兩度拒
    p, s, repo, out, _ = await _run(db_session, "隨便講講", select_result=bad,
                                    chat_text="沒關係,再多說一點?")
    assert out.doc_changed is False
    assert out.say == "沒關係,再多說一點?"                        # 顧問仍回應(fail-open)
    assert any("backstop" in g for g in out.guard_log)
    turns = await repo.list_turns(s.id)
    assert turns[1].role == "consultant"


@pytest.mark.asyncio
async def test_consultant_silence_gets_fallback(db_session):
    p, s, repo, out, _ = await _run(db_session, "嗨", select_result={"records": []}, chat_text="")
    assert out.say.strip()                                         # 保底:靜默→合成問題


@pytest.mark.asyncio
async def test_no_active_session_raises(db_session):
    u = User(email=f"{uuid4()}@x.com", name="n"); db_session.add(u); await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="x"); db_session.add(p); await db_session.flush()
    with pytest.raises(NoActiveInterview):
        await run_turn(p.id, "hi", db=db_session, llm=StubLlm(), knowledge=StubKnowledge())


@pytest.mark.asyncio
async def test_roles_scribe_select_consultant_interview(db_session):
    p, s, repo, out, llm = await _run(db_session, "每兩週跑一次", select_result=SCRIBE_SLOT)
    selects = [c for c in llm.calls if c["kind"] == "select"]
    chats = [c for c in llm.calls if c["kind"] == "chat"]
    assert selects and all(c["role"] == "select" for c in selects)       # 書記=便宜模型
    assert chats and all(c["role"] == "interview" for c in chats)        # 顧問=強模型
