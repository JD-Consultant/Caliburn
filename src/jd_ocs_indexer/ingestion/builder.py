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
