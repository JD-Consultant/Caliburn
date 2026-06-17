import os
import uuid
import pytest
from app.database import AsyncSessionLocal
from app.models import JobProfile, User
from app.graph_v3.deps import LiveDbPersist
from app.services.persistence import KsaRepo, DocRepo

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"),
                                reason="TEST_DATABASE_URL not set")


@pytest.mark.asyncio
async def test_live_persist_commits_each_op_visible_in_new_session():
    pid = uuid.uuid4()
    uid = uuid.uuid4()
    # 建 user+profile（獨立 session，commit 讓其他 session 看得到）
    async with AsyncSessionLocal() as s:
        s.add_all([User(id=uid, email=f"{uid}@t.co", name="t"),
                   JobProfile(id=pid, user_id=uid, job_title="工程師")])
        await s.commit()
    try:
        live = LiveDbPersist(AsyncSessionLocal)
        await live.set_selected_ocs(pid, "OC1")
        await live.flush_ksa(pid, {"knowledge": [{"content": "設備原理", "source": "catalog", "icap_ref": "K01"}],
                                   "skills": [], "attitudes": []})
        doc = await live.save_document(pid, {"ocs_profile": {"ocs_code": "ENT-001"}})
        assert doc["version"] == 1

        # 用全新 session 讀回 → 證明各操作確實 commit
        async with AsyncSessionLocal() as s:
            prof = await s.get(JobProfile, pid)
            assert prof.selected_ocs_code == "OC1"
            ksa = await KsaRepo(s).hydrate(pid)
            assert ksa["knowledge"][0]["content"] == "設備原理"
            latest = await DocRepo(s).latest(pid)
            assert latest["content"]["ocs_profile"]["ocs_code"] == "ENT-001"
    finally:
        async with AsyncSessionLocal() as s:
            prof = await s.get(JobProfile, pid)
            if prof:
                await s.delete(prof)            # cascade 刪 ksa_items/document_versions
            user = await s.get(User, uid)
            if user:
                await s.delete(user)
            await s.commit()
