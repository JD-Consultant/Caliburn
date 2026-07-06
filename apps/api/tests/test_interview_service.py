"""T8:回合服務整合(真 DB + StubLlm;無真 LLM)。"""
import pytest
from uuid import uuid4

from app.adapters.interview_repo import InterviewRepo
from app.adapters.llm_openrouter import LlmSchemaError
from app.adapters.persistence import DocRepo
from app.adapters.stubs import StubLlm
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


GOOD = {"commands": [
    {"type": "set_slot", "path": FREQ, "value": "每雙週", "quote": "每兩週跑一次"},
    {"type": "ask", "question": "一次大概跑多久?", "target_path": f"{TASK_PATH}.details.duration"},
], "saturation": False}


@pytest.mark.asyncio
async def test_happy_path_writes_doc_evidence_counters_transcript(db_session):
    p, s, repo = await _setup(db_session)
    out = await run_turn(p.id, "我們每兩週跑一次回歸", db=db_session,
                         llm=StubLlm(select_result=GOOD))
    assert out.doc_changed is True
    latest = await DocRepo(db_session).latest(p.id)
    task = latest["content"]["ocs_content"]["ocu_units"][0]["tasks"][0]
    assert task["details"]["frequency"] == "每雙週"
    ev = await repo.list_evidence(s.id)
    assert len(ev) == 1 and ev[0].verified is True
    turns = await repo.list_turns(s.id)
    assert [t.role for t in turns] == ["employee", "consultant"]
    assert "跑多久" in turns[1].text
    got = await repo.get_active(p.id)
    assert got.counters[f"{TASK_PATH}.details.duration"] == 1
    assert out.question["target_path"].endswith("duration")


@pytest.mark.asyncio
async def test_human_touched_routes_to_suggestion_not_doc(db_session):
    p, s, repo = await _setup(db_session, human_touched=[FREQ])
    out = await run_turn(p.id, "每兩週跑一次", db=db_session, llm=StubLlm(select_result=GOOD))
    assert out.doc_changed is False and out.pending_suggestions == 1
    latest = await DocRepo(db_session).latest(p.id)
    assert "details" not in latest["content"]["ocs_content"]["ocu_units"][0]["tasks"][0]


@pytest.mark.asyncio
async def test_semantic_invalid_retries_then_succeeds(db_session):
    p, s, repo = await _setup(db_session)
    state = {"n": 0}

    def flaky(prompt, schema):
        state["n"] += 1
        return {"commands": [{"type": "delete_all"}]} if state["n"] == 1 else GOOD

    out = await run_turn(p.id, "每兩週跑一次", db=db_session,
                         llm=StubLlm(select_result=flaky))
    assert state["n"] == 2 and out.doc_changed is True


@pytest.mark.asyncio
async def test_semantic_invalid_twice_raises(db_session):
    p, s, repo = await _setup(db_session)
    bad = StubLlm(select_result={"commands": [{"type": "delete_all"}], "saturation": False})
    with pytest.raises(LlmSchemaError):
        await run_turn(p.id, "x", db=db_session, llm=bad)


@pytest.mark.asyncio
async def test_no_active_session_raises(db_session):
    u = User(email=f"{uuid4()}@x.com", name="n"); db_session.add(u); await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="工程師"); db_session.add(p); await db_session.flush()
    with pytest.raises(NoActiveInterview):
        await run_turn(p.id, "hi", db=db_session, llm=StubLlm())


@pytest.mark.asyncio
async def test_silent_llm_output_still_records_consultant_turn(db_session):
    """RC2:模型漏 reply/ask 也要有可見回應+逐字稿落盤(實戰「沒反應」回歸網)。"""
    p, s, repo = await _setup(db_session)
    only_set = {"commands": [{"type": "set_slot", "path": FREQ, "value": "每雙週",
                              "quote": "每兩週跑一次"}], "saturation": False}
    out = await run_turn(p.id, "我們每兩週跑一次", db=db_session,
                         llm=StubLlm(select_result=only_set))
    assert out.say and out.question is not None
    turns = await repo.list_turns(s.id)
    assert [t.role for t in turns] == ["employee", "consultant"]
    assert turns[1].text                                   # 稽核軌跡不再消失


@pytest.mark.asyncio
async def test_turn_schema_locks_slot_paths(db_session):
    """接線驗證:deep 段丟給 LLM 的 schema,寫入 path 已用焦點任務槽位 enum 鎖死。"""
    p, s, repo = await _setup(db_session)
    seen = {}

    def capture(prompt, schema):
        seen["schema"] = schema
        return GOOD

    await run_turn(p.id, "每兩週跑一次", db=db_session, llm=StubLlm(select_result=capture))
    variants = seen["schema"]["properties"]["commands"]["items"]["anyOf"]
    by_tag = {v["properties"]["type"]["enum"][0]: v for v in variants}
    paths = by_tag["set_slot"]["properties"]["path"]["enum"]
    assert FREQ in paths and "ocs_profile.job_description" in paths
    assert all(".details." in x or x == "ocs_profile.job_description" for x in paths)


@pytest.mark.asyncio
async def test_advance_to_review_switches_phase(db_session):
    p, s, repo = await _setup(db_session)
    # light 任務:補齊三槽後 advance
    doc = _doc()
    doc["ocs_content"]["ocu_units"][0]["tasks"][0]["details"] = {
        "frequency": "每季", "time_share_pct": 5, "standards": "主管確認"}
    await DocRepo(db_session).upsert_draft(p.id, doc)
    out = await run_turn(p.id, "就這樣", db=db_session, llm=StubLlm(select_result={
        "commands": [{"type": "advance", "next_focus": "review"}], "saturation": True}))
    assert out.phase == "review"
    got = await repo.get_active(p.id)
    assert got.phase == "review"
