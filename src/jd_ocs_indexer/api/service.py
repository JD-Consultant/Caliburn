"""Stateless orchestration over Qdrant + embedder for the HTTP API.

Pure-sync functions; routes wrap blocking calls in a threadpool. No FastAPI
imports here so the layer stays unit-testable with fakes.
"""

from __future__ import annotations

from jd_ocs_indexer.validation import search as search_mod
from jd_ocs_indexer.validation import stats as stats_mod
from qdrant_client.http import models


def _project_hit(hit) -> dict:
    p = hit.payload or {}
    return {
        "id": getattr(hit, "id", None),
        "chunk_level": p.get("chunk_level", ""),
        "ocs_code": p.get("ocs_code", ""),
        "score": hit.score,
        "job_title": p.get("job_title"),
        "job_description": p.get("job_description"),
        "version": p.get("version"),
        "is_current": p.get("is_current"),
        "ocs_level": p.get("ocs_level"),
        "industry_names": p.get("industry_names") or [],
        "occupation_names": p.get("occupation_names") or [],
        "unit_id": p.get("unit_id"),
        "unit_title": p.get("unit_title"),
        "task_id": p.get("task_id"),
        "task_title": p.get("task_title"),
        "competency_level": p.get("competency_level"),
        "activity_examples": p.get("activity_examples") or [],
        "k_pairs": p.get("k_pairs") or [],
        "s_pairs": p.get("s_pairs") or [],
        "output_pairs": p.get("output_pairs") or [],
        "source_file": p.get("source_file"),
    }


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
) -> dict:
    filters = filters or {}
    vec = embedder.embed_query(query)
    kw = dict(level=level, ocs_code=filters.get("ocs_code"), is_current=filters.get("is_current"), limit=top_k)
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
    return {"mode": mode, "level": level, "hits": [_project_hit(h) for h in hits]}


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


def _scroll_records(client, collection: str, flt, *, page: int = 256) -> list:
    out: list = []
    offset = None
    while True:
        records, offset = client.scroll(
            collection_name=collection, scroll_filter=flt,
            with_payload=True, with_vectors=False, limit=page, offset=offset,
        )
        out.extend(records)
        if offset is None:
            break
    return out


def build_task_pool(client, collection: str, *, ocs_codes: list[str], activity_examples: int = 1) -> dict:
    """Round-2 task menu, sourced from v3 task points (one point per task)."""
    prof_flt = models.Filter(must=[
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="profile")),
        models.FieldCondition(key="ocs_code", match=models.MatchAny(any=list(ocs_codes))),
    ])
    job_titles = {
        (r.payload or {}).get("ocs_code"): (r.payload or {}).get("job_title") or ""
        for r in _scroll_records(client, collection, prof_flt)
    }
    task_flt = models.Filter(must=[
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="task")),
        models.FieldCondition(key="ocs_code", match=models.MatchAny(any=list(ocs_codes))),
    ])
    groups: dict[str, dict] = {}
    for r in _scroll_records(client, collection, task_flt):
        p = r.payload or {}
        oc = p.get("ocs_code")
        if oc is None:
            continue
        g = groups.setdefault(oc, {"units": {}})
        ukey = p.get("unit_id")
        u = g["units"].setdefault(ukey, {"unit_id": p.get("unit_id"), "unit_title": p.get("unit_title"), "tasks": []})
        u["tasks"].append({
            "id": getattr(r, "id", None),
            "task_id": p.get("task_id"),
            "task_title": p.get("task_title"),
            "activity_examples": (p.get("activity_examples") or [])[:activity_examples],
        })
    out_groups = []
    for oc in ocs_codes:
        g = groups.get(oc)
        if not g:
            continue
        units_sorted = sorted(g["units"].values(), key=lambda u: (u["unit_id"] is None, u["unit_id"] or ""))
        for u in units_sorted:
            u["tasks"].sort(key=lambda t: (t["task_id"] is None, t["task_id"] or ""))
        out_groups.append({"ocs_code": oc, "job_title": job_titles.get(oc, ""), "units": units_sorted})
    return {"groups": out_groups}


