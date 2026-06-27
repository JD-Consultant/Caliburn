"""Derive a single task's K/S/O/indicators from an occupation CompetencyPool by
filtering CitableItems on their source task_code. The v4 surface is
resource-oriented (occupation/competencies), so a task is resolved by its
task_code rather than by per-point lookup."""
from __future__ import annotations

from app.services.knowledge.models import CompetencyPool


def _matches(item, task_code: str) -> bool:
    return any(s.task_code == task_code for s in item.sources)


def _level(pool: CompetencyPool, task_code: str) -> int | None:
    """Task competency level = first non-null competency_level on a source whose
    task_code matches (a task's points share one level in the OCS contract)."""
    for bucket in (pool.knowledge, pool.skills, pool.outputs, pool.indicators):
        for it in bucket:
            for s in it.sources:
                if s.task_code == task_code and s.competency_level is not None:
                    return s.competency_level
    return None


def task_competencies(pool: CompetencyPool, task_code: str) -> dict:
    """Per-task slice of the pool. K/S/O → [{code,name}], indicators(P) → [{code,text}];
    competency_level = the task's level (from the matching source)."""
    return {
        "knowledge": [{"code": it.code, "name": it.name or ""}
                      for it in pool.knowledge if _matches(it, task_code)],
        "skills": [{"code": it.code, "name": it.name or ""}
                   for it in pool.skills if _matches(it, task_code)],
        "outputs": [{"code": it.code, "name": it.name or ""}
                    for it in pool.outputs if _matches(it, task_code)],
        "indicators": [{"code": it.code, "text": it.text or ""}
                       for it in pool.indicators if _matches(it, task_code)],
        "competency_level": _level(pool, task_code),
    }
