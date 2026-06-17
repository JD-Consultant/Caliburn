import uuid
import pytest
from app.models import JobProfile, User
from app.services.persistence import DocRepo


async def _profile(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@t.co", name="t")
    prof = JobProfile(id=uuid.uuid4(), user_id=user.id, job_title="工程師")
    db_session.add_all([user, prof])
    await db_session.flush()
    return prof


@pytest.mark.asyncio
async def test_save_increments_version_and_latest(db_session):
    prof = await _profile(db_session)
    repo = DocRepo(db_session)
    v1 = await repo.save(prof.id, {"ocs_profile": {"ocs_code": "ENT-001"}})
    assert v1["version"] == 1 and v1["format"] == "json"
    v2 = await repo.save(prof.id, {"ocs_profile": {"ocs_code": "ENT-002"}})
    assert v2["version"] == 2
    latest = await repo.latest(prof.id)
    assert latest["version"] == 2 and latest["content"]["ocs_profile"]["ocs_code"] == "ENT-002"
