import uuid
import pytest
from app.models import JobProfile, User
from app.graph_v3.deps import DbPersist
from app.services.persistence import TaskRepo


@pytest.mark.asyncio
async def test_dbpersist_flush_and_select(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@t.co", name="t")
    prof = JobProfile(id=uuid.uuid4(), user_id=user.id, job_title="工程師")
    db_session.add_all([user, prof])
    await db_session.flush()

    persist = DbPersist(session=db_session)
    await persist.set_selected_ocs(prof.id, "OC1")
    await persist.flush_tasks(prof.id, [{"task_name": "巡檢", "source": "catalog"}])

    assert (await db_session.get(JobProfile, prof.id)).selected_ocs_code == "OC1"
    assert (await TaskRepo(db_session).hydrate(prof.id))[0]["task_name"] == "巡檢"


@pytest.mark.asyncio
async def test_dbpersist_flush_ksa_and_save_document(db_session):
    import uuid
    from app.models import JobProfile, User
    from app.graph_v3.deps import DbPersist
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@t.co", name="t")
    prof = JobProfile(id=uuid.uuid4(), user_id=user.id, job_title="工程師")
    db_session.add_all([user, prof])
    await db_session.flush()

    p = DbPersist(db_session)
    await p.flush_ksa(prof.id, {"knowledge": [{"content": "A", "source": "catalog", "icap_ref": "K01"}],
                                "skills": [], "attitudes": []})
    doc = await p.save_document(prof.id, {"ocs_profile": {"ocs_code": "ENT-001"}})
    assert doc["version"] == 1
