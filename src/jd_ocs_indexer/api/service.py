"""Stateless orchestration over Qdrant + embedder for the HTTP API.

Pure-sync functions; routes wrap blocking calls in a threadpool. No FastAPI
imports here so the layer stays unit-testable with fakes.
"""

from __future__ import annotations

from jd_ocs_indexer.validation import search as search_mod


def _project_hit(hit, *, include_text: bool, text_lines: int) -> dict:
    p = hit.payload or {}
    out = {
        "chunk_key": hit.chunk_key,
        "chunk_level": hit.chunk_level,
        "ocs_code": hit.ocs_code,
        "job_title": hit.job_title,
        "score": hit.score,
        "version": p.get("version"),
        "is_current": p.get("is_current"),
        "ocs_level": p.get("ocs_level"),
        "competency_level": p.get("competency_level"),
        "unit_id": p.get("unit_id"),
        "unit_title": p.get("unit_title"),
        "unit_order": p.get("unit_order"),
        "task_ids": p.get("task_ids") or [],
        "task_titles": p.get("task_titles") or [],
        "block_order": p.get("block_order"),
        "k_pairs": p.get("k_pairs") or [],
        "s_pairs": p.get("s_pairs") or [],
        "industry_names": p.get("industry_names") or [],
        "occupation_names": p.get("occupation_names") or [],
        "source_file": p.get("source_file"),
        "snippet": None,
    }
    if include_text and text_lines > 0:
        body = (p.get("text") or "").strip().splitlines()
        lines = [ln for ln in body[1:] if ln.strip()][:text_lines]
        out["snippet"] = "\n".join(lines) if lines else None
    return out


def search(
    client,
    embedder,
    collection: str,
    *,
    query: str,
    level: str | None = None,
    hybrid: bool = True,
    top_k: int = 10,
    filters: dict | None = None,
    include_text: bool = False,
    text_lines: int = 6,
) -> dict:
    filters = filters or {}
    vec = embedder.embed_query(query)
    kw = dict(
        level=level,
        ocs_code=filters.get("ocs_code"),
        is_current=filters.get("is_current"),
        k_codes=filters.get("k_codes"),
        s_codes=filters.get("s_codes"),
        attitude_codes=filters.get("attitude_codes"),
        limit=top_k,
    )
    if hybrid:
        hits = search_mod.hybrid_search(
            client, collection, vec.dense,
            vec.sparse.indices if vec.sparse else [],
            vec.sparse.values if vec.sparse else [],
            **kw,
        )
        mode = "hybrid"
    else:
        hits = search_mod.dense_search(client, collection, vec.dense, **kw)
        mode = "dense"
    return {
        "mode": mode,
        "level": level,
        "hits": [_project_hit(h, include_text=include_text, text_lines=text_lines) for h in hits],
    }
