"""Source-side and Qdrant-side stats."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models

from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.ingestion.reader import OCSJSONReader


@dataclass
class SourceStats:
    files: int = 0
    failed: int = 0
    units: int = 0
    tasks: int = 0
    blocks: int = 0
    missing_version: int = 0
    missing_job_category: int = 0
    multi_task_groups: int = 0
    zero_block_units: int = 0
    empty_attitudes: int = 0
    bad_files: list[tuple[str, str]] = field(default_factory=list)


def source_stats(scan_dir: Path, source_root: Path) -> SourceStats:
    reader = OCSJSONReader(source_root)
    stats = SourceStats()
    for loaded, failed in reader.iter_loaded(scan_dir):
        if failed is not None:
            stats.failed += 1
            stats.bad_files.append((failed.rel_path, failed.error))
            continue
        assert loaded is not None
        stats.files += 1
        norm = normalize(loaded.document)
        if norm.version is None:
            stats.missing_version += 1
        if norm.job_category is None:
            stats.missing_job_category += 1
        if not norm.attitude_codes:
            stats.empty_attitudes += 1
        for u in norm.units:
            stats.units += 1
            unit_block_count = 0
            for g in u.task_groups:
                if len(g.task_ids) > 1:
                    stats.multi_task_groups += 1
                stats.tasks += max(len(g.task_ids), 1)
                unit_block_count += len(g.blocks)
                stats.blocks += len(g.blocks)
            if unit_block_count == 0:
                stats.zero_block_units += 1
    return stats


@dataclass
class CollectionStats:
    name: str
    total_points: int
    by_level: dict[str, int]


def collection_stats(client: QdrantClient, collection: str) -> CollectionStats:
    total = client.count(collection_name=collection, exact=True).count
    by_level: dict[str, int] = {}
    for level in ("profile", "task"):
        n = client.count(
            collection_name=collection,
            exact=True,
            count_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="chunk_level",
                        match=models.MatchValue(value=level),
                    )
                ]
            ),
        ).count
        by_level[level] = n
    return CollectionStats(name=collection, total_points=total, by_level=by_level)
