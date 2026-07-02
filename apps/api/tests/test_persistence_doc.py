import pytest
from uuid import uuid4
from sqlalchemy import select
from app.models import JobProfile, User
from app.adapters.persistence import ProfileRepo, DocRepo
from app.core.domain.ocs_doc import compute_completion


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


# --- revision (SQLAlchemy version_id_col optimistic-concurrency counter, ADR 0015 / 2a Task A) ---

@pytest.mark.asyncio
async def test_upsert_draft_twice_increments_revision(db_session):
    """就地更新同一 draft 列（version 不變）：revision 應由 version_id_col 逐次 +1。"""
    p = await _seed_profile(db_session)
    repo = DocRepo(db_session)
    r1 = await repo.upsert_draft(p.id, {"k": 1})
    r2 = await repo.upsert_draft(p.id, {"k": 2})
    r3 = await repo.upsert_draft(p.id, {"k": 3})
    assert r1["revision"] == 1
    assert r2["revision"] == 2
    assert r3["revision"] == 3
    # version stays put across in-place updates (unchanged existing behavior)
    assert r1["version"] == r2["version"] == r3["version"] == 1
    latest = await repo.latest(p.id)
    assert latest["revision"] == 3 and latest["content"]["k"] == 3


@pytest.mark.asyncio
async def test_finalize_new_row_revision_starts_at_one(db_session):
    """finalize INSERT 新列：revision 從 1 起（與既有列的 revision 無關）。"""
    p = await _seed_profile(db_session)
    repo = DocRepo(db_session)
    await repo.upsert_draft(p.id, {"k": 1})
    await repo.upsert_draft(p.id, {"k": 2})  # bump draft row's revision to 2
    fin = await repo.finalize(p.id)
    assert fin["version"] == 2 and fin["status"] == "final"
    assert fin["revision"] == 1
    # subsequent new draft row (after final) also starts its own revision at 1
    nxt = await repo.upsert_draft(p.id, {"k": 3})
    assert nxt["version"] == 3 and nxt["revision"] == 1


@pytest.mark.asyncio
@pytest.mark.filterwarnings(
    "ignore:transaction already deassociated from connection:sqlalchemy.exc.SAWarning"
)
async def test_concurrent_stale_update_raises_stale_data_error(db_session):
    """雙分頁同毫秒競態的最終防線：version_id_col 的 CAS。

    模擬「另一分頁已搶先存過」：直接用 Core UPDATE 繞過 ORM 把 DB 列的 revision 推進
    （代表其他 writer 的既成事實），接著讓**已經讀到舊 revision 的 ORM 物件**再次 flush——
    它組出的 WHERE revision=<舊值> 命中 0 rows，SQLAlchemy 應拋 StaleDataError（非本專案發明，
    SQLAlchemy 官方 optimistic-concurrency 機制：https://docs.sqlalchemy.org/en/20/orm/versioning.html）。

    註：filterwarnings 只壓這一個已知良性訊息——db_session fixture（tests/conftest.py）用
    「join 外部 conn.begin()」模式，任何 flush 失敗都會讓 fixture 收尾的 trans.rollback() 印出
    "transaction already deassociated from connection"（已用一個無關的 UNIQUE 違反測試驗證過，
    非 StaleDataError 特有、非本測試邏輯有誤）。真正修法是 fixture 改用
    join_transaction_mode="create_savepoint"，但那是 conftest.py 改動，超出本 task 範圍
    （本 task 只動 migration/model/persistence.py/本檔）。
    """
    from sqlalchemy import update
    from sqlalchemy.orm.exc import StaleDataError
    from app.models import DocumentVersion

    p = await _seed_profile(db_session)
    repo = DocRepo(db_session)
    r1 = await repo.upsert_draft(p.id, {"k": 1})
    assert r1["revision"] == 1

    # ORM object still believes revision == 1 (its in-memory state after the flush above).
    row = await repo._latest_row(p.id)
    assert row.revision == 1

    # Simulate a concurrent writer landing first: bump the DB row's revision via raw Core
    # UPDATE, bypassing this session's ORM identity map/unit-of-work entirely.
    # synchronize_session=False is essential here: the ORM-enabled update() construct
    # otherwise auto-patches any already-loaded in-memory object matching the WHERE clause
    # (confirmed empirically — without this flag `row.revision` silently becomes 2 too,
    # which would defeat the staleness this test is simulating).
    await db_session.execute(
        update(DocumentVersion)
        .where(DocumentVersion.id == row.id)
        .values(revision=2, content={"k": "other-tab"})
        .execution_options(synchronize_session=False)
    )
    await db_session.flush()

    # Now mutate via the *stale* ORM object (still holds revision == 1 in memory) and flush.
    # SQLAlchemy appends "AND revision = 1" to its UPDATE; that matches 0 rows in the DB
    # (which now has revision = 2) → StaleDataError.
    row.content = {"k": "this-tab-too-late"}
    with pytest.raises(StaleDataError):
        await db_session.flush()

    # A failed flush leaves the Session in an "inactive" state that requires rollback
    # before further use (SQLAlchemy docs). Doing so here — rather than leaving it purely
    # to the fixture's teardown — restores session.is_active for good measure, though the
    # fixture's own outer trans.rollback() still hits the deassociated connection-level
    # transaction regardless (see filterwarnings note above).
    await db_session.rollback()


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
