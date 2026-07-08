"""InterviewRepo(T2):sessions/turns/evidence/suggestions CRUD 與守則。

家規:db_session fixture(真 PG,無 TEST_DATABASE_URL 即 skip、交易回滾)。
守則:同 profile 同時最多一個 active session(應用層檢查 + DB partial unique 雙保險,
對齊 persistence.md 的雙保險慣例)。
"""
import pytest
from uuid import uuid4

from app.models import JobProfile, User
from app.adapters.interview_repo import ActiveInterviewExists, InterviewRepo


async def _profile(db_session):
    u = User(email=f"{uuid4()}@x.com", name="n")
    db_session.add(u)
    await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="工程師")
    db_session.add(p)
    await db_session.flush()
    return p


@pytest.mark.asyncio
async def test_create_defaults_and_get_active(db_session):
    p = await _profile(db_session)
    repo = InterviewRepo(db_session)
    s = await repo.create(p.id)
    assert s.status == "active" and s.phase == "survey"
    assert s.focus == {} and s.counters == {} and s.human_touched == []
    got = await repo.get_active(p.id)
    assert got is not None and got.id == s.id


@pytest.mark.asyncio
async def test_second_active_refused(db_session):
    p = await _profile(db_session)
    repo = InterviewRepo(db_session)
    await repo.create(p.id)
    with pytest.raises(ActiveInterviewExists):
        await repo.create(p.id)


@pytest.mark.asyncio
async def test_done_session_allows_new_active(db_session):
    p = await _profile(db_session)
    repo = InterviewRepo(db_session)
    s1 = await repo.create(p.id)
    await repo.update_session(s1.id, status="done")
    s2 = await repo.create(p.id)
    assert s2.id != s1.id
    got = await repo.get_active(p.id)
    assert got.id == s2.id


@pytest.mark.asyncio
async def test_update_session_fields(db_session):
    p = await _profile(db_session)
    repo = InterviewRepo(db_session)
    s = await repo.create(p.id)
    await repo.update_session(s.id, phase="deep",
                              focus={"task": "T1.1", "slot": "frequency"},
                              counters={"T1.1/frequency": 1})
    got = await repo.get_active(p.id)
    assert got.phase == "deep"
    assert got.focus["task"] == "T1.1"
    assert got.counters == {"T1.1/frequency": 1}


@pytest.mark.asyncio
async def test_ledger_state_defaults_and_roundtrip(db_session):
    """T2:ledger_state 預設 {} + 往返 + 重算一致性(存回的 attempts 餵 ledger 同結果)。"""
    from app.interview import ledger as L
    p = await _profile(db_session)
    repo = InterviewRepo(db_session)
    s = await repo.create(p.id)
    assert s.ledger_state == {}                                   # server_default
    state = {"attempts": {"ocs_content.ocu_units.U1.tasks.C.details.wait_points": L.STALL_K},
             "tier_override": {"ocs_content.ocu_units.U1.tasks.C": "light"},
             "probe": {"depth": "deep", "style": "warm"}}
    await repo.update_session(s.id, ledger_state=state)
    got = await repo.get_active(p.id)
    assert got.ledger_state == state                             # JSONB 往返無損
    # 重算一致性:存回的狀態餵純函式 → 確定性同結果
    assert L.is_stalled(got.ledger_state,
                        "ocs_content.ocu_units.U1.tasks.C.details.wait_points")


@pytest.mark.asyncio
async def test_merge_human_touched_dedupes(db_session):
    p = await _profile(db_session)
    repo = InterviewRepo(db_session)
    s = await repo.create(p.id)
    await repo.merge_human_touched(s.id, ["a.b", "c.d"])
    await repo.merge_human_touched(s.id, ["c.d", "e.f"])
    got = await repo.get_active(p.id)
    assert got.human_touched == ["a.b", "c.d", "e.f"]


@pytest.mark.asyncio
async def test_turns_seq_monotonic(db_session):
    p = await _profile(db_session)
    repo = InterviewRepo(db_session)
    s = await repo.create(p.id)
    t1 = await repo.append_turn(s.id, role="consultant", text="請描述你的工作")
    t2 = await repo.append_turn(s.id, role="employee", text="我做軟體測試",
                                commands=[{"type": "reply", "text": "hi"}])
    t3 = await repo.append_turn(s.id, role="consultant", text="多久跑一次回歸?")
    assert (t1.seq, t2.seq, t3.seq) == (1, 2, 3)
    assert t2.commands[0]["type"] == "reply"


@pytest.mark.asyncio
async def test_evidence_roundtrip(db_session):
    p = await _profile(db_session)
    repo = InterviewRepo(db_session)
    s = await repo.create(p.id)
    await repo.add_evidence(s.id, doc_path="units.0.tasks.0.details.frequency",
                            quote="上線前那兩天都在跑回歸", turn_seq=2, verified=True)
    rows = await repo.list_evidence(s.id)
    assert len(rows) == 1 and rows[0].verified is True
    assert rows[0].quote.startswith("上線前")


@pytest.mark.asyncio
async def test_evidence_review_roundtrip(db_session):
    """T5:evidence.review 預設 auto、可標 pending、批次審裁決 + pending 查詢。"""
    p = await _profile(db_session)
    repo = InterviewRepo(db_session)
    s = await repo.create(p.id)
    auto = await repo.add_evidence(s.id, doc_path="a.b.c", quote="x", turn_seq=1, verified=True)
    pend = await repo.add_evidence(s.id, doc_path="d.e.f", quote="y", turn_seq=1,
                                   verified=True, review="pending")
    assert auto.review == "auto" and pend.review == "pending"
    assert [e.id for e in await repo.list_pending_evidence(s.id)] == [pend.id]
    await repo.set_evidence_review(pend.id, "accepted")
    assert await repo.list_pending_evidence(s.id) == []


@pytest.mark.asyncio
async def test_suggestions_pending_flow(db_session):
    p = await _profile(db_session)
    repo = InterviewRepo(db_session)
    s = await repo.create(p.id)
    sug = await repo.add_suggestion(s.id, doc_path="units.0.tasks.0.details.standards",
                                    old_value="組長口頭確認", new_value="組長審查通過並簽核",
                                    reason="後續訪談提到簽核流程", turn_seq=9)
    pending = await repo.list_pending(s.id)
    assert [x.id for x in pending] == [sug.id]
    await repo.set_suggestion_status(sug.id, "accepted")
    assert await repo.list_pending(s.id) == []
