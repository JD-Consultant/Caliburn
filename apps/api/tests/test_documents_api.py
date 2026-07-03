"""REST document endpoints (D27 T3): GET/PATCH/finalize + set-occupations + list doc_status.

Transaction isolation: override get_db to yield the test's transaction-bound
db_session WITHOUT committing, so every ASGI request shares one rolled-back tx.
"""
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from app.api.routes.documents import get_knowledge
from app.database import get_db
from app.main import app
from app.models import JobProfile, User
from app.core.domain import ocs_doc
from app.core.knowledge_dto import (
    CodeName,
    CompetencyPool,
    OccupationDetail,
    OcsName,
)


class StubKnowledge:
    def __init__(self, comp_map=None, fail=False, tasks_map=None, occupations=None):
        self.comp_map, self.fail = comp_map or {}, fail
        self.tasks_map = tasks_map or {}
        self.occupations = occupations or {}

    async def competencies(self, ocs_code):
        if self.fail:
            raise RuntimeError("indexer down")
        return self.comp_map.get(ocs_code, CompetencyPool(ocs_code=ocs_code))

    async def occupation(self, ocs_code):
        if self.fail:
            raise RuntimeError("indexer down")
        return self.occupations[ocs_code]  # KeyError surfaces missing test setup

    async def occupation_tasks(self, ocs_code):
        if self.fail:
            raise RuntimeError("indexer down")
        return self.tasks_map[ocs_code]  # KeyError surfaces missing test setup


@pytest_asyncio.fixture
async def client(db_session):
    async def _db():
        yield db_session  # shared session; NO commit → fixture rolls back

    app.dependency_overrides[get_db] = _db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://t", follow_redirects=True
    ) as ac:
        ac._db = db_session
        yield ac
    app.dependency_overrides.clear()


async def _mk_profile(db_session, codes=None):
    u = User(email=f"{uuid4()}@x.com", name="n")
    db_session.add(u)
    await db_session.flush()
    p = JobProfile(
        user_id=u.id,
        job_title="工程師",
        job_summary="做事",
        selected_ocs_codes=codes or [],
    )
    db_session.add(p)
    await db_session.flush()
    return p


@pytest.mark.asyncio
async def test_get_document_no_doc_returns_skeleton(client):
    p = await _mk_profile(client._db)
    r = await client.get(f"/api/v1/job-profiles/{p.id}/document")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "none"
    assert body["version"] == 0
    assert body["revision"] == 0  # empty-skeleton envelope must carry revision too (2a Task B)
    assert body["content"]["ocs_content"]["ocu_units"] == []


@pytest.mark.asyncio
async def test_patch_then_get_roundtrips(client):
    p = await _mk_profile(client._db)
    doc = {
        "ocs_content": {
            "ocu_units": [
                {
                    "ocu_code": "T1",
                    "ocu_name": "u",
                    "tasks": [
                        {
                            "task_codes": [{"code": "T1.1", "name": "t"}],
                            "competency_blocks": [],
                        }
                    ],
                }
            ]
        },
        "ocs_attitude": {"attitudes": []},
    }
    r = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["version"] == 1

    r2 = await client.get(f"/api/v1/job-profiles/{p.id}/document")
    assert r2.status_code == 200
    assert r2.json()["content"] == doc


@pytest.mark.asyncio
async def test_patch_twice_no_version_bump(client):
    p = await _mk_profile(client._db)
    doc = {"ocs_content": {"ocu_units": []}, "ocs_attitude": {"attitudes": []}}
    r1 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    assert r1.json()["version"] == 1
    r2 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    assert r2.json()["version"] == 1


# --- optimistic-concurrency guard: expect_version/expect_revision (2a Task B, ADR 0015) ---


@pytest.mark.asyncio
async def test_patch_no_expect_params_is_legacy_unguarded(client):
    """不帶 expect_* → 200，行為同現況（opt-in，legacy 相容）。"""
    p = await _mk_profile(client._db)
    doc = {"ocs_content": {"ocu_units": []}, "ocs_attitude": {"attitudes": []}}
    r1 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    assert r1.status_code == 200, r1.text
    # a second PATCH with no expect params still overwrites unconditionally
    r2 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json={**doc, "k": 2})
    assert r2.status_code == 200, r2.text
    assert r2.json()["revision"] == 2


