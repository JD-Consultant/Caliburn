"""AI proposal endpoints (D28).

Stateless, catalog-first, propose-only (these NEVER write the DB — the user applies
a proposal via the existing PATCH). Each endpoint is a thin adapter: load context
(document/provenance/catalog) and delegate to a pure function in ``app/services/ai/``
so the same logic is reusable by a future autonomous interview agent (design §I).

No ``OPENROUTER_API_KEY`` → ``get_llm`` yields ``None`` and endpoints degrade to
catalog-only (no LLM calls, no failing retries).
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.documents import _require_profile, get_knowledge
from app.config import settings
from app.database import get_db
from app.core.ports import LlmPort
from app.adapters.llm_openrouter import OpenRouterLlm
from app.services.ai import clarify as _clarify
from app.services.ai import draft_op as _draft_op
from app.services.ai import extract_tasks as _extract_tasks
from app.services.ai import recommend_ks as _recommend_ks
from app.services.ai import structure_task as _structure_task
from app.services.ai import tasks as _tasks
from app.core.ports import KnowledgeClient
from app.services.knowledge.task_detail import task_competencies
from app.adapters.persistence import DocRepo

logger = logging.getLogger("jobintel")

router = APIRouter(prefix="/ai", tags=["ai"])


def get_llm() -> LlmPort | None:
    """LLM dependency: ``OpenRouterLlm`` if a key is configured, else ``None``."""
    return OpenRouterLlm() if settings.openrouter_api_key else None


async def _catalog_ks(knowledge: KnowledgeClient, ref: dict) -> tuple[list[dict], list[dict], int | None]:
    """Per-task official K/S + competency_level from the v4 competency pool, sliced on
    ``(ocs_code, task_code)`` from provenance. No ref or indexer down → empty lists +
    None level (caller degrades gracefully, never crashes)."""
    if not ref.get("ocs_code") or not ref.get("task_code"):
        return [], [], None
    try:
        pool = await knowledge.competencies(ref["ocs_code"])
    except Exception:
        logger.warning("ai: competencies failed", exc_info=True)
        return [], [], None
    detail = task_competencies(pool, ref["task_code"])
    return detail["knowledge"], detail["skills"], detail["competency_level"]


@router.post("/recommend-ks")
async def recommend_ks_ep(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
    llm: LlmPort | None = Depends(get_llm),
):
    """Propose per-task K/S. With a note + LLM → filtered/ranked catalog with reasons;
    otherwise the full official catalog K/S (source=catalog)."""
    profile_id = body.get("profile_id")
    task_key = body.get("task_key") or ""
    note = body.get("note")
    if not profile_id or not task_key:
        raise HTTPException(status_code=400, detail="profile_id and task_key required")
    pid = UUID(str(profile_id))
    await _require_profile(pid, db)
    latest = await DocRepo(db).latest(pid)
    content = (latest or {}).get("content") or {}
    task = _tasks.find_task(content, task_key)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found in document")
    k_candidates, s_candidates, level = await _catalog_ks(knowledge, _tasks.catalog_ref(task))
    result = await _recommend_ks.recommend_ks(
        task_name=_tasks.task_name(task),
        note=note,
        k_candidates=k_candidates,
        s_candidates=s_candidates,
        llm=llm,
    )
    result["competency_level"] = level
    return result


async def _catalog_op(knowledge: KnowledgeClient, ref: dict) -> tuple[list[str], list[str]]:
    """Per-task official outputs + indicators from the v4 competency pool, sliced on
    ``(ocs_code, task_code)`` from provenance. No ref or indexer down → empty lists
    (caller degrades gracefully)."""
    if not ref.get("ocs_code") or not ref.get("task_code"):
        return [], []
    try:
        pool = await knowledge.competencies(ref["ocs_code"])
    except Exception:
        logger.warning("ai: competencies failed", exc_info=True)
        return [], []
    detail = task_competencies(pool, ref["task_code"])
    return [o["name"] for o in detail["outputs"]], [p["text"] for p in detail["indicators"]]


@router.post("/draft-op")
async def draft_op_ep(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
    llm: LlmPort | None = Depends(get_llm),
):
    """Propose per-task outputs + indicators. With a note + LLM → personalised drafts
    (source=ai); otherwise the official catalog outputs/activity-examples (source=catalog)."""
    profile_id = body.get("profile_id")
    task_key = body.get("task_key") or ""
    note = body.get("note")
    if not profile_id or not task_key:
        raise HTTPException(status_code=400, detail="profile_id and task_key required")
    pid = UUID(str(profile_id))
    await _require_profile(pid, db)
    latest = await DocRepo(db).latest(pid)
    content = (latest or {}).get("content") or {}
    task = _tasks.find_task(content, task_key)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found in document")
    outputs, examples = await _catalog_op(knowledge, _tasks.catalog_ref(task))
    return await _draft_op.draft_op(
        task_name=_tasks.task_name(task),
        note=note,
        outputs_catalog=outputs,
        indicators_catalog=examples,
        llm=llm,
    )


async def _task_candidates(knowledge: KnowledgeClient, ocs_codes: list[str]) -> list[dict]:
    """Flatten the v4 occupation task lists for the given OCS codes into grounding
    candidates ``[{"id": task_code, "title": task_name}]``. Indexer down for a code →
    skip it (caller degrades, never crashes)."""
    if not ocs_codes:
        return []
    out: list[dict] = []
    for code in ocs_codes:
        try:
            occ = await knowledge.occupation_tasks(code)
        except Exception:
            logger.warning("ai: occupation_tasks failed", exc_info=True)
            continue
        out += [{"id": t.task_code, "title": t.task_name} for u in occ.units for t in u.tasks]
    return out


@router.post("/extract-tasks")
async def extract_tasks_ep(
    body: dict = Body(...),
    knowledge: KnowledgeClient = Depends(get_knowledge),
    llm: LlmPort | None = Depends(get_llm),
):
    """Propose which catalog tasks an employee performs from their self-description +
    any clearly-mentioned tasks not in the catalog as custom candidates."""
    intake = body.get("intake") or ""
    ocs_codes = body.get("ocs_codes") or []
    candidates = await _task_candidates(knowledge, ocs_codes)
    return await _extract_tasks.extract_tasks(intake=intake, candidates=candidates, llm=llm)


@router.post("/structure-task")
async def structure_task_ep(
    body: dict = Body(...),
    llm: LlmPort | None = Depends(get_llm),
):
    """Turn a one-line free-text description into a formal 任務名稱 + suggested 職責."""
    description = body.get("description") or ""
    if not description.strip():
        raise HTTPException(status_code=400, detail="description required")
    occupation_context = ", ".join(body.get("ocs_codes") or [])
    return await _structure_task.structure_task(
        description=description,
        occupation_context=occupation_context,
        llm=llm,
    )


@router.post("/clarify")
async def clarify_ep(
    body: dict = Body(...),
    llm: LlmPort | None = Depends(get_llm),
):
    """Ask ONE short follow-up question for a too-thin task note, or ``null`` if the
    note is already sufficient (stable typed contract for the frontend)."""
    task = body.get("task") or ""
    note = body.get("note") or ""
    question = await _clarify.clarify(task=task, note=note, llm=llm)
    return {"question": question}