def get_pairs(client, collection: str, *, ocs_code: str) -> dict | None:
    """OCS-wide K/S/output pools (union of task points) + attitudes (profile)."""
    prof_flt = models.Filter(must=[
        models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)),
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="profile")),
    ])
    prof_recs, _ = client.scroll(
        collection_name=collection, scroll_filter=prof_flt,
        with_payload=True, with_vectors=False, limit=1,
    )
    if not prof_recs:
        return None
    pp = prof_recs[0].payload or {}

    task_flt = models.Filter(must=[
        models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)),
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="task")),
    ])
    task_payloads = _scroll_all(client, collection, task_flt)

    def _union(key: str) -> list[dict]:
        out: list[dict] = []
        seen: set = set()
        for p in task_payloads:
            for pair in (p.get(key) or []):
                code = pair.get("code")
                if code not in seen:
                    seen.add(code)
                    out.append(pair)
        return out

    return {
        "ocs_code": ocs_code,
        "job_title": pp.get("job_title") or "",
        "all_k_pairs": _union("k_pairs"),
        "all_s_pairs": _union("s_pairs"),
        "all_a_pairs": pp.get("all_a_pairs") or [],
        "all_output_pairs": _union("output_pairs"),
        "prerequisites": pp.get("prerequisites") or [],
        "supplements": pp.get("supplements") or [],
    }


def _zip_pairs(codes, names) -> list[dict]:
    """Zip parallel code/name arrays into [{code,name}] pairs, tolerating length
    mismatch or one side missing (fill the short side with '')."""
    codes = list(codes or [])
    names = list(names or [])
    n = max(len(codes), len(names))
    return [
        {"code": codes[i] if i < len(codes) else "", "name": names[i] if i < len(names) else ""}
        for i in range(n)
    ]


def get_profile(client, collection: str, *, ocs_code: str) -> dict | None:
    """Profile-metadata projection for the document header (D29): occupation/category/
    industry (with codes) + description + level + attitudes + notes. One profile point,
    pure payload projection — no embedding, no task scroll. None when not found."""
    flt = models.Filter(must=[
        models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)),
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="profile")),
    ])
    recs, _ = client.scroll(
        collection_name=collection, scroll_filter=flt,
        with_payload=True, with_vectors=False, limit=1,
    )
    if not recs:
        return None
    p = recs[0].payload or {}
    jc_codes = list(p.get("job_category_codes") or [])
    return {
        "ocs_code": p.get("ocs_code", ""),
        "job_title": p.get("job_title") or "",
        "job_category": {"code": jc_codes[0] if jc_codes else "", "name": p.get("job_category") or ""},
        "occupations": _zip_pairs(p.get("occupation_codes"), p.get("occupation_names")),
        "industries": _zip_pairs(p.get("industry_codes"), p.get("industry_names")),
        "job_description": p.get("job_description") or "",
        "ocs_level": p.get("ocs_level"),
        "attitudes": p.get("all_a_pairs") or [],
        "prerequisites": p.get("prerequisites") or [],
        "supplements": p.get("supplements") or [],
    }


def _project_task_detail(rec) -> dict:
    p = rec.payload or {}
    return {
        "id": str(getattr(rec, "id", "")),
        "ocs_code": p.get("ocs_code", ""),
        "unit_id": p.get("unit_id"),
        "unit_title": p.get("unit_title"),
        "task_id": p.get("task_id"),
        "task_title": p.get("task_title"),
        "competency_level": p.get("competency_level"),
        "activity_examples": p.get("activity_examples") or [],
        "k_pairs": p.get("k_pairs") or [],
        "s_pairs": p.get("s_pairs") or [],
        "output_pairs": p.get("output_pairs") or [],
    }


def retrieve_tasks(client, collection: str, *, ids: list[str]) -> dict:
    """By-id task retrieve (Step 4 output_pairs + Step 5 unchanged-task K/S shortcut).

    Returns only the points that exist; missing ids are silently dropped.
    """
    records = client.retrieve(
        collection_name=collection, ids=list(ids),
        with_payload=True, with_vectors=False,
    )
    return {"tasks": [_project_task_detail(r) for r in records]}


def get_stats(client, collection: str) -> dict:
    c = stats_mod.collection_stats(client, collection)
    return {"collection": c.name, "total_points": c.total_points, "by_level": c.by_level}


def healthcheck(client, embedder, collection: str) -> dict:
    model_loaded = embedder is not None
    qdrant_ok = True
    try:
        client.get_collections()
    except Exception:
        qdrant_ok = False
    status = "ok" if (model_loaded and qdrant_ok) else "degraded"
    return {
        "status": status,
        "model_loaded": model_loaded,
        "qdrant": "reachable" if qdrant_ok else "unreachable",
        "collection": collection,
    }
