import uuid
import pytest
from app.models import JobProfile, User
from app.services.persistence import KsaRepo


async def _profile(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@t.co", name="t")
    prof = JobProfile(id=uuid.uuid4(), user_id=user.id, job_title="工程師")
    db_session.add_all([user, prof])
    await db_session.flush()
    return prof


@pytest.mark.asyncio
async def test_ksa_flush_then_hydrate(db_session):
    prof = await _profile(db_session)
    repo = KsaRepo(db_session)
    ksa = {
        "knowledge": [{"content": "設備原理", "source": "catalog", "icap_ref": "K01"}],
        "skills": [{"content": "點檢操作", "source": "company", "icap_ref": None}],
        "attitudes": [{"content": "細心", "source": "company", "icap_ref": None}],
    }
    await repo.flush(prof.id, ksa)
    got = await repo.hydrate(prof.id)
    assert [k["content"] for k in got["knowledge"]] == ["設備原理"]
    assert got["knowledge"][0]["source"] == "catalog" and got["knowledge"][0]["icap_ref"] == "K01"
    assert got["skills"][0]["content"] == "點檢操作"
    assert got["attitudes"][0]["content"] == "細心"


@pytest.mark.asyncio
async def test_ksa_flush_idempotent_keeps_row_id(db_session):
    prof = await _profile(db_session)
    repo = KsaRepo(db_session)
    await repo.flush(prof.id, {"knowledge": [{"content": "設備原理", "source": "catalog", "icap_ref": "K01"}],
                               "skills": [], "attitudes": []})
    first = (await repo.hydrate(prof.id))["knowledge"][0]["id"]
    # 再 flush 同 content（K 類）→ update 同 row，不新建
    await repo.flush(prof.id, {"knowledge": [{"content": "設備原理", "source": "company", "icap_ref": None}],
                               "skills": [], "attitudes": []})
    rows = await repo.hydrate(prof.id)
    assert len(rows["knowledge"]) == 1 and rows["knowledge"][0]["id"] == first
    assert rows["knowledge"][0]["source"] == "company"   # 已更新
