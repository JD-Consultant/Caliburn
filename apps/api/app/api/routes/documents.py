"""REST document endpoints (D27 T3): the OCS document-of-record worktable.

GET/PATCH/finalize over ``document_versions`` (via ``DocRepo``) plus read-only
task-candidates / header-meta / task-catalogs aggregations from the knowledge
indexer. The PATCH body is the whole OCS document dict (loose; no strict
validation on draft).
"""
import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.api.deps import get_knowledge  # noqa: F401  (re-export; tests override via this name)
from app.database import get_db
from app.models import JobProfile
from app.core.domain import header_meta, knowledge_pack, ocs_doc
from app.core.ports import KnowledgeClient
from app.adapters.persistence import DocConflictError, DocRepo, ProfileRepo
from app.services.ai import tasks as ai_tasks
from app.services.knowledge.task_detail import task_competencies

logger = logging.getLogger("caliburn")

router = APIRouter(prefix="/job-profiles", tags=["documents"])


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
        "revision": 0,
        "status": "none",
        "content": ocs_doc.skeleton(profile_dict, []),
    }


@router.patch("/{profile_id}/document")
async def patch_document(
    profile_id: UUID,
    body: dict = Body(...),
    expect_version: int | None = None,
    expect_revision: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """PATCH 整份 OCS 文件（存草稿）。

    樂觀鎖為 **opt-in**：帶 expect_version + expect_revision 兩者、且與最新列不符 → 409
    ``{"detail": {"code": "version_conflict", "current_version": ..., "current_revision": ...}}``
    （帶當前 token，前端「覆蓋」路徑免多打一次 GET）。**不帶（或只帶一個）= 不守衛**（legacy
    相容現況；web 前端一律帶，未來可能收緊為必帶——ADR 0015 / 2a-minimal spec §2.3）。
    """
    await _require_profile(profile_id, db)
    try:
        return await DocRepo(db).upsert_draft(
            profile_id, body,
            expected_version=expect_version, expected_revision=expect_revision,
        )
    except DocConflictError as e:
        raise HTTPException(status_code=409, detail={
            "code": "version_conflict",
            "current_version": e.current_version,
            "current_revision": e.current_revision,
        })
    except StaleDataError:
        # 應用層檢查通過後、flush 前被搶先的同毫秒競態（version_id_col 的 CAS 兜底）。
        # flush 失敗會讓 session 進入需要 rollback 才能再用的狀態（SQLAlchemy 官方要求）。
        await db.rollback()
        row = await DocRepo(db)._latest_row(profile_id)
        raise HTTPException(status_code=409, detail={
            "code": "version_conflict",
            "current_version": row.version if row else 0,
            "current_revision": row.revision if row else 0,
        })


@router.post("/{profile_id}/document:finalize")
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


@router.put("/{profile_id}/occupations")
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


@router.post("/{profile_id}/document:buildTasks")
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


@router.get("/{profile_id}/knowledge")
async def get_knowledge_pack(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    """知識包(ADR 0021):選職類後一次抓齊——``occupation_details + 12 池 + source_tasks``,
    每個官方值帶 srcs(來源必標)。per-code **並行**抓三資源、**組裝照優先序**(append 序);
    單 code 掛 → 略過 + ``meta.partial=true``(ADR 0018);**全掛 → 502**(沒有 knowledge
    選不了職責/任務,critical)。"""
    profile = await _require_profile(profile_id, db)
    codes = profile.selected_ocs_codes or []
    if not codes:
        pack = knowledge_pack.build_pack([], {}, {}, {})
        pack["meta"] = {"partial": False}
        return pack

    async def fetch_one(code: str):
        return (await knowledge.occupation(code),
                await knowledge.occupation_tasks(code),
                await knowledge.competencies(code))

    results = await asyncio.gather(*(fetch_one(c) for c in codes), return_exceptions=True)
    details, tasks_by, pools_by, ok = {}, {}, {}, []
    for code, r in zip(codes, results):
        if isinstance(r, BaseException):
            logger.warning("knowledge: fetch(%s) failed; skipping", code, exc_info=r)
            continue
        details[code], tasks_by[code], pools_by[code] = r
        ok.append(code)
    if not ok:
        raise HTTPException(status_code=502, detail="indexer unavailable")
    pack = knowledge_pack.build_pack(ok, details, tasks_by, pools_by)
    pack["meta"] = {"partial": len(ok) < len(codes)}
    return pack


@router.get("/{profile_id}/task-catalogs")
async def task_catalogs(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    """批次:文件每任務的官方 catalog（K/S/O/P + level），每個不同 ocs_code 只撈一次池。
    唯讀、note-less、不跑 LLM（ADR 0016）。
    **鍵 = 任務身分 URN**（``ocs:{ocs_code}:T:{task_code}``，scheme 同 indexer api/urn.py，
    由 provenance 組出）——非文件位置碼：結構性編輯（刪/拖/重編）不影響鍵（A1）。
    **enrichment 端點**（ADR 0018）：indexer 某 code 掛 → 略過該 code 的任務並回
    ``meta.partial=true``（缺了仍可手動編輯，不快錯）。"""
    await _require_profile(profile_id, db)
    latest = await DocRepo(db).latest(profile_id)
    content = (latest or {}).get("content") or {}
    pairs: list[tuple[str, str]] = []  # (ocs_code, task_code) — 鍵由 provenance 組，不用位置碼
    for unit in (content.get("ocs_content") or {}).get("ocu_units") or []:
        for task in unit.get("tasks") or []:
            ref = ai_tasks.catalog_ref(task)
            if ref["ocs_code"] and ref["task_code"]:
                pairs.append((ref["ocs_code"], ref["task_code"]))
    pools: dict[str, object | None] = {}
    for ocs_code, _ in pairs:
        if ocs_code not in pools:
            try:
                pools[ocs_code] = await knowledge.competencies(ocs_code)
            except Exception:
                logger.warning("task-catalogs: competencies(%s) failed; skipping", ocs_code, exc_info=True)
                pools[ocs_code] = None
    catalogs: dict[str, dict] = {}
    for ocs_code, task_code in pairs:
        pool = pools.get(ocs_code)
        if pool is None:
            continue
        catalogs[f"ocs:{ocs_code}:T:{task_code}"] = task_competencies(pool, task_code)
    partial = any(pool is None for pool in pools.values())
    return {"catalogs": catalogs, "meta": {"partial": partial}}
