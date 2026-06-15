import uuid

import pytest

from app.models import JobProfile, User
from app.services.persistence import TaskRepo


@pytest.mark.asyncio
async def test_flush_then_hydrate_roundtrip(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@t.co", name="t")
    prof = JobProfile(id=uuid.uuid4(), user_id=user.id, job_title="工程師")
    db_session.add_all([user, prof])
    await db_session.flush()

    repo = TaskRepo(db_session)
    tasks = [{"task_name": "巡檢", "source": "catalog",
              "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}}]
    await repo.flush(prof.id, tasks)

    got = await repo.hydrate(prof.id)
    assert len(got) == 1 and got[0]["task_name"] == "巡檢"
    assert got[0]["source"] == "catalog"
    assert got[0]["indexer_ref"] == {"ocs_code": "OC1", "task_id": "T1.1"}


@pytest.mark.asyncio
async def test_flush_is_idempotent_keeps_row_id(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@t.co", name="t")
    prof = JobProfile(id=uuid.uuid4(), user_id=user.id, job_title="工程師")
    db_session.add_all([user, prof])
    await db_session.flush()

    repo = TaskRepo(db_session)
    await repo.flush(prof.id, [{"task_name": "巡檢", "source": "catalog",
                                "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}}])
    first = (await repo.hydrate(prof.id))[0]["id"]
    # 第二次 flush 同一任務（task_name 不變）→ 應 update 同 row，不新建
    await repo.flush(prof.id, [{"task_name": "巡檢", "source": "catalog",
                                "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"},
                                "frequency": "每日"}])
    rows = await repo.hydrate(prof.id)
    assert len(rows) == 1 and rows[0]["id"] == first and rows[0]["frequency"] == "每日"


@pytest.mark.asyncio
async def test_flush_deletes_dropped_tasks(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@t.co", name="t")
    prof = JobProfile(id=uuid.uuid4(), user_id=user.id, job_title="工程師")
    db_session.add_all([user, prof])
    await db_session.flush()

    repo = TaskRepo(db_session)
    await repo.flush(prof.id, [{"task_name": "A"}, {"task_name": "B"}])
    await repo.flush(prof.id, [{"task_name": "A"}])   # B 被移除
    rows = await repo.hydrate(prof.id)
    assert [r["task_name"] for r in rows] == ["A"]
