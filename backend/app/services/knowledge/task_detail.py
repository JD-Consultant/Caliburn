"""Derive a single task's K/S/O/indicators from an occupation CompetencyPool by
filtering CitableItems on their source task_code. Replaces the old per-point
tasks_by_id path — the v4 surface exposes no Qdrant point ids to feed batchGet."""
from __future__ import annotations

from app.services.knowledge.models import CompetencyPool


def _matches(item, task_code: str) -> bool:
    return any(s.task_code == task_code for s in item.sources)


def task_competencies(pool: CompetencyPool, task_code: str) -> dict:
    """Per-task slice of the pool. K/S/O → [{code,name}], indicators(P) → [{code,text}]."""
    return {
        "knowledge": [{"code": it.code, "name": it.name or ""}
                      for it in pool.knowledge if _matches(it, task_code)],
        "skills": [{"code": it.code, "name": it.name or ""}
                   for it in pool.skills if _matches(it, task_code)],
        "outputs": [{"code": it.code, "name": it.name or ""}
                    for it in pool.outputs if _matches(it, task_code)],
        "indicators": [{"code": it.code, "text": it.text or ""}
                       for it in pool.indicators if _matches(it, task_code)],
    }