@pytest.mark.asyncio
async def test_patch_first_save_expect_zero_zero_succeeds(client):
    """無文件首存：expect (0,0) → 200，建 draft(version 1, revision 1)。"""
    p = await _mk_profile(client._db)
    doc = {"ocs_content": {"ocu_units": []}, "ocs_attitude": {"attitudes": []}}
    r = await client.patch(
        f"/api/v1/job-profiles/{p.id}/document?expect_version=0&expect_revision=0", json=doc
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == 1
    assert body["revision"] == 1


@pytest.mark.asyncio
async def test_patch_first_save_expect_zero_zero_but_already_exists_409(client):
    """無文件但 expect (0,0) 且已被別人建立 → 409。"""
    p = await _mk_profile(client._db)
    doc = {"ocs_content": {"ocu_units": []}, "ocs_attitude": {"attitudes": []}}
    r1 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    assert r1.status_code == 200, r1.text
    assert r1.json()["version"] == 1 and r1.json()["revision"] == 1

    r2 = await client.patch(
        f"/api/v1/job-profiles/{p.id}/document?expect_version=0&expect_revision=0",
        json={**doc, "k": 2},
    )
    assert r2.status_code == 409, r2.text
    detail = r2.json()["detail"]
    assert detail == {"code": "version_conflict", "current_version": 1, "current_revision": 1}


@pytest.mark.asyncio
async def test_patch_matching_expect_succeeds_and_bumps_revision(client):
    """帶 expect、token 相符 → 200；回應 revision = 原 +1。"""
    p = await _mk_profile(client._db)
    doc = {"ocs_content": {"ocu_units": []}, "ocs_attitude": {"attitudes": []}}
    r1 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    v, rev = r1.json()["version"], r1.json()["revision"]

    r2 = await client.patch(
        f"/api/v1/job-profiles/{p.id}/document?expect_version={v}&expect_revision={rev}",
        json={**doc, "k": 2},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["version"] == v
    assert r2.json()["revision"] == rev + 1


@pytest.mark.asyncio
async def test_patch_stale_revision_409_with_current_token(client):
    """expect_revision 過期（另一「分頁」先存）→ 409 + current_version/current_revision 正確。"""
    p = await _mk_profile(client._db)
    doc = {"ocs_content": {"ocu_units": []}, "ocs_attitude": {"attitudes": []}}
    r1 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    v, rev = r1.json()["version"], r1.json()["revision"]

    # "another tab" saves first, using the correct current token → revision advances
    other_tab = await client.patch(
        f"/api/v1/job-profiles/{p.id}/document?expect_version={v}&expect_revision={rev}",
        json={**doc, "k": "other-tab"},
    )
    assert other_tab.status_code == 200, other_tab.text
    assert other_tab.json()["revision"] == rev + 1

    # this tab retries with its now-stale token → 409, carrying the actual current token
    stale = await client.patch(
        f"/api/v1/job-profiles/{p.id}/document?expect_version={v}&expect_revision={rev}",
        json={**doc, "k": "this-tab-too-late"},
    )
    assert stale.status_code == 409, stale.text
    detail = stale.json()["detail"]
    assert detail == {
        "code": "version_conflict",
        "current_version": v,
        "current_revision": rev + 1,
    }


@pytest.mark.asyncio
async def test_patch_stale_version_after_finalize_409(client):
    """expect_version 過期（finalize 後 / 舊分頁）→ 409。"""
    p = await _mk_profile(client._db)
    skel = ocs_doc.skeleton(
        {"ocs_code": "OC1", "job_title": "x"},
        [{"task_name": "t", "unit_id": "T1", "unit_title": "u",
          "indexer_ref": {"task_code": "T1.1"}}],
    )
    r1 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=skel)
    v, rev = r1.json()["version"], r1.json()["revision"]
    assert v == 1

    fin = await client.post(f"/api/v1/job-profiles/{p.id}/document:finalize")
    assert fin.status_code == 200, fin.text
    assert fin.json()["version"] == 2 and fin.json()["revision"] == 1

    # old tab still holds the pre-finalize (version=1, revision=rev) token
    stale = await client.patch(
        f"/api/v1/job-profiles/{p.id}/document?expect_version={v}&expect_revision={rev}",
        json=skel,
    )
    assert stale.status_code == 409, stale.text
    detail = stale.json()["detail"]
    assert detail == {
        "code": "version_conflict",
        "current_version": 2,
        "current_revision": 1,
    }


@pytest.mark.asyncio
async def test_patch_concurrent_writer_via_core_update_still_409s_with_current_token(client):
    """另一 writer 繞過 ORM（Core UPDATE）直接推進 DB 列的 revision（代表任何非本 session 的
    寫入者，例如另一 worker process）→ 這個 session 下一次 PATCH 的 _latest_row() 是全新
    SELECT（route 每次請求都重新查詢，不持有跨請求的 ORM 物件），如實讀到 DB 最新值 → 落在
    DocConflictError（應用層 expected_* 檢查）而非 StaleDataError（flush 期 CAS）→ 409 +
    當前 token。

    （StaleDataError 本身——同一 flush 呼叫前一刻被搶先的窄視窗 CAS——與 route 的
    except StaleDataError 復原邏輯，由 tests/test_persistence_doc.py 的
    test_upsert_draft_guard_passes_app_check_but_cas_race_still_raises_stale_data_error 在
    repo 層驗證，其手法比照 Task A 的 test_concurrent_stale_update_raises_stale_data_error：
    在同一個未跨 request 邊界的 Python scope 內，靠 session identity map 保留一個仍記著舊
    revision 的 in-memory ORM 物件。經驗證：那個手法**無法**跨兩個獨立 HTTP request 重現——
    route 每次請求都用全新查詢，前一個 request 回應後其 ORM 物件在 session 的 identity map
    裡只是弱引用，物件已被回收，所以第二個 request 必然讀到 DB 的當下實際值，永遠不會落在
    "in-memory 仍是舊值但 DB 已變" 的窄縫。這才是本測試改用 DocConflictError 而非
    StaleDataError 案例的原因；本測試仍然驗證了一個真實情境：非本 session 的並發寫入者。）
    """
    from sqlalchemy import update
    from app.models import DocumentVersion

    p = await _mk_profile(client._db)
    doc = {"ocs_content": {"ocu_units": []}, "ocs_attitude": {"attitudes": []}}
    r1 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    v, rev = r1.json()["version"], r1.json()["revision"]
    assert (v, rev) == (1, 1)

    # Simulate a concurrent writer (e.g. another process/worker) landing between this
    # session's two requests: bump the DB row's revision via raw Core UPDATE.
    await client._db.execute(
        update(DocumentVersion)
        .where(DocumentVersion.job_profile_id == p.id)
        .values(revision=2, content={"k": "other-writer"})
        .execution_options(synchronize_session=False)
    )
    await client._db.flush()

    # This PATCH's expect_version/expect_revision still hold the pre-conflict token (1, 1).
    # The route's _latest_row() re-queries fresh and sees revision=2 → DocConflictError → 409
    # with the actual current token.
    r2 = await client.patch(
        f"/api/v1/job-profiles/{p.id}/document?expect_version={v}&expect_revision={rev}",
        json={**doc, "k": "this-request-too-late"},
    )
    assert r2.status_code == 409, r2.text
    detail = r2.json()["detail"]
    assert detail == {
        "code": "version_conflict",
        "current_version": 1,
        "current_revision": 2,
    }


@pytest.mark.asyncio
async def test_finalize_success(client):
    p = await _mk_profile(client._db)
    skel = ocs_doc.skeleton(
        {"ocs_code": "OC1", "job_title": "x"},
        [{"task_name": "t", "unit_id": "T1", "unit_title": "u",
          "indexer_ref": {"task_code": "T1.1"}}],
    )
    r1 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=skel)
    assert r1.json()["version"] == 1
    r = await client.post(f"/api/v1/job-profiles/{p.id}/document:finalize")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "final"
    assert body["version"] == 2


