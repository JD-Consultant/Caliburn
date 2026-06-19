import pytest
from uuid import uuid4
from sqlalchemy import select
from app.models import JobProfile, User
from app.services.persistence import ProfileRepo, DocRepo


@pytest.mark.asyncio
async def test_set_selected_ocs_writes_array(db_session):
    u = User(email=f"{uuid4()}@x.com", name="n"); db_session.add(u); await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="工程師"); db_session.add(p); await db_session.flush()
    await ProfileRepo(db_session).set_selected_ocs(p.id, ["OC2", "OC1"])
    row = (await db_session.execute(select(JobProfile).where(JobProfile.id == p.id))).scalar_one()
    assert row.selected_ocs_codes == ["OC2", "OC1"]


@pytest.mark.asyncio
async def test_doc_repo_save_increments_version(db_session):
    u = User(email=f"{uuid4()}@x.com", name="n"); db_session.add(u); await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="工程師"); db_session.add(p); await db_session.flush()
    r1 = await DocRepo(db_session).save(p.id, {"ocs_profile": {}})
    r2 = await DocRepo(db_session).save(p.id, {"ocs_profile": {}})
    assert r1["version"] == 1 and r2["version"] == 2
