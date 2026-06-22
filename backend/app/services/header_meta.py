"""Document-header metadata aggregation (D29 V1).

Pure functions over a list of indexer ``ProfileMeta`` (one per selected OCS).
Produces the candidate pools for the header pickers (所屬職類/職業/行業 + 態度)
and the single-value 主基準 fields. The frontend ticks candidates and writes the
result into ``ocs_profile.category`` / ``notes`` / ``ocs_attitude`` via PATCH —
this module NEVER writes the document, so re-selecting occupations can never wipe
a user's edits (the document is only mutated by an explicit user PATCH).

Multi-OCS rules (防雷):
- candidates deduped by ``code`` (fall back to ``name`` when code is empty), so two
  occupations sharing e.g. industry "A" never produce a duplicate row.
- first-seen order preserved.
- each candidate records the ``sources`` (ocs_codes) that contributed it, so the
  frontend can drop a candidate only when the *last* contributing OCS is removed.
"""
from __future__ import annotations

from app.services.knowledge.models import Pair, ProfileMeta


def _merge_pairs(acc: list[dict], pairs: list[Pair], source: str) -> None:
    """Union ``pairs`` into ``acc`` (list of {code,name,sources}) deduped by code|name."""
    for p in pairs:
        key = (p.code or "").strip() or ("name:" + (p.name or "").strip())
        if not key.strip() or key == "name:":
            continue
        existing = next((x for x in acc if x["_key"] == key), None)
        if existing is None:
            acc.append({"_key": key, "code": p.code or "", "name": p.name or "", "sources": [source]})
        elif source not in existing["sources"]:
            existing["sources"].append(source)


def _merge_texts(acc: list[dict], texts: list[str], source: str) -> None:
    for t in texts:
        key = (t or "").strip()
        if not key:
            continue
        existing = next((x for x in acc if x["text"] == key), None)
        if existing is None:
            acc.append({"text": key, "sources": [source]})
        elif source not in existing["sources"]:
            existing["sources"].append(source)


def _strip(items: list[dict]) -> list[dict]:
    return [{k: v for k, v in x.items() if k != "_key"} for x in items]


def aggregate(metas: list[ProfileMeta], primary_code: str = "") -> dict:
    """Aggregate per-OCS metadata into header candidate pools + 主基準 single values."""
    job_categories: list[dict] = []
    occupations: list[dict] = []
    industries: list[dict] = []
    attitudes: list[dict] = []
    prerequisites: list[dict] = []
    supplements: list[dict] = []

    by_code = {m.ocs_code: m for m in metas}

    for m in metas:
        src = m.ocs_code
        if m.job_category and (m.job_category.code or m.job_category.name):
            _merge_pairs(job_categories, [m.job_category], src)
        _merge_pairs(occupations, m.occupations, src)
        _merge_pairs(industries, m.industries, src)
        _merge_pairs(attitudes, m.attitudes, src)
        _merge_texts(prerequisites, m.prerequisites, src)
        _merge_texts(supplements, m.supplements, src)

    # 主基準：default = primary_code (codes[0]); fall back to first meta.
    primary = by_code.get(primary_code) or (metas[0] if metas else None)
    primary_out = {
        "ocs_code": primary.ocs_code if primary else "",
        "occupation_name": primary.job_title if primary else "",
        "job_category_name": (primary.job_category.name if primary and primary.job_category else "") or "",
        "job_description": primary.job_description if primary else "",
        "ocs_level": primary.ocs_level if primary else None,
    }

    return {
        "primary": primary_out,
        "primary_options": [{"ocs_code": m.ocs_code, "occupation_name": m.job_title} for m in metas],
        "job_categories": _strip(job_categories),
        "occupations": _strip(occupations),
        "industries": _strip(industries),
        "attitudes": _strip(attitudes),
        "prerequisites": _strip(prerequisites),
        "supplements": _strip(supplements),
    }
