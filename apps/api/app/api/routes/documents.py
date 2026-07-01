"""REST document endpoints (D27 T3): the OCS document-of-record worktable.

GET/PATCH/finalize over ``document_versions`` (via ``DocRepo``) plus read-only
task-candidates / header-meta / task-catalogs aggregations from the knowledge
indexer. The PATCH body is the whole OCS document dict (loose; no strict
validation on draft).
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import JobProfile
from app.core.domain import header_meta, ocs_doc
from app.core.ports import KnowledgeClient
from app.adapters.knowledge_http import HttpIndexerClient
from app.adapters.persistence import DocRepo, ProfileRepo
from app.services.ai import tasks as ai_tasks
from app.services.knowledge.task_detail import task_competencies

logger = logging.getLogger("caliburn")

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


def _refresh_header(content: dict, profile, code: str, primary=None) -> dict:
    """Update the document header (ocs_profile) to reflect current occupation.
    With ``primary`` (indexer OccupationDetail) fill the OFFICIAL 職業名/職類名
    (same as the 職能基準代碼 picker / setPrimaryBasis). Without it (indexer down)
    leave the name EMPTY — never fall back to the user's job_title."""
    content.setdefault("ocs_profile", {})
    p = content["ocs_profile"]
    p["ocs_code"] = code
    name = p.setdefault("ocs_name", {"job_category_name": None, "occupation_name": ""})
    if primary is not None:
        name["occupation_name"] = primary.ocs_name.occupation_name or ""
        name["job_category_name"] = primary.ocs_name.job_category_name
    else:
        name["occupation_name"] = ""
        name["job_category_name"] = None
    p.setdefault("job_description", profile.job_summary or "")
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
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    """選職類：設定 selected_ocs_codes（順序=優先度），並把文件表頭刷新成該職類的
    官方主基準（職業名/職類名）。已有 draft 則就地更新表頭，否則建一個只有表頭的
    draft。indexer 掛則表頭名稱留空（不退回 job_title）。任務待 curate。"""
    profile = await _require_profile(profile_id, db)
    codes = body.get("ocs_codes") or []
    if not codes:
        raise HTTPException(status_code=400, detail="no ocs_codes provided")
    await ProfileRepo(db).set_selected_ocs(profile_id, codes)
    # 官方主基準（第一順位）→ 表頭職業名/職類名填官方值（同 setPrimaryBasis）。
    primary = None
    try:
        primary = await knowledge.occupation(codes[0])
    except Exception:
        logger.warning("set_occupations: occupation(%s) failed; header name left blank", codes[0], exc_info=True)
    repo = DocRepo(db)
    prev = await repo.latest(profile_id)
    if prev:
        content = _refresh_header(prev["content"], profile, codes[0], primary)
    else:
        content = ocs_doc.skeleton(
            {"ocs_code": codes[0], "job_title": profile.job_title, "job_summary": profile.job_summary},
            [],
        )
        content = _refresh_header(content, profile, codes[0], primary)
    await repo.upsert_draft(profile_id, content)
    return {"ocs_codes": codes}


@router.get("/{profile_id}/task-candidates")
async def task_candidates(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    """選任務候選：已選職類的所有任務，依職類→職責(unit)分組（含來源），供勾選。
    **critical 端點**（ADR 0018）：沒有候選清單就選不了任務，主流程斷 → indexer 掛回 502 快錯。"""
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
    """用勾選的任務建/更新文件（遞進重編、保留已填）。picked 每筆（v4 PickedTask）：
    {ocs_code, ocu_code, ocu_name, ocs_name, task_code, task_name}。
    ocu_name 留白＝cherry-pick（職責名讓使用者自填）。"""
    profile = await _require_profile(profile_id, db)
    picked = body.get("picked") or []
    units_tasks = [
        {
            "task_name": p.get("task_name", ""),
            "unit_id": p.get("ocu_code") or "",
            "unit_title": p.get("ocu_name") or "",
            "occupation_name": p.get("ocs_name") or "",
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
    """職類層搜尋（seed 用）：回 [{ocs_code, ocs_name}]，依 ocs_code 去重保序。
    **critical 端點**（ADR 0018）：空搜尋結果會被誤解成「查無此職類」→ indexer 掛回 502 快錯。"""
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
    自行 PATCH 寫入，故重選職類不會洗掉使用者編輯。
    **enrichment 端點**（ADR 0018）：indexer 掛/某 code 失敗則略過該 code 並回
    ``meta.partial=true``（缺了仍可手動編輯，不快錯）。"""
    profile = await _require_profile(profile_id, db)
    codes = profile.selected_ocs_codes or []
    metas = []
    partial = False
    for code in codes:
        try:
            metas.append(await knowledge.occupation(code))
        except Exception:
            partial = True
            logger.warning("header-meta: occupation(%s) failed; skipping", code, exc_info=True)
    result = header_meta.aggregate(metas, primary_code=codes[0] if codes else "")
    result["meta"] = {"partial": partial}
    return result


@router.get("/{profile_id}/task-catalogs")
async def task_catalogs(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    """批次:文件每任務的官方 catalog（K/S/O/P + level），每個不同 ocs_code 只撈一次池。
    唯讀、note-less、不跑 LLM（ADR 0016）。
    **enrichment 端點**（ADR 0018）：indexer 某 code 掛 → 略過該 code 的任務並回
    ``meta.partial=true``（缺了仍可手動編輯，不快錯）。"""
    await _require_profile(profile_id, db)
    latest = await DocRepo(db).latest(profile_id)
    content = (latest or {}).get("content") or {}
    triples: list[tuple[str, str, str]] = []  # (task_key, ocs_code, task_code)
    for unit in (content.get("ocs_content") or {}).get("ocu_units") or []:
        for task in unit.get("tasks") or []:
            tcs = task.get("task_codes") or []
            tk = tcs[0].get("code") if tcs and isinstance(tcs[0], dict) else ""
            ref = ai_tasks.catalog_ref(task)
            if tk and ref["ocs_code"] and ref["task_code"]:
                triples.append((tk, ref["ocs_code"], ref["task_code"]))
    pools: dict[str, object | None] = {}
    for _, ocs_code, _ in triples:
        if ocs_code not in pools:
            try:
                pools[ocs_code] = await knowledge.competencies(ocs_code)
            except Exception:
                logger.warning("task-catalogs: competencies(%s) failed; skipping", ocs_code, exc_info=True)
                pools[ocs_code] = None
    catalogs: dict[str, dict] = {}
    for tk, ocs_code, task_code in triples:
        pool = pools.get(ocs_code)
        if pool is None:
            continue
        catalogs[tk] = task_competencies(pool, task_code)
    partial = any(pool is None for pool in pools.values())
    return {"catalogs": catalogs, "meta": {"partial": partial}}
