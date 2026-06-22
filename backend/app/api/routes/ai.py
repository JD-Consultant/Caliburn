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
from app.graph_v3.deps import LlmPort
from app.graph_v3.llm import OpenRouterLlm
from app.services.ai import draft_op as _draft_op
from app.services.ai import recommend_ks as _recommend_ks
from app.services.ai import tasks as _tasks
from app.services.knowledge.base import KnowledgeClient
from app.services.persistence import DocRepo

logger = logging.getLogger("jobintel")

router = APIRouter(prefix="/ai", tags=["ai"])


def get_llm() -> LlmPort | None:
    """LLM dependency: ``OpenRouterLlm`` if a key is configured, else ``None``."""
    return OpenRouterLlm() if settings.openrouter_api_key else None


async def _catalog_ks(knowledge: KnowledgeClient, catalog_id: str) -> tuple[list[dict], list[dict]]:
    """Fetch a task's official K/S from the indexer by catalog UUID. Indexer down or
    no id → empty lists (caller degrades gracefully, never crashes)."""
    if not catalog_id:
        return [], []
    try:
        res = await knowledge.tasks_by_id([catalog_id])
    except Exception:
        logger.warning("ai: tasks_by_id failed", exc_info=True)
        return [], []
    k: list[dict] = []
    s: list[dict] = []
    for td in res.tasks:
        k += [{"code": p.code, "name": p.name} for p in td.k_pairs]
        s += [{"code": p.code, "name": p.name} for p in td.s_pairs]
    return k, s


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
    k_candidates, s_candidates = await _catalog_ks(knowledge, _tasks.catalog_id(task))
    return await _recommend_ks.recommend_ks(
        task_name=_tasks.task_name(task),
        note=note,
        k_candidates=k_candidates,
        s_candidates=s_candidates,
        llm=llm,
    )


async def _catalog_op(knowledge: KnowledgeClient, catalog_id: str) -> tuple[list[str], list[str]]:
    """Fetch a task's official outputs + activity examples from the indexer by catalog
    UUID. Indexer down or no id → empty lists (caller degrades gracefully)."""
    if not catalog_id:
        return [], []
    try:
        res = await knowledge.tasks_by_id([catalog_id])
    except Exception:
        logger.warning("ai: tasks_by_id failed", exc_info=True)
        return [], []
    outputs: list[str] = []
    examples: list[str] = []
    for td in res.tasks:
        outputs += [p.name for p in td.output_pairs]
        examples += list(td.activity_examples)
    return outputs, examples


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
    outputs, examples = await _catalog_op(knowledge, _tasks.catalog_id(task))
    return await _draft_op.draft_op(
        task_name=_tasks.task_name(task),
        note=note,
        outputs_catalog=outputs,
        indicators_catalog=examples,
        llm=llm,
    )