@pytest.mark.asyncio
async def test_finalize_invalid_returns_422(client):
    p = await _mk_profile(client._db)
    doc = {
        "ocs_content": {
            "ocu_units": [
                {
                    "ocu_code": "T1",
                    "ocu_name": "u",
                    "tasks": [
                        {
                            "task_codes": [],
                            "competency_blocks": [],
                        }
                    ],
                }
            ]
        },
        "ocs_attitude": {"attitudes": []},
    }
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    r = await client.post(f"/api/v1/job-profiles/{p.id}/document:finalize")
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert detail["errors"]


@pytest.mark.asyncio
async def test_finalize_no_document_returns_400(client):
    p = await _mk_profile(client._db)
    r = await client.post(f"/api/v1/job-profiles/{p.id}/document:finalize")
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_export_returns_clean_ocs_json(client):
    p = await _mk_profile(client._db)
    skel = ocs_doc.skeleton({"ocs_code": "OC1", "job_title": "x"},
                            [{"task_name": "t", "unit_id": "T1", "unit_title": "u",
                              "indexer_ref": {"task_code": "T1.1"}}])
    skel["_pool"] = {"knowledge": [], "skills": [], "attitudes": []}
    skel["ocs_content"]["ocu_units"][0]["_uid"] = "u-x"
    skel["ocs_content"]["ocu_units"][0]["tasks"][0]["_notes"] = "工作筆記原文"
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=skel)
    r = await client.get(f"/api/v1/job-profiles/{p.id}/document/export")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "_pool" not in body
    assert "_uid" not in body["ocs_content"]["ocu_units"][0]
    assert "_notes" not in body["ocs_content"]["ocu_units"][0]["tasks"][0]
    assert set(["version_info", "ocs_profile", "ocs_content", "ocs_attitude", "notes"]).issubset(body)


