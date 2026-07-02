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


# --- upsert_draft optimistic-concurrency guard: expected_version/expected_revision
# (2a Task B, ADR 0015) ---


@pytest.mark.asyncio
async def test_upsert_draft_guard_matching_expected_succeeds(db_session):
    """兩者皆給且與最新列相符 → 正常就地更新，revision 照常 +1。"""
    p = await _seed_profile(db_session)
    repo = DocRepo(db_session)
    r1 = await repo.upsert_draft(p.id, {"k": 1})
    r2 = await repo.upsert_draft(
        p.id, {"k": 2}, expected_version=r1["version"], expected_revision=r1["revision"]
    )
    assert r2["version"] == r1["version"]
    assert r2["revision"] == r1["revision"] + 1


@pytest.mark.asyncio
async def test_upsert_draft_guard_no_row_expects_zero_zero_succeeds(db_session):
    """無列視為 (0, 0)：首存 expected_version=0, expected_revision=0 → 成功建立 draft。"""
    p = await _seed_profile(db_session)
    repo = DocRepo(db_session)
    r1 = await repo.upsert_draft(p.id, {"k": 1}, expected_version=0, expected_revision=0)
    assert r1["version"] == 1 and r1["revision"] == 1


@pytest.mark.asyncio
async def test_upsert_draft_guard_mismatch_raises_doc_conflict_error(db_session):
    """不符 → raise DocConflictError(current_version, current_revision)（無列視為 (0,0)）。"""
    from app.adapters.persistence import DocConflictError

    p = await _seed_profile(db_session)
    repo = DocRepo(db_session)

    # no row yet, but caller claims to expect (1, 1) → conflict against the "no row" (0, 0) baseline
    with pytest.raises(DocConflictError) as exc_info:
        await repo.upsert_draft(p.id, {"k": 1}, expected_version=1, expected_revision=1)
    assert exc_info.value.current_version == 0
    assert exc_info.value.current_revision == 0

    # now seed a row and try a stale token against it
    r1 = await repo.upsert_draft(p.id, {"k": 1})
    with pytest.raises(DocConflictError) as exc_info2:
        await repo.upsert_draft(
            p.id, {"k": 2}, expected_version=r1["version"], expected_revision=r1["revision"] + 1
        )
    assert exc_info2.value.current_version == r1["version"]
    assert exc_info2.value.current_revision == r1["revision"]


@pytest.mark.asyncio
async def test_upsert_draft_guard_only_one_of_pair_given_is_unguarded(db_session):
    """spec：兩者皆給時才檢查；只給一個視為不守衛（legacy 相容，非本任務要收緊的範圍）。"""
    p = await _seed_profile(db_session)
    repo = DocRepo(db_session)
    r1 = await repo.upsert_draft(p.id, {"k": 1})
    # wrong expected_version alone, expected_revision omitted → guard not engaged, still succeeds
    r2 = await repo.upsert_draft(p.id, {"k": 2}, expected_version=999)
    assert r2["version"] == r1["version"]
    assert r2["revision"] == r1["revision"] + 1


@pytest.mark.asyncio
@pytest.mark.filterwarnings(
    "ignore:transaction already deassociated from connection:sqlalchemy.exc.SAWarning"
)
async def test_upsert_draft_guard_passes_app_check_but_cas_race_still_raises_stale_data_error(
    db_session,
):
    """CAS 競態視窗：expected_version/expected_revision 與**這個 session 記憶中**的舊值相符
    （通過 upsert_draft 的應用層 DocConflictError 檢查），但另一個 writer 已經在 DB 層把
    revision 推進過去（本測試同 Task A 的 test_concurrent_stale_update_raises_stale_data_error
    手法，用 Core UPDATE + synchronize_session=False 模擬）→ flush 時 version_id_col 的 CAS
    UPDATE 撞到 DB 實際值、0 rows 命中 → StaleDataError（不是 DocConflictError；兩者是不同
    的防線——前者是應用層先檢查、後者是 flush 期的最終 DB 層 CAS 兜底）。

    route（app/api/routes/documents.py::patch_document）的 except StaleDataError 分支即是
    為了兜住這個窗口而寫；此處在 repo 層直接證明「通過 upsert_draft 的守衛檢查」與
    「仍然可能在 flush 觸發 StaleDataError」兩者並不互斥——這正是 route 需要兩個獨立
    except 子句（DocConflictError 和 StaleDataError）的原因。

    注意：此手法依賴同一個 in-memory ORM 物件在 Core UPDATE 前後被同一個 session 的 identity
    map 保留（未經 GC、未跨 request 邊界重新查詢）——已驗證這**無法**簡單地跨兩個獨立 HTTP
    PATCH request 重現（route 每次請求都是全新 `_latest_row()` 查詢，前一 request 的 ORM 物件
    只是弱引用、對下一個 request 不可見），因此本測試特意留在 repo 層、在單一未中斷的 await
    鏈中完成（同 Task A 的既有測試手法）。

    filterwarnings 理由同 Task A：db_session fixture 用「join 外部 conn.begin()」模式，flush
    失敗需要的 rollback 會把 fixture 外層那條 trans 一併結束，導致 fixture teardown 印出一個
    無害但吵的 SAWarning（非本測試邏輯有誤）。
    """
    from sqlalchemy import update
    from sqlalchemy.orm.exc import StaleDataError
    from app.models import DocumentVersion

    p = await _seed_profile(db_session)
    repo = DocRepo(db_session)
    r1 = await repo.upsert_draft(p.id, {"k": 1})
    assert (r1["version"], r1["revision"]) == (1, 1)

    # Keep the same repo (and thus the same session/identity-map) alive across the "other
    # writer" simulation, matching Task A's proven approach.
    row = await repo._latest_row(p.id)
    assert row.revision == 1

    # Another writer lands first: bump the DB row's revision via raw Core UPDATE, bypassing
    # this session's identity map/unit-of-work (synchronize_session=False is essential — see
    # Task A's note in test_concurrent_stale_update_raises_stale_data_error).
    await db_session.execute(
        update(DocumentVersion)
        .where(DocumentVersion.id == row.id)
        .values(revision=2, content={"k": "other-writer"})
        .execution_options(synchronize_session=False)
    )
    await db_session.flush()
    assert row.revision == 1  # still stale in this session's memory

    # expected_version/expected_revision match the *stale* in-memory value → passes the
    # app-layer DocConflictError check inside upsert_draft — but the flush's CAS UPDATE
    # (WHERE ... AND revision=1) now hits 0 rows in the DB (which is at revision=2) →
    # StaleDataError, not DocConflictError.
    with pytest.raises(StaleDataError):
        await repo.upsert_draft(
            p.id, {"k": "this-session-too-late"}, expected_version=1, expected_revision=1
        )

    # A failed flush leaves the Session inactive until rolled back (SQLAlchemy requirement;
    # mirrors what the route's except StaleDataError branch does via `await db.rollback()`).
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
