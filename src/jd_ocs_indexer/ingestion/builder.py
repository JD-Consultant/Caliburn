"""Build profile / unit / block ChunkRecords from a NormalizedOCS.

This stage produces chunk text *placeholders* — the renderer fills the actual
Markdown. Payloads are mostly complete here so the renderer can also reach
them when needed.
"""

from __future__ import annotations

import datetime as _dt
from typing import Iterator

from jd_ocs_indexer.models.chunk import ChunkRecord
from jd_ocs_indexer.ingestion.normalizer import (
    NormalizedBlock,
    NormalizedOCS,
    NormalizedTaskGroup,
    NormalizedUnit,
)


CHUNK_KEY_PROFILE = "ocs:{ocs}:profile"
CHUNK_KEY_UNIT = "ocs:{ocs}:unit:{unit}"
CHUNK_KEY_BLOCK = "ocs:{ocs}:unit:{unit}:task:{task}:block:{block}"


def _profile_key(ocs_code: str) -> str:
    return CHUNK_KEY_PROFILE.format(ocs=ocs_code)


def _unit_key(ocs_code: str, unit_key: str) -> str:
    return CHUNK_KEY_UNIT.format(ocs=ocs_code, unit=unit_key)


def _block_key(ocs_code: str, unit_key: str, task_key: str, block_key: str) -> str:
    return CHUNK_KEY_BLOCK.format(
        ocs=ocs_code, unit=unit_key, task=task_key, block=block_key
    )


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


class BuilderContext:
    """Per-file context passed into ChunkBuilder.build."""

    def __init__(
        self,
        *,
        source_root_alias: str,
        source_file: str,
        source_json_hash: str,
        schema_version: str,
        embedding_provider: str,
        indexed_at: str | None = None,
    ) -> None:
        self.source_root_alias = source_root_alias
        self.source_file = source_file
        self.source_json_hash = source_json_hash
        self.schema_version = schema_version
        self.embedding_provider = embedding_provider
        self.indexed_at = indexed_at or _utc_now_iso()


