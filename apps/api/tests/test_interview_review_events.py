"""審閱事件表(ADR 0030 T2):✓/✗/批量拒絕的無聲記帳。

家規:db_session fixture(真 PG,無 TEST_DATABASE_URL 即 skip、交易回滾)。
語意(§6.3):事件只記不觸發 AI;之後由 ledger 讀成「上輪被拒清單」供下回合利用。
"""
import pytest
from uuid import uuid4

from app.adapters.interview_repo import InterviewRepo
from app.models import JobProfile, User


async def _session(db_session):
    u = User(email=f"{uuid4()}@x.com", name="n")
    db_session.add(u)
    await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="工程師")
    db_session.add(p)
    await db_session.flush()
    repo = InterviewRepo(db_session)
    return repo, await repo.create(p.id)


@pytest.mark.asyncio
async def test_add_and_list_review_events(db_session):
    repo, s = await _session(db_session)
    n = await repo.add_review_events(s.id, [
        {"doc_path": "ocs_content.ocu_units.u1.tasks.t1", "decision": "accepted",
         "op_meta": {"op": "add", "turn_id": 3}},
        {"doc_path": "ocs_content.ocu_units.u1.tasks.t2", "decision": "rejected",
         "op_meta": {"op": "add", "turn_id": 3, "value": "跨部門協調"}},
    ])
    assert n == 2
    rows = await repo.list_review_events(s.id)
    assert [r.decision for r in rows] == ["accepted", "rejected"]
    assert rows[1].op_meta["value"] == "跨部門協調"


@pytest.mark.asyncio
async def test_batch_rejected_is_single_event(db_session):
    repo, s = await _session(db_session)
    await repo.add_review_events(s.id, [
        {"doc_path": "*", "decision": "batch_rejected", "op_meta": {"count": 7}},
    ])
    rows = await repo.list_review_events(s.id)
    assert len(rows) == 1 and rows[0].decision == "batch_rejected"


@pytest.mark.asyncio
async def test_rejected_since_turn_for_ledger(db_session):
    """T5 消費介面:取某回合之後被拒的路徑清單(不重提用)。"""
    repo, s = await _session(db_session)
    await repo.add_review_events(s.id, [
        {"doc_path": "p.a", "decision": "rejected", "op_meta": {"turn_id": 2}},
        {"doc_path": "p.b", "decision": "accepted", "op_meta": {"turn_id": 2}},
        {"doc_path": "p.c", "decision": "rejected", "op_meta": {"turn_id": 5}},
    ])
    rows = await repo.list_review_events(s.id, decision="rejected")
    assert [r.doc_path for r in rows] == ["p.a", "p.c"]
