import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import DocumentVersion, JobProfile
from app.services.document_service import (
    generate_docx,
    generate_pdf,
    generate_xlsx,
    get_ocs_json,
    get_enriched_export_json,
)

logger = logging.getLogger("jobintel")
router = APIRouter(prefix="/documents", tags=["documents"])

MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf":  "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "json": "application/json",
}


@router.post("/{profile_id}/export")
async def export_document(
    profile_id: UUID,
    format: str = "docx",
    db: AsyncSession = Depends(get_db),
):
    if format not in MIME:
        raise HTTPException(status_code=400, detail="format must be docx, pdf, xlsx, or json")

    profile = await db.get(JobProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.stage not in ("ksa", "preview"):
        raise HTTPException(status_code=422, detail="Profile not ready for export (stage must be ksa or preview)")

    profile_data = {
        "job_title":   profile.job_title,
        "department":  profile.department or "",
        "job_summary": profile.job_summary or "",
        "graph_state": profile.graph_state or {},
    }

    try:
        if format == "json":
            export = get_enriched_export_json(profile_data)
            db.add(DocumentVersion(job_profile_id=profile_id, format="json", status="done"))
            ocs_code = (export["ocs_document"].get("ocs_profile") or {}).get("ocs_code") or str(profile_id)
            filename = f"{ocs_code}.json"
            return JSONResponse(
                content=export,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        if format == "docx":
            path = generate_docx(profile_id, profile_data)
        elif format == "pdf":
            path = generate_pdf(profile_id, profile_data)
        else:
            path = generate_xlsx(profile_id, profile_data)

    except Exception as e:
        logger.error("export failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")

    db.add(DocumentVersion(
        job_profile_id=profile_id,
        format=format,
        file_path=str(path),
        status="done",
    ))

    ocs_code = (profile_data["graph_state"].get("ocs_document") or {})
    ocs_code = (ocs_code.get("ocs_profile") or {}).get("ocs_code") or str(profile_id)
    filename = f"{ocs_code}.{format}"
    return FileResponse(path=str(path), media_type=MIME[format], filename=filename)


@router.get("/{profile_id}/preview")
async def get_document_preview(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """回傳 OCS 文件 + 行為指標 + KSA，供預覽頁使用（比完整 profile 輕量）。"""
    profile = await db.get(JobProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    gs = profile.graph_state or {}
    ocs = gs.get("ocs_document")
    if not ocs:
        raise HTTPException(status_code=404, detail="OCS 文件尚未生成")
    return {
        "profile_id": str(profile_id),
        "stage": profile.stage,
        "ocs_document": ocs,
        "behavior_indicators": gs.get("behavior_indicators", []),
        "ksa_items": gs.get("ksa_items", []),
        "extracted_tasks": gs.get("extracted_tasks", []),
    }


@router.post("/{profile_id}/freeze")
async def freeze_document(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """凍結（鎖定）目前的 OCS 文件，並將 profile stage 設為 preview。

    不需要先匯出：直接從 graph_state 取得 ocs_document 建立 frozen JSON 版本。
    """
    from sqlalchemy import select as sa_select

    profile = await db.get(JobProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    gs = dict(profile.graph_state or {})
    ocs_document = gs.get("ocs_document")
    if not ocs_document:
        raise HTTPException(status_code=400, detail="OCS 文件尚未生成，無法定版")

    # 找最新版號（若已有 frozen 版本則遞增）
    ver_result = await db.execute(
        sa_select(DocumentVersion)
        .where(DocumentVersion.job_profile_id == profile_id)
        .order_by(DocumentVersion.version.desc())
        .limit(1)
    )
    latest = ver_result.scalar_one_or_none()
    next_version = (latest.version + 1) if latest else 1

    version = DocumentVersion(
        job_profile_id=profile_id,
        version=next_version,
        format="json",
        content=ocs_document,
        status="frozen",
    )
    db.add(version)
    await db.flush()  # 取得 version.id

    # 寫回 graph_state，標記已定版
    gs["frozen_version_id"] = str(version.id)
    gs["document_frozen"] = True
    gs["current_stage"] = "preview"
    profile.graph_state = gs
    profile.stage = "preview"

    await db.commit()
    return {
        "id": str(version.id),
        "version": next_version,
        "format": "json",
        "status": "frozen",
        "profile_stage": profile.stage,
    }


@router.get("/{profile_id}/versions")
async def list_versions(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.job_profile_id == profile_id)
        .order_by(DocumentVersion.created_at.desc())
    )
    versions = result.scalars().all()
    return [
        {
            "id": str(v.id),
            "format": v.format,
            "status": v.status,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]
