"""Markdown renderer for profile / unit / block chunks.

Renderer rules (from CHUNKING.md):
  - Markdown must be self-contained and human-readable.
  - Block chunks must include natural-language work activities, knowledge,
    and skill terms — not just OCS codes.
  - Computes `chunk_content_hash` for each rendered chunk.
"""

from __future__ import annotations

import hashlib

from jd_ocs_indexer.models.chunk import ChunkRecord
from jd_ocs_indexer.ingestion.normalizer import (
    NormalizedBlock,
    NormalizedOCS,
    NormalizedTaskGroup,
    NormalizedUnit,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bullet_list(items: list[str], prefix: str = "- ") -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for it in items:
        if not it:
            continue
        s = it.strip()
        if not s or s in seen:
            continue
        seen.add(s)
        lines.append(f"{prefix}{s}")
    return "\n".join(lines)


def _heading_title(norm: NormalizedOCS) -> str:
    parts = [norm.job_title, f"({norm.ocs_code})"]
    return f"# {' '.join(parts)}"


class MarkdownRenderer:
    """Render all three chunk levels.

    The renderer takes the NormalizedOCS so it can reach context the builder
    flattened into payload (e.g. ocs_level) without re-parsing.
    """

    def render(self, norm: NormalizedOCS, records: list[ChunkRecord]) -> None:
        """Fill `text` and `chunk_content_hash` on each record in-place."""
        # Index records by chunk_level / unit / block for quick lookups
        unit_lookup: dict[str, NormalizedUnit] = {
            f"unit:{u.unit_key}": u for u in norm.units
        }

        for rec in records:
            if rec.chunk_level == "profile":
                text = self._render_profile(norm)
            elif rec.chunk_level == "unit":
                unit_key = rec.payload.get("unit_id") or _extract_unit_key(rec.chunk_key)
                unit = self._find_unit(norm, unit_key)
                text = self._render_unit(norm, unit) if unit else _heading_title(norm)
            else:  # block
                text = self._render_block_from_payload(norm, rec)

            rec.text = text
            rec.payload["text"] = text
            rec.payload["chunk_content_hash"] = _sha256(text)

    # ---- helpers ----

    def _find_unit(self, norm: NormalizedOCS, unit_key: str | None) -> NormalizedUnit | None:
        if not unit_key:
            return None
        for u in norm.units:
            if u.unit_key == unit_key or u.unit_id == unit_key:
                return u
        return None

    # ---- profile ----

    def _render_profile(self, norm: NormalizedOCS) -> str:
        lines: list[str] = [_heading_title(norm)]
        meta: list[str] = []
        if norm.ocs_level is not None:
            meta.append(f"- 職能基準等級：L{norm.ocs_level}")
        if norm.version:
            meta.append(f"- 版本：{norm.version}")
        if norm.job_category:
            meta.append(f"- 職類：{norm.job_category}")
        if norm.industry_names:
            meta.append(f"- 適用產業：{'、'.join(norm.industry_names)}")
        if norm.occupation_names:
            meta.append(f"- 職業：{'、'.join(norm.occupation_names)}")
        if norm.update_date:
            meta.append(f"- 更新日期：{norm.update_date}")
        if meta:
            lines.append("")
            lines.extend(meta)

        if norm.job_description:
            lines.append("")
            lines.append("## 工作描述")
            lines.append(norm.job_description.strip())

        if norm.units:
            lines.append("")
            lines.append("## 主要工作任務")
            unit_lines: list[str] = []
            for u in norm.units:
                label = u.unit_id or f"#{u.unit_order}"
                title = u.unit_title or ""
                unit_lines.append(f"- {label} {title}".rstrip())
            lines.extend(unit_lines)

        # v2: skill cloud — aggregate dedup K-names and S-names from all child
        # blocks. Provides retrieval signal for stage 1 (candidate OCS selection)
        # when user query contains tool-level terms that only appear deep in blocks.
        all_k_names: list[str] = []
        all_s_names: list[str] = []
        seen_k: set[str] = set()
        seen_s: set[str] = set()
        for u in norm.units:
            for g in u.task_groups:
                for b in g.blocks:
                    for p in b.k_pairs:
                        if p.name and p.name not in seen_k:
                            seen_k.add(p.name)
                            all_k_names.append(p.name)
                    for p in b.s_pairs:
                        if p.name and p.name not in seen_s:
                            seen_s.add(p.name)
                            all_s_names.append(p.name)

        if all_k_names:
            lines.append("")
            lines.append("## 核心知識領域")
            lines.append(_bullet_list(all_k_names))

        if all_s_names:
            lines.append("")
            lines.append("## 核心技能")
            lines.append(_bullet_list(all_s_names))

        if norm.attitude_terms:
            lines.append("")
            lines.append("## 態度需求")
            atts = _bullet_list(norm.attitude_terms)
            if atts:
                lines.append(atts)

        if norm.prerequisites:
            lines.append("")
            lines.append("## 任職條件")
            ps = _bullet_list(norm.prerequisites)
            if ps:
                lines.append(ps)

        if norm.supplements:
            lines.append("")
            lines.append("## 補充說明")
            ss = _bullet_list(norm.supplements)
            if ss:
                lines.append(ss)

        return "\n".join(lines).rstrip() + "\n"

    # ---- unit ----

    def _render_unit(self, norm: NormalizedOCS, unit: NormalizedUnit) -> str:
        lines: list[str] = [_heading_title(norm)]

        unit_label = unit.unit_id or f"#{unit.unit_order}"
        unit_title = unit.unit_title or ""
        lines.append("")
        lines.append(f"## 職能單元：{unit_title}".rstrip())
        if unit.unit_id:
            lines.append(f"- 單元代碼：{unit.unit_id}")

        # Tasks
        task_lines: list[str] = []
        for g in unit.task_groups:
            for tid, title in zip(g.task_ids or [None], g.task_titles or [None]):
                if not tid and not title:
                    continue
                label = tid or "-"
                tt = title or ""
                task_lines.append(f"- {label} {tt}".rstrip())
        if task_lines:
            lines.append("")
            lines.append("## 工作任務")
            lines.extend(task_lines)

        # Aggregate K / S / activity terms
        k_terms: list[str] = []
        s_terms: list[str] = []
        activities: list[str] = []
        outputs: list[str] = []
        for g in unit.task_groups:
            for b in g.blocks:
                for t in b.knowledge_terms:
                    if t not in k_terms:
                        k_terms.append(t)
                for t in b.skill_terms:
                    if t not in s_terms:
                        s_terms.append(t)
                for t in b.indicator_texts:
                    if t and t not in activities:
                        activities.append(t)
                for t in b.output_names:
                    if t and t not in outputs:
                        outputs.append(t)

        if activities:
            lines.append("")
            lines.append("## 工作活動")
            lines.append(_bullet_list(activities))

        if outputs:
            lines.append("")
            lines.append("## 工作產出")
            lines.append(_bullet_list(outputs))

        if k_terms:
            lines.append("")
            lines.append("## 涵蓋知識")
            lines.append(_bullet_list(k_terms))

        if s_terms:
            lines.append("")
            lines.append("## 涵蓋技能")
            lines.append(_bullet_list(s_terms))

        return "\n".join(lines).rstrip() + "\n"

    # ---- block ----

    def _render_block_from_payload(self, norm: NormalizedOCS, rec: ChunkRecord) -> str:
        p = rec.payload
        lines: list[str] = [_heading_title(norm)]

        unit_title = p.get("unit_title") or ""
        unit_id = p.get("unit_id") or ""
        if unit_title or unit_id:
            head = f"## 職能單元：{unit_title}".rstrip()
            lines.append("")
            lines.append(head)
            if unit_id:
                lines.append(f"- 單元代碼：{unit_id}")

        task_ids = p.get("task_ids") or []
        task_titles = p.get("task_titles") or []
        if task_ids or task_titles:
            title_text = "、".join([t for t in task_titles if t]) or ""
            id_text = "、".join(task_ids)
            lines.append("")
            lines.append(f"### 工作任務：{title_text}".rstrip())
            if id_text:
                lines.append(f"- 任務代碼：{id_text}")

        # v2: no synthetic block_title — identify block by its order within task
        block_order = p.get("block_order")
        lines.append("")
        if block_order is not None:
            lines.append(f"#### 能力區塊 #{block_order}")
        else:
            lines.append("#### 能力區塊")
        if p.get("competency_level") is not None:
            lines.append(f"- 能力等級：L{p['competency_level']}")

        # v2: render evidence / output / K / S directly from payload pair fields
        # in '(code) name' format — gives LLM a citable atom in the markdown.

        evidence = p.get("evidence") or []
        if evidence:
            lines.append("")
            lines.append("工作活動：")
            for ev in evidence:
                code = ev.get("indicator_code", "")
                text = ev.get("activity_text", "")
                if code and text:
                    lines.append(f"- ({code}) {text}")
                elif text:
                    lines.append(f"- {text}")

        output_pairs = p.get("output_pairs") or []
        if output_pairs:
            lines.append("")
            lines.append("工作產出：")
            for op in output_pairs:
                code = op.get("code", "")
                name = op.get("name", "")
                if code and name:
                    lines.append(f"- ({code}) {name}")
                elif name:
                    lines.append(f"- {name}")

        k_pairs = p.get("k_pairs") or []
        if k_pairs:
            lines.append("")
            lines.append("必備知識：")
            for kp in k_pairs:
                code = kp.get("code", "")
                name = kp.get("name", "")
                if code and name:
                    lines.append(f"- ({code}) {name}")
                elif name:
                    lines.append(f"- {name}")

        s_pairs = p.get("s_pairs") or []
        if s_pairs:
            lines.append("")
            lines.append("必備技能：")
            for sp in s_pairs:
                code = sp.get("code", "")
                name = sp.get("name", "")
                if code and name:
                    lines.append(f"- ({code}) {name}")
                elif name:
                    lines.append(f"- {name}")

        return "\n".join(lines).rstrip() + "\n"


def _extract_unit_key(chunk_key: str) -> str | None:
    # chunk_key shape: ocs:{ocs}:unit:{unit_key}[:...]
    parts = chunk_key.split(":")
    if "unit" in parts:
        i = parts.index("unit")
        if i + 1 < len(parts):
            return parts[i + 1]
    return None