class ChunkBuilder:
    """Builds chunk records and (mostly) complete payloads.

    The renderer is responsible for filling `text` + `chunk_content_hash`
    afterwards.
    """

    def build(self, norm: NormalizedOCS, ctx: BuilderContext) -> list[ChunkRecord]:
        records: list[ChunkRecord] = []
        profile_chunk_key = _profile_key(norm.ocs_code)

        records.append(self._profile_record(norm, ctx, profile_chunk_key))

        for unit in norm.units:
            unit_chunk_key = _unit_key(norm.ocs_code, unit.unit_key)
            records.append(
                self._unit_record(norm, unit, ctx, profile_chunk_key, unit_chunk_key)
            )

            for group in unit.task_groups:
                for block in group.blocks:
                    block_chunk_key = _block_key(
                        norm.ocs_code,
                        unit.unit_key,
                        group.primary_task_key,
                        f"{block.block_order:04d}",
                    )
                    records.append(
                        self._block_record(
                            norm,
                            unit,
                            group,
                            block,
                            ctx,
                            profile_chunk_key,
                            unit_chunk_key,
                            block_chunk_key,
                        )
                    )
        return records

    # ---- profile ----

    def _profile_record(
        self,
        norm: NormalizedOCS,
        ctx: BuilderContext,
        chunk_key: str,
    ) -> ChunkRecord:
        payload = self._base_payload(norm, ctx, chunk_key, "profile")
        payload.update(
            {
                "unit_id": None,
                "unit_title": None,
                "unit_order": None,
                "task_ids": [],
                "task_titles": [],
                "task_orders": [],
                "block_id": None,
                "block_title": None,
                "block_order": None,
                "competency_level": None,
                "indicator_codes": [],
                "output_codes": [],
                "k_codes": [],
                "s_codes": [],
                "knowledge_terms": [],
                "skill_terms": [],
                "work_activity_terms": [],
                "profile_chunk_id": None,
                "unit_chunk_id": None,
                "source_path": "$",
                "source_labels": {},
            }
        )
        return ChunkRecord(
            chunk_key=chunk_key,
            chunk_level="profile",
            text="",  # filled by renderer
            payload=payload,
        )

    # ---- unit ----

    def _unit_record(
        self,
        norm: NormalizedOCS,
        unit: NormalizedUnit,
        ctx: BuilderContext,
        profile_chunk_key: str,
        unit_chunk_key: str,
    ) -> ChunkRecord:
        # Aggregate task ids/titles + K/S over the whole unit.
        task_ids: list[str] = []
        task_titles: list[str] = []
        task_orders: list[int] = []
        k_codes: list[str] = []
        s_codes: list[str] = []
        knowledge_terms: list[str] = []
        skill_terms: list[str] = []
        work_activity_terms: list[str] = []
        levels: list[int] = []

        seen_k: set[str] = set()
        seen_s: set[str] = set()
        seen_kt: set[str] = set()
        seen_st: set[str] = set()

        for group in unit.task_groups:
            for tid, ttl in zip(group.task_ids, group.task_titles or [None] * len(group.task_ids)):
                if tid not in task_ids:
                    task_ids.append(tid)
                if ttl and ttl not in task_titles:
                    task_titles.append(ttl)
            task_orders.extend(group.task_orders)

            for block in group.blocks:
                if block.competency_level is not None:
                    levels.append(block.competency_level)
                for c in block.k_codes:
                    if c not in seen_k:
                        seen_k.add(c)
                        k_codes.append(c)
                for c in block.s_codes:
                    if c not in seen_s:
                        seen_s.add(c)
                        s_codes.append(c)
                for t in block.knowledge_terms:
                    if t not in seen_kt:
                        seen_kt.add(t)
                        knowledge_terms.append(t)
                for t in block.skill_terms:
                    if t not in seen_st:
                        seen_st.add(t)
                        skill_terms.append(t)
                for t in block.indicator_texts:
                    if t and t not in work_activity_terms:
                        work_activity_terms.append(t)

        payload = self._base_payload(norm, ctx, unit_chunk_key, "unit")
        payload.update(
            {
                "unit_id": unit.unit_id,
                "unit_title": unit.unit_title,
                "unit_order": unit.unit_order,
                "task_ids": task_ids,
                "task_titles": task_titles,
                "task_orders": task_orders,
                "block_id": None,
                "block_title": None,
                "block_order": None,
                "competency_level": max(levels) if levels else None,
                "indicator_codes": [],
                "output_codes": [],
                "k_codes": k_codes,
                "s_codes": s_codes,
                "knowledge_terms": knowledge_terms,
                "skill_terms": skill_terms,
                "work_activity_terms": work_activity_terms,
                "profile_chunk_id": profile_chunk_key,
                "unit_chunk_id": None,
                "source_path": f"$.ocs_content.ocu_units[{unit.unit_order - 1}]",
                "source_labels": {"unit": unit.unit_id} if unit.unit_id else {},
            }
        )
        return ChunkRecord(
            chunk_key=unit_chunk_key,
            chunk_level="unit",
            text="",
            payload=payload,
        )

    # ---- block ----

    def _block_record(
        self,
        norm: NormalizedOCS,
        unit: NormalizedUnit,
        group: NormalizedTaskGroup,
        block: NormalizedBlock,
        ctx: BuilderContext,
        profile_chunk_key: str,
        unit_chunk_key: str,
        block_chunk_key: str,
    ) -> ChunkRecord:
        payload = self._base_payload(norm, ctx, block_chunk_key, "block")
        payload.update(
            {
                "unit_id": unit.unit_id,
                "unit_title": unit.unit_title,
                "unit_order": unit.unit_order,
                "task_ids": group.task_ids,
                "task_titles": group.task_titles,
                "task_orders": group.task_orders,
                "block_id": block.block_id,
                "block_title": block.block_title,
                "block_order": block.block_order,
                "competency_level": block.competency_level,
                "indicator_codes": block.indicator_codes,
                "output_codes": block.output_codes,
                "k_codes": block.k_codes,
                "s_codes": block.s_codes,
                "knowledge_terms": block.knowledge_terms,
                "skill_terms": block.skill_terms,
                "work_activity_terms": block.indicator_texts,
                "profile_chunk_id": profile_chunk_key,
                "unit_chunk_id": unit_chunk_key,
                "source_path": (
                    f"$.ocs_content.ocu_units[{unit.unit_order - 1}]"
                    f".tasks[?(@.primary='{group.primary_task_key}')]"
                    f".competency_blocks[{block.block_order - 1}]"
                ),
                "source_labels": {
                    "unit": unit.unit_id,
                    "tasks": group.task_ids,
                    "indicators": block.indicator_codes,
                    "outputs": block.output_codes,
                },
            }
        )
        return ChunkRecord(
            chunk_key=block_chunk_key,
            chunk_level="block",
            text="",
            payload=payload,
        )

    # ---- shared payload ----

    def _base_payload(
        self,
        norm: NormalizedOCS,
        ctx: BuilderContext,
        chunk_key: str,
        chunk_level: str,
    ) -> dict:
        return {
            # Identification
            "chunk_key": chunk_key,
            "chunk_level": chunk_level,
            "schema_version": ctx.schema_version,
            "embedding_provider": ctx.embedding_provider,
            "text_format": "markdown",
            "text": "",  # placeholder, filled by renderer
            # OCS profile
            "ocs_code": norm.ocs_code,
            "ocs_code_base": norm.ocs_code_base,
            "job_title": norm.job_title,
            "job_category": norm.job_category,
            "version": norm.version,
            "version_seq": norm.version_seq,
            "is_current": norm.is_current,
            "update_date": norm.update_date,
            "ocs_level": norm.ocs_level,
            # Category arrays
            "job_category_codes": list(norm.job_category_codes),
            "industry_codes": list(norm.industry_codes),
            "industry_names": list(norm.industry_names),
            "occupation_codes": list(norm.occupation_codes),
            "occupation_names": list(norm.occupation_names),
            # Attitudes (codes are reused across blocks; we store profile-level codes everywhere)
            "attitude_codes": list(norm.attitude_codes),
            # Source trace
            "source_root_alias": ctx.source_root_alias,
            "source_file": ctx.source_file,
            "source_json_hash": ctx.source_json_hash,
            "chunk_content_hash": "",  # filled by renderer
            "indexed_at": ctx.indexed_at,
        }