@pytest.mark.asyncio
async def test_export_no_document_returns_400(client):
    p = await _mk_profile(client._db)
    r = await client.get(f"/api/v1/job-profiles/{p.id}/document/export")
    assert r.status_code == 400, r.text


# ocs-search 測試已隨端點搬家:根層 GET /occupations?q= → tests/test_occupations_api.py(ADR 0019)。
# header-meta / task-candidates / task-catalogs / buildTasks 測試已隨端點退役刪除
# (P3,ADR 0021):web 改讀 /knowledge(tests/test_knowledge_api.py)、寫入走 PATCH。


@pytest.mark.asyncio
async def test_list_doc_status(client):
    p = await _mk_profile(client._db)
    r = await client.get(f"/api/v1/job-profiles?user_id={p.user_id}")
    assert r.status_code == 200, r.text
    items = r.json()
    entry = next(i for i in items if i["id"] == str(p.id))
    assert entry["doc_status"] == "none"
    assert entry["completion"] == 0.0

    doc = {
        "ocs_content": {
            "ocu_units": [
                {
                    "ocu_code": "T1",
                    "ocu_name": "u",
                    "tasks": [
                        {
                            "task_codes": [{"code": "T1.1", "name": "t"}],
                            "competency_blocks": [
                                {"outputs": ["o"], "indicators": [],
                                 "knowledge": [], "skills": []}
                            ],
                        }
                    ],
                }
            ]
        },
        "ocs_attitude": {"attitudes": []},
    }
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    r2 = await client.get(f"/api/v1/job-profiles?user_id={p.user_id}")
    entry2 = next(i for i in r2.json() if i["id"] == str(p.id))
    assert entry2["doc_status"] == "draft"
    assert entry2["completion"] > 0


@pytest.mark.asyncio
async def test_set_occupations(client, db_session):
    p = await _mk_profile(client._db)
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(
        occupations={
            "OC1": OccupationDetail(
                ocs_code="OC1",
                ocs_name=OcsName(occupation_name="官方職業A", job_category_name="類別A"),
            )
        }
    )
    r = await client.put(
        f"/api/v1/job-profiles/{p.id}/occupations", json={"ocs_codes": ["OC1", "OC2"]}
    )
    assert r.status_code == 200, r.text
    assert r.json()["ocs_codes"] == ["OC1", "OC2"]
    await db_session.refresh(p)
    assert p.selected_ocs_codes == ["OC1", "OC2"]
    g = await client.get(f"/api/v1/job-profiles/{p.id}/document")
    name = g.json()["content"]["ocs_profile"]["ocs_name"]
    # 官方名/職類名填入；絕不用 job_title（_mk_profile 的職稱）。
    assert name["occupation_name"] == "官方職業A"
    assert name["job_category_name"] == "類別A"


@pytest.mark.asyncio
async def test_set_occupations_refreshes_stale_draft_header(client):
    # repro: an empty draft (no ocs_code) exists before 選職類 → occupations must
    # refresh the draft header so 選任務 (FE gates on ocs_code) becomes enabled.
    p = await _mk_profile(client._db)
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(
        occupations={
            "OC1": OccupationDetail(
                ocs_code="OC1",
                ocs_name=OcsName(occupation_name="官方職業A", job_category_name="類別A"),
            )
        }
    )
    await client.patch(
        f"/api/v1/job-profiles/{p.id}/document",
        json={"ocs_content": {"ocu_units": []}, "ocs_profile": {"ocs_code": ""}},
    )
    r = await client.put(
        f"/api/v1/job-profiles/{p.id}/occupations", json={"ocs_codes": ["OC1"]}
    )
    assert r.status_code == 200, r.text
    g = await client.get(f"/api/v1/job-profiles/{p.id}/document")
    prof = g.json()["content"]["ocs_profile"]
    assert prof["ocs_code"] == "OC1"
    assert prof["ocs_name"]["occupation_name"] == "官方職業A"


@pytest.mark.asyncio
async def test_set_occupations_empty_400(client):
    p = await _mk_profile(client._db)
    r = await client.put(
        f"/api/v1/job-profiles/{p.id}/occupations", json={"ocs_codes": []}
    )
    assert r.status_code == 400, r.text
