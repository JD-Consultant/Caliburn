"""Stateless orchestration over Qdrant + embedder for the HTTP API.

Pure-sync functions; routes wrap blocking calls in a threadpool. No FastAPI
imports here so the layer stays unit-testable with fakes.
"""

from __future__ import annotations

from jd_ocs_indexer.validation import search as search_mod
from qdrant_client.http import models


def _project_hit(hit, *, include_text: bool, text_lines: int) -> dict:
    p = hit.payload or {}
    # All display fields come from the payload; score is the query-result rank
    # score (not in payload), so it's the one field read off the Hit itself.
    out = {
        "chunk_key": p.get("chunk_key", ""),
        "chunk_level": p.get("chunk_level", ""),
        "ocs_code": p.get("ocs_code", ""),
        "job_title": p.get("job_title", ""),
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


def _scroll_all(client, collection: str, flt, *, page: int = 256) -> list[dict]:
    out: list[dict] = []
    offset = None
    while True:
        records, offset = client.scroll(
            collection_name=collection,
            scroll_filter=flt,
            with_payload=True,
            with_vectors=False,
            limit=page,
            offset=offset,
        )
        out.extend((r.payload or {}) for r in records)
        if offset is None:
            break
    return out


def build_task_pool(client, collection: str, *, ocs_codes: list[str], activity_examples: int = 1) -> dict:
    """Round 2 task menu. Shaped from block chunks (not unit payload) because the
    unit payload's task_ids/task_titles are independently deduped and not safely
    zippable; block chunks carry aligned per-group task arrays + activities."""
    flt = models.Filter(
        must=[
            models.FieldCondition(key="chunk_level", match=models.MatchValue(value="block")),
            models.FieldCondition(key="ocs_code", match=models.MatchAny(any=list(ocs_codes))),
        ]
    )
    payloads = _scroll_all(client, collection, flt)

    groups: dict[str, dict] = {}
    for p in payloads:
        oc = p.get("ocs_code")
        if oc is None:
            continue
        g = groups.setdefault(oc, {"ocs_code": oc, "job_title": p.get("job_title") or "", "units": {}})
        if not g["job_title"] and p.get("job_title"):
            g["job_title"] = p["job_title"]
        uorder = p.get("unit_order")
        # unit_order is authoritative when present; fall back to unit_id otherwise.
        # The builder stamps every block of a unit with that unit's order, so all
        # blocks of one unit agree on the key form (no phantom-duplicate units).
        ukey = ("o", uorder) if uorder is not None else ("i", p.get("unit_id"))
        u = g["units"].setdefault(
            ukey,
            {"unit_id": p.get("unit_id"), "unit_title": p.get("unit_title"), "unit_order": uorder, "tasks": {}},
        )
        task_ids = p.get("task_ids") or []
        task_titles = p.get("task_titles") or []
        activities = p.get("work_activity_terms") or []
        for i, tid in enumerate(task_ids):
            ttl = task_titles[i] if i < len(task_titles) else None
            t = u["tasks"].setdefault(tid, {"task_id": tid, "task_title": ttl, "acts": []})
            if not t["task_title"] and ttl:
                t["task_title"] = ttl
            for a in activities:
                if a and a not in t["acts"]:
                    t["acts"].append(a)

    out_groups = []
    for oc in ocs_codes:
        g = groups.get(oc)
        if not g:
            continue
        units_sorted = sorted(
            g["units"].values(),
            key=lambda u: (u["unit_order"] is None, u["unit_order"] if u["unit_order"] is not None else 0),
        )
        units_out = []
        for u in units_sorted:
            tasks_sorted = sorted(u["tasks"].values(), key=lambda t: t["task_id"])
            units_out.append(
                {
                    "unit_id": u["unit_id"],
                    "unit_title": u["unit_title"],
                    "unit_order": u["unit_order"],
                    "tasks": [
                        {
                            "task_id": t["task_id"],
                            "task_title": t["task_title"],
                            "activity_examples": t["acts"][:activity_examples],
                        }
                        for t in tasks_sorted
                    ],
                }
            )
        out_groups.append({"ocs_code": g["ocs_code"], "job_title": g["job_title"], "units": units_out})
    return {"groups": out_groups}


def get_pairs(client, collection: str, *, ocs_code: str) -> dict | None:
    """Round 4 / gap detection: the OCS-wide K/S/A/output vocabulary pools."""
    flt = models.Filter(
        must=[
            models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)),
            models.FieldCondition(key="chunk_level", match=models.MatchValue(value="profile")),
        ]
    )
    records, _ = client.scroll(
        collection_name=collection,
        scroll_filter=flt,
        with_payload=True,
        with_vectors=False,
        limit=1,
    )
    if not records:
        return None
    p = records[0].payload or {}
    return {
        "ocs_code": ocs_code,
        "job_title": p.get("job_title") or "",
        "all_k_pairs": p.get("all_k_pairs") or [],
        "all_s_pairs": p.get("all_s_pairs") or [],
        "all_a_pairs": p.get("all_a_pairs") or [],
        "all_output_pairs": p.get("all_output_pairs") or [],
    }
