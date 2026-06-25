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
from app.services import header_meta, ocs_doc
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


def _refresh_header(content: dict, profile, code: str) -> dict:
    """Update the document header (ocs_profile) to reflect current occupation."""
    content.setdefault("ocs_profile", {})
    content["ocs_profile"]["ocs_code"] = code
    name = content["ocs_profile"].setdefault(
        "ocs_name", {"job_category_name": None, "occupation_name": ""}
    )
    name["occupation_name"] = profile.job_title
    content["ocs_profile"].setdefault("job_description", profile.job_summary or "")
    return content


@router.get("/{profile_id}/document/export")
async def export_document(profile_id: UUID, db: AsyncSession = Depends(get_db)):
    """唯讀匯出：把最新文件（draft 或 final）組裝成乾淨合法的 OCS JSON（不寫 DB）。"""
    await _require_profile(profile_id, db)
    latest = await DocRepo(db).latest(profile_id)
    if latest is None:
        raise HTTPException(status_code=400, detail="no document to export")
    return ocs_doc.assemble_final(latest["content"])


@router.post("/{profile_id}/occupations")
async def set_occupations(
    profile_id: UUID,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """選職類：設定 selected_ocs_codes（順序=優先度），並把文件表頭刷新成該職類
    （已有 draft 則就地更新表頭，否則建一個只有表頭的 draft）。任務待 curate。"""
    profile = await _require_profile(profile_id, db)
    codes = body.get("ocs_codes") or []
    if not codes:
        raise HTTPException(status_code=400, detail="no ocs_codes provided")
    await ProfileRepo(db).set_selected_ocs(profile_id, codes)
    repo = DocRepo(db)
    prev = await repo.latest(profile_id)
    if prev:
        content = _refresh_header(prev["content"], profile, codes[0])
    else:
        content = ocs_doc.skeleton(
            {"ocs_code": codes[0], "job_title": profile.job_title, "job_summary": profile.job_summary},
            [],
        )
    await repo.upsert_draft(profile_id, content)
    return {"ocs_codes": codes}


@router.get("/{profile_id}/task-candidates")
async def task_candidates(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    """選任務候選：已選職類的所有任務，依職類→職責(unit)分組（含來源），供勾選。"""
    profile = await _require_profile(profile_id, db)
    codes = profile.selected_ocs_codes or []
    if not codes:
        return {"groups": []}
    groups = []
    for code in codes:
        try:
            occ = await knowledge.occupation_tasks(code)
        except Exception:
            logger.warning("task-candidates: occupation_tasks(%s) failed", code, exc_info=True)
            raise HTTPException(status_code=502, detail="indexer unavailable")
        groups.append({
            "ocs_code": occ.ocs_code,
            "ocs_name": occ.ocs_name,
            "units": [
                {
                    "ocu_code": u.ocu_code,
                    "ocu_name": u.ocu_name,
                    "tasks": [
                        {"task_code": t.task_code, "task_name": t.task_name, "urn": t.urn}
                        for t in u.tasks
                    ],
                }
                for u in occ.units
            ],
        })
    return {"groups": groups}


@router.post("/{profile_id}/build-tasks")
async def build_tasks(
    profile_id: UUID,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """用勾選的任務建/更新文件（遞進重編、保留已填）。picked 每筆：
    {ocs_code, unit_id, unit_title, occupation_name, task_code, task_name}。
    unit_title 留白＝cherry-pick（職責名讓使用者自填）。"""
    profile = await _require_profile(profile_id, db)
    picked = body.get("picked") or []
    units_tasks = [
        {
            "task_name": p.get("task_name", ""),
            "unit_id": p.get("unit_id") or "",
            "unit_title": p.get("unit_title") or "",
            "occupation_name": p.get("occupation_name") or "",
            "indexer_ref": {"ocs_code": p.get("ocs_code") or "", "task_code": p.get("task_code") or ""},
        }
        for p in picked
    ]
    codes = profile.selected_ocs_codes or []
    profile_dict = {
        "ocs_code": codes[0] if codes else "",
        "job_title": profile.job_title,
        "job_summary": profile.job_summary,
    }
    prev = await DocRepo(db).latest(profile_id)
    doc = ocs_doc.build_from_picked(profile_dict, units_tasks, prev["content"] if prev else None)
    _refresh_header(doc, profile, codes[0] if codes else "")
    return await DocRepo(db).upsert_draft(profile_id, doc)


@router.get("/{profile_id}/ocs-search")
async def ocs_search(
    profile_id: UUID,
    q: str,
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    """職類層搜尋（seed 用）：回 [{ocs_code, ocs_name}]，依 ocs_code 去重保序。"""
    await _require_profile(profile_id, db)
    if not q.strip():
        return {"hits": []}
    try:
        res = await knowledge.search_occupations(q, top_k=8)
    except Exception:
        logger.warning("ocs-search indexer query failed", exc_info=True)
        raise HTTPException(status_code=502, detail="indexer unavailable")
    seen: dict[str, dict] = {}
    for h in res.hits:
        if h.ocs_code and h.ocs_code not in seen:
            seen[h.ocs_code] = {"ocs_code": h.ocs_code, "ocs_name": h.ocs_name or h.ocs_code}
    return {"hits": list(seen.values())}


@router.get("/{profile_id}/header-meta")
async def get_header_meta(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    """表頭候選池（D29）：逐已選職類取官方 metadata，聯集去重成所屬職類/職業/行業 +
    態度 + notes 候選，並回主基準單值（預設第一順位）。唯讀、不寫文件——前端勾選後
    自行 PATCH 寫入，故重選職類不會洗掉使用者編輯。indexer 掛或某 code 失敗則略過該 code。"""
    profile = await _require_profile(profile_id, db)
    codes = profile.selected_ocs_codes or []
    metas = []
    for code in codes:
        try:
            metas.append(await knowledge.occupation(code))
        except Exception:
            logger.warning("header-meta: occupation(%s) failed; skipping", code, exc_info=True)
    return header_meta.aggregate(metas, primary_code=codes[0] if codes else "")


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
            comp = await knowledge.competencies(code)
            for bucket, items in (
                ("knowledge", comp.knowledge),
                ("skills", comp.skills),
                ("attitudes", comp.attitudes),
            ):
                for it in items:
                    entry = {
                        "code": it.code,
                        "name": it.name or "",
                        "sources": [s.task_code for s in it.sources if s.task_code],
                    }
                    if it.code:
                        buckets[bucket].setdefault(it.code, entry)
                    else:
                        loose[bucket].append(entry)
        return {
            bucket: list(buckets[bucket].values()) + loose[bucket]
            for bucket in ("knowledge", "skills", "attitudes")
        }
    except Exception:
        logger.warning("ksa-pool indexer query failed; returning empty pool", exc_info=True)
        return empty
