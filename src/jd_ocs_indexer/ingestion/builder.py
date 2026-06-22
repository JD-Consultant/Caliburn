"""Schema v3 chunk builder: profile + per-task records.

Reuses the normalizer's OCS tree. Emits one `profile` record per OCS and one
`task` record per task (aggregating that task-group's blocks). The embed string
is set on ChunkRecord.text for the embedder but is NEVER written to payload.
"""

from __future__ import annotations

from dataclasses import dataclass

from jd_ocs_indexer.models.chunk import ChunkRecord, Pair
from jd_ocs_indexer.ingestion.normalizer import (
    NormalizedOCS,
    NormalizedTaskGroup,
    NormalizedUnit,
)

_ACTIVITY_EXAMPLES = 3


@dataclass
class BuildContext:
    source_file: str
    indexed_at: str


def _dedup_pairs(pairs: list[Pair]) -> list[Pair]:
    out: list[Pair] = []
    seen: set[str] = set()
    for p in pairs:
        if p.code not in seen:
            seen.add(p.code)
            out.append(p)
    return out


def _aggregate_group(group: NormalizedTaskGroup) -> dict:
    """Aggregate a task-group's blocks into per-task K/S/output/activities/level."""
    k: list[Pair] = []
    s: list[Pair] = []
    out: list[Pair] = []
    activities: list[str] = []
    levels: list[int] = []
    for b in group.blocks:
        k.extend(b.k_pairs)
        s.extend(b.s_pairs)
        out.extend(b.output_pairs)
        for ev in b.evidence:  # ev.name == activity text
            if ev.name and ev.name not in activities:
                activities.append(ev.name)
        if b.competency_level is not None:
            levels.append(b.competency_level)
    return {
        "k_pairs": _dedup_pairs(k),
        "s_pairs": _dedup_pairs(s),
        "output_pairs": _dedup_pairs(out),
        "activities": activities,
        "competency_level": max(levels) if levels else None,
    }


def _all_skill_names(norm: NormalizedOCS) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for u in norm.units:
        for g in u.task_groups:
            for b in g.blocks:
                for p in (*b.k_pairs, *b.s_pairs):
                    if p.name and p.name not in seen:
                        seen.add(p.name)
                        names.append(p.name)
    return names


def _profile_embed_text(norm: NormalizedOCS) -> str:
    task_titles = [p.name for u in norm.units for g in u.task_groups for p in g.tasks]
    skill_names = _all_skill_names(norm)
    sample_activities: list[str] = []
    for u in norm.units:
        for g in u.task_groups:
            for b in g.blocks:
                for ev in b.evidence:
                    if ev.name and len(sample_activities) < 20:
                        sample_activities.append(ev.name)
    parts = [
        norm.job_title,
        norm.job_description or "",
        ("工作內容：" + "、".join(task_titles)) if task_titles else "",
        ("活動：" + "、".join(sample_activities)) if sample_activities else "",
        ("技能：" + "、".join(skill_names)) if skill_names else "",
    ]
    return "\n".join(part for part in parts if part.strip())


def _profile_record(norm: NormalizedOCS, ctx: BuildContext) -> ChunkRecord:
    payload = {
        "chunk_level": "profile",
        "ocs_code": norm.ocs_code,
        "ocs_code_base": norm.ocs_code_base,
        "job_title": norm.job_title,
        "job_category": norm.job_category,
        "job_category_codes": list(norm.job_category_codes),
        "industry_codes": list(norm.industry_codes),
        "industry_names": list(norm.industry_names),
        "occupation_codes": list(norm.occupation_codes),
        "occupation_names": list(norm.occupation_names),
        "version": norm.version,
        "version_seq": norm.version_seq,
        "is_current": norm.is_current,
        "update_date": norm.update_date,
        "ocs_level": norm.ocs_level,
        "job_description": norm.job_description,
        "all_a_pairs": [{"code": p.code, "name": p.name} for p in norm.attitude_pairs],
        "prerequisites": list(norm.prerequisites),
        "supplements": list(norm.supplements),
        "source_file": ctx.source_file,
        "indexed_at": ctx.indexed_at,
    }
    return ChunkRecord(
        chunk_key=f"ocs:{norm.ocs_code}:profile",
        chunk_level="profile",
        text=_profile_embed_text(norm),
        payload=payload,
    )


def _task_record(norm: NormalizedOCS, unit: NormalizedUnit, task: Pair, agg: dict, ctx: BuildContext) -> ChunkRecord:
    activities = agg["activities"]
    embed_parts = [task.name, *activities]
    payload = {
        "chunk_level": "task",
        "ocs_code": norm.ocs_code,
        "unit_id": unit.unit_id,
        "unit_title": unit.unit_title,
        "task_id": task.code,
        "task_title": task.name,
        "activity_examples": activities[:_ACTIVITY_EXAMPLES],
        "k_pairs": [{"code": p.code, "name": p.name} for p in agg["k_pairs"]],
        "s_pairs": [{"code": p.code, "name": p.name} for p in agg["s_pairs"]],
        "output_pairs": [{"code": p.code, "name": p.name} for p in agg["output_pairs"]],
        "competency_level": agg["competency_level"],
        "source_file": ctx.source_file,
    }
    return ChunkRecord(
        chunk_key=f"ocs:{norm.ocs_code}:unit:{unit.unit_key}:task:{task.code}",
        chunk_level="task",
        text="\n".join(part for part in embed_parts if part and part.strip()),
        payload=payload,
    )


def build(norm: NormalizedOCS, ctx: BuildContext) -> list[ChunkRecord]:
    records: list[ChunkRecord] = [_profile_record(norm, ctx)]
    for unit in norm.units:
        for group in unit.task_groups:
            agg = _aggregate_group(group)
            for task in group.tasks:
                records.append(_task_record(norm, unit, task, agg, ctx))
    return records
