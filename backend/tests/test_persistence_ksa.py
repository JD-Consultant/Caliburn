import pytest
from uuid import uuid4
from app.models import JobProfile, User, CompanyTask, KsaItem
from app.services.persistence import KsaRepo
from sqlalchemy import select


@pytest.mark.asyncio
async def test_flush_ksa_links_ks_to_task_and_a_global(db_session):
    user = User(email=f"{uuid4()}@x.com", name="n"); db_session.add(user); await db_session.flush()
    prof = JobProfile(user_id=user.id, job_title="工程師"); db_session.add(prof); await db_session.flush()
    t = CompanyTask(job_profile_id=prof.id, task_name="巡檢", indexer_ref={"task_id": "T1"})
    db_session.add(t); await db_session.flush()

    await KsaRepo(db_session).flush(
        prof.id,
        by_task={"T1": {"knowledge": [{"content": "PLC 原理", "source": "catalog", "icap_ref": "K01"}],
                        "skills": [{"content": "故障排除", "source": "company", "icap_ref": None}]}},
        attitudes=[{"content": "細心", "source": "catalog", "icap_ref": "A01"}],
    )
    rows = (await db_session.execute(select(KsaItem).where(KsaItem.job_profile_id == prof.id))).scalars().all()
    by_type = {(r.ksa_type, r.content): r for r in rows}
    assert by_type[("K", "PLC 原理")].task_id == t.id
    assert by_type[("S", "故障排除")].task_id == t.id
    assert by_type[("A", "細心")].task_id is None

    result = await KsaRepo(db_session).hydrate(prof.id)
    assert result["by_task"]["T1"]["knowledge"][0]["content"] == "PLC 原理"
    assert result["by_task"]["T1"]["skills"][0]["content"] == "故障排除"
    assert result["attitudes"][0]["content"] == "細心"
