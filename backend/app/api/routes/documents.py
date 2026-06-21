"""REST document endpoints (D27 T3): the OCS document-of-record worktable.

GET/PATCH/finalize over ``document_versions`` (via ``DocRepo``) plus a
read-only ``ksa-pool`` aggregation from the knowledge indexer. The PATCH body
is the whole OCS document dict (loose; no strict validation on draft).
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import JobProfile
from app.services import ocs_doc
from app.services.knowledge.base import KnowledgeClient
from app.services.knowledge.http_client import HttpIndexerClient
from app.services.persistence import DocRepo, ProfileRepo

logger = logging.getLogger("jobintel")

router = APIRouter(prefix="/job-profiles", tags=["documents"])


async def get_knowledge():
    client = HttpIndexerClient(
        settings.indexer_base_url, settings.indexer_api_key, settings.indexer_timeout_s
    )
    try:
        yield client
    finally:
        await client.aclose()


async def _require_profile(profile_id: UUID, db: AsyncSession) -> JobProfile:
    profile = await db.get(JobProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Job profile not found")
    return profile


@router.get("/{profile_id}/document")
async def get_document(profile_id: UUID, db: AsyncSession = Depends(get_db)):
    profile = await _require_profile(profile_id, db)
    latest = await DocRepo(db).latest(profile_id)
    if latest is not None:
        return latest
    codes = profile.selected_ocs_codes or []
    profile_dict = {
        "ocs_code": codes[0] if codes else "",
        "job_title": profile.job_title,
        "job_summary": profile.job_summary,
    }
    return {
        "id": None,
        "version": 0,
        "status": "none",
        "content": ocs_doc.skeleton(profile_dict, []),
    }


@router.patch("/{profile_id}/document")
async def patch_document(
    profile_id: UUID,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    await _require_profile(profile_id, db)
    return await DocRepo(db).upsert_draft(profile_id, body)


@router.post("/{profile_id}/document/finalize")
async def finalize_document(profile_id: UUID, db: AsyncSession = Depends(get_db)):
    await _require_profile(profile_id, db)
    repo = DocRepo(db)
    latest = await repo.latest(profile_id)
    if latest is None:
        raise HTTPException(status_code=400, detail="no document to finalize")
    assembled = ocs_doc.assemble_final(latest["content"])
    errs = ocs_doc.validate(assembled)
    if errs:
        raise HTTPException(
            status_code=422, detail={"detail": "invalid document", "errors": errs}
        )
    return await repo.finalize(profile_id, content=assembled)


@router.post("/{profile_id}/seed")
async def seed_document(
    profile_id: UUID,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    profile = await _require_profile(profile_id, db)
    codes = body.get("ocs_codes") or []
    if not codes:
        raise HTTPException(status_code=400, detail="no ocs_codes provided")
    await ProfileRepo(db).set_selected_ocs(profile_id, codes)
    try:
        pool = await knowledge.task_pool(codes)
    except Exception:
        logger.warning("seed: indexer task_pool failed", exc_info=True)
        raise HTTPException(status_code=502, detail="indexer unavailable")
    units_tasks = []
    for g in pool.groups:
        for u in g.units:
            for t in u.tasks:
                units_tasks.append({
                    "task_name": t.task_title,
                    "unit_id": u.unit_id,
                    "unit_title": u.unit_title,
                    "indexer_ref": {"ocs_code": g.ocs_code, "task_id": t.task_id},
                })
    profile_dict = {
        "ocs_code": codes[0],
        "job_title": profile.job_title,
        "job_summary": profile.job_summary,
    }
    doc = ocs_doc.skeleton(profile_dict, units_tasks)
    return await DocRepo(db).upsert_draft(profile_id, doc)


@router.get("/{profile_id}/ocs-search")
async def ocs_search(
    profile_id: UUID,
    q: str,
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    """職類層搜尋（seed 用）：回 [{ocs_code, job_title}]，依 ocs_code 去重保序。"""
    await _require_profile(profile_id, db)
    if not q.strip():
        return {"hits": []}
    try:
        res = await knowledge.search(q, level="profile", top_k=8)
    except Exception:
        logger.warning("ocs-search indexer query failed", exc_info=True)
        raise HTTPException(status_code=502, detail="indexer unavailable")
    seen: dict[str, dict] = {}
    for h in res.hits:
        if h.ocs_code and h.ocs_code not in seen:
            seen[h.ocs_code] = {"ocs_code": h.ocs_code, "job_title": h.job_title or h.ocs_code}
    return {"hits": list(seen.values())}


@router.get("/{profile_id}/ksa-pool")
async def get_ksa_pool(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    profile = await _require_profile(profile_id, db)
    empty = {"knowledge": [], "skills": [], "attitudes": []}
    codes = profile.selected_ocs_codes or []
    if not codes:
        return empty
    try:
        buckets: dict[str, dict[str, dict]] = {
            "knowledge": {},
            "skills": {},
            "attitudes": {},
        }
        loose: dict[str, list[dict]] = {"knowledge": [], "skills": [], "attitudes": []}
        for code in codes:
            pairs = await knowledge.pairs(code)
            for bucket, items in (
                ("knowledge", pairs.knowledge),
                ("skills", pairs.skills),
                ("attitudes", pairs.attitudes),
            ):
                for pair in items:
                    entry = {"code": pair.code, "name": pair.name}
                    if pair.code:
                        buckets[bucket].setdefault(pair.code, entry)
                    else:
                        loose[bucket].append(entry)
        return {
            bucket: list(buckets[bucket].values()) + loose[bucket]
            for bucket in ("knowledge", "skills", "attitudes")
        }
    except Exception:
        logger.warning("ksa-pool indexer query failed; returning empty pool", exc_info=True)
        return empty
