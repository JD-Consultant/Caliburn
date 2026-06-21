import pytest
from uuid import uuid4
from sqlalchemy import select
from app.models import JobProfile, User
from app.services.persistence import ProfileRepo, DocRepo, compute_completion


def _doc(*, outputs=None, indicators=None, knowledge=None, skills=None, attitudes=None):
    """Build a single-task OCS document with the given cell contents."""
    block = {
        "competency_level": "L1",
        "outputs": list(outputs or []),
        "indicators": list(indicators or []),
        "knowledge": list(knowledge or []),
        "skills": list(skills or []),
    }
    return {
        "ocs_content": {"ocu_units": [{"tasks": [{"competency_blocks": [block]}]}]},
        "ocs_attitude": {"attitudes": list(attitudes or [])},
    }


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
    r1 = await DocRepo(db_session).save(p.id, {"ocs_profile": {"ocs_code": "ENT-001"}})
    r2 = await DocRepo(db_session).save(p.id, {"ocs_profile": {"ocs_code": "ENT-002"}})
    assert r1["version"] == 1 and r2["version"] == 2
    latest = await DocRepo(db_session).latest(p.id)
    assert latest["version"] == 2 and latest["content"]["ocs_profile"]["ocs_code"] == "ENT-002"


# --- compute_completion pure tests (no DB) ---

def test_compute_completion_all_empty():
    assert compute_completion(_doc()) == pytest.approx(1 / 6)


def test_compute_completion_only_outputs():
    assert compute_completion(_doc(outputs=["o1"])) == pytest.approx(2 / 6)


def test_compute_completion_full():
    doc = _doc(outputs=["o"], indicators=["p"], knowledge=["k"],
               skills=["s"], attitudes=["a"])
    assert compute_completion(doc) == pytest.approx(1.0)


# --- upsert_draft / finalize / status_of (DB) ---

async def _seed_profile(db_session):
    u = User(email=f"{uuid4()}@x.com", name="n"); db_session.add(u); await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="工程師"); db_session.add(p); await db_session.flush()
    return p


@pytest.mark.asyncio
async def test_upsert_draft_does_not_bump_version(db_session):
    p = await _seed_profile(db_session)
    repo = DocRepo(db_session)
    r1 = await repo.upsert_draft(p.id, {"k": 1})
    r2 = await repo.upsert_draft(p.id, {"k": 2})
    assert r1["version"] == 1 and r2["version"] == 1
    latest = await repo.latest(p.id)
    assert latest["version"] == 1 and latest["content"]["k"] == 2


@pytest.mark.asyncio
async def test_finalize_bumps_version_and_sets_status(db_session):
    p = await _seed_profile(db_session)
    repo = DocRepo(db_session)
    await repo.upsert_draft(p.id, {"k": 1})
    fin = await repo.finalize(p.id)
    assert fin["version"] == 2 and fin["status"] == "final"
    # latest is now final, so a new upsert_draft inserts a new draft row
    nxt = await repo.upsert_draft(p.id, {"k": 3})
    assert nxt["version"] == 3 and nxt["status"] == "draft"


@pytest.mark.asyncio
async def test_finalize_no_document_raises(db_session):
    p = await _seed_profile(db_session)
    with pytest.raises(ValueError):
        await DocRepo(db_session).finalize(p.id)


@pytest.mark.asyncio
async def test_status_of_three_states(db_session):
    p = await _seed_profile(db_session)
    repo = DocRepo(db_session)
    assert await repo.status_of(p.id) == ("none", 0.0)

    partial = _doc(outputs=["o1"])
    await repo.upsert_draft(p.id, partial)
    status, comp = await repo.status_of(p.id)
    assert status == "draft" and comp == pytest.approx(compute_completion(partial))

    await repo.finalize(p.id)
    status, comp = await repo.status_of(p.id)
    assert status == "final" and comp == pytest.approx(compute_completion(partial))
