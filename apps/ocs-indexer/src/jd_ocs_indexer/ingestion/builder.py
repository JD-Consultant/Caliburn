"""Schema v4 chunk builder: profile + per-task_code records.

Reuses the normalizer's OCS tree. Emits one `profile` record per OCS and one
`task` record per task_code, carrying that task-group's competency_blocks
(nested, K/S sliced per block). The embed string is set on ChunkRecord.text for
the embedder but is NEVER written to payload.
"""

from __future__ import annotations

from dataclasses import dataclass

from jd_ocs_indexer.models.chunk import ChunkRecord, Pair
from jd_ocs_indexer.ingestion.normalizer import NormalizedBlock, NormalizedOCS, NormalizedUnit
from jd_ocs_indexer.ingestion.payloads import (
    CodeName,
    CompetencyBlock,
    Indicator,
    OcsName,
    ProfilePayload,
    TaskPayload,
)


@dataclass
class BuildContext:
    source_file: str
    indexed_at: str


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


def _code_names(pairs: list[Pair]) -> list[CodeName]:
    return [CodeName(code=p.code, name=p.name) for p in pairs]


def _profile_record(norm: NormalizedOCS, ctx: BuildContext) -> ChunkRecord:
    payload = ProfilePayload(
        ocs_code=norm.ocs_code,
        ocs_code_base=norm.ocs_code_base,
        is_current=norm.is_current,
        ocs_name=OcsName(job_category_name=norm.job_category, occupation_name=norm.job_title),
        job_description=norm.job_description,
        ocs_level=norm.ocs_level,
        job_categories=_code_names(norm.job_category_pairs),
        occupations=_code_names(norm.occupation_pairs),
        industries=_code_names(norm.industry_pairs),
        attitudes=_code_names(norm.attitude_pairs),
        prerequisites=list(norm.prerequisites),
        supplements=list(norm.supplements),
        indexed_at=ctx.indexed_at,
        source_file=ctx.source_file,
    ).model_dump()
    return ChunkRecord(
        chunk_key=f"ocs:{norm.ocs_code}:profile",
        chunk_level="profile",
        text=_profile_embed_text(norm),
        payload=payload,
    )


def _block_payload(b: NormalizedBlock) -> CompetencyBlock:
    return CompetencyBlock(
        competency_level=b.competency_level,
        indicators=[Indicator(code=p.code, text=p.name) for p in b.evidence],
        outputs=_code_names(b.output_pairs),
        knowledge=_code_names(b.k_pairs),
        skills=_code_names(b.s_pairs),
    )


def _embed_activities(blocks: list[CompetencyBlock]) -> list[str]:
    """Indicator texts (deduped) — embed signal only, never stored in payload."""
    out: list[str] = []
    seen: set[str] = set()
    for b in blocks:
        for ind in b.indicators:
            if ind.text and ind.text not in seen:
                seen.add(ind.text)
                out.append(ind.text)
    return out


def _task_record(norm: NormalizedOCS, unit: NormalizedUnit, task: Pair,
                 blocks: list[CompetencyBlock], ctx: BuildContext) -> ChunkRecord:
    payload = TaskPayload(
        ocs_code=norm.ocs_code,
        ocs_name=norm.job_title,
        ocu_code=unit.unit_id,
        ocu_name=unit.unit_title,
        task_code=task.code,
        task_name=task.name,
        competency_blocks=blocks,
        source_file=ctx.source_file,
    ).model_dump()
    embed_parts = [task.name, *_embed_activities(blocks)]
    return ChunkRecord(
        chunk_key=f"ocs:{norm.ocs_code}:task:{task.code}",
        chunk_level="task",
        text="\n".join(part for part in embed_parts if part and part.strip()),
        payload=payload,
    )


def build(norm: NormalizedOCS, ctx: BuildContext) -> list[ChunkRecord]:
    records: list[ChunkRecord] = [_profile_record(norm, ctx)]
    for unit in norm.units:
        for group in unit.task_groups:
            blocks = [_block_payload(b) for b in group.blocks]
            for task in group.tasks:
                records.append(_task_record(norm, unit, task, blocks, ctx))
    return records
