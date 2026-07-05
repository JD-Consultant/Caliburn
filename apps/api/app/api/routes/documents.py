"""REST document endpoints (D27 T3): the OCS document-of-record worktable.

GET/PATCH/finalize over ``document_versions`` (via ``DocRepo``) plus the
knowledge pack aggregation from the knowledge indexer (ADR 0021; the former
task-candidates / header-meta / task-catalogs / document:buildTasks endpoints
were retired with it — web reads the pack and writes via PATCH only). The
PATCH body is the whole OCS document dict (loose; no strict validation on
draft).
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
from app.core.domain import knowledge_pack, ocs_doc
from app.core.ports import KnowledgeClient
from app.adapters.persistence import DocConflictError, DocRepo, ProfileRepo
from app.adapters.interview_repo import InterviewRepo
from app.interview.diff import doc_paths_changed

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
    # 訪談中的人工存檔 → 變動 path 記入 session.human_touched(ADR 0025 provenance;
    # 引擎寫入走內部 repo 不經本 route,故此鉤子天然只記「人」)
    active = await InterviewRepo(db).get_active(profile_id)
    old_content = None
    if active is not None:
        prev = await DocRepo(db).latest(profile_id)
        old_content = (prev or {}).get("content")
    try:
        result = await DocRepo(db).upsert_draft(
            profile_id, body,
            expected_version=expect_version, expected_revision=expect_revision,
        )
        if active is not None:
            paths = doc_paths_changed(old_content, body)
            if paths:
                await InterviewRepo(db).merge_human_touched(active.id, paths)
        return result
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


async def _attach_similarity(pack: dict, knowledge: KnowledgeClient) -> None:
    """相似比對(ADR 0022,enrichment):態度/任務兩池丟 items:match,回應原樣掛
    ``pack.similarity``;失敗不擋池、不丟例外,降級顯式標 ``meta.similarity``。"""
    sim: dict = {}
    items_by_kind = knowledge_pack.similarity_items(pack)
    results = await asyncio.gather(
        *(knowledge.match(kind, items) for kind, items in items_by_kind.items()),
        return_exceptions=True)
    for kind, r in zip(items_by_kind.keys(), results):
        if isinstance(r, BaseException):
            logger.warning("knowledge: match(%s) failed; degrading", kind, exc_info=r)
        else:
            sim[kind] = r.model_dump()
    pack["similarity"] = sim
    pack["meta"]["similarity"] = (
        "ok" if len(sim) == len(items_by_kind) else ("partial" if sim else "unavailable"))


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
    await _attach_similarity(pack, knowledge)
    return pack
