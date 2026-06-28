"""Stateless orchestration over Qdrant + embedder for the HTTP API.

Pure-sync functions; routes wrap blocking calls in a threadpool. No FastAPI
imports here so the layer stays unit-testable with fakes.
"""

from __future__ import annotations

import numpy as np

from jd_ocs_indexer.api import urn
from jd_ocs_indexer.embeddings.base import assert_compatible
from jd_ocs_indexer.store.manifest import read_manifest
from jd_ocs_indexer.validation import search as search_mod
from jd_ocs_indexer.validation import stats as stats_mod
from qdrant_client.http import models


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


def _profile_point(client, collection, ocs_code):
    flt = models.Filter(must=[
        models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)),
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="profile")),
    ])
    recs, _ = client.scroll(collection_name=collection, scroll_filter=flt,
                            with_payload=True, with_vectors=False, limit=1)
    return (recs[0].payload or {}) if recs else None


def _resolve_ocs_name(profile_payload: dict) -> str:
    n = profile_payload.get("ocs_name") or {}
    return n.get("occupation_name") or n.get("job_category_name") or profile_payload.get("ocs_code", "")


def _task_points(client, collection, ocs_code):
    flt = models.Filter(must=[
        models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)),
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="task")),
    ])
    return _scroll_all(client, collection, flt)


def get_occupation_tasks(client, collection: str, *, ocs_code: str) -> dict | None:
    prof = _profile_point(client, collection, ocs_code)
    if prof is None:
        return None
    units: dict[str, dict] = {}
    for p in _task_points(client, collection, ocs_code):
        uc = p.get("ocu_code")
        u = units.setdefault(uc, {"ocu_code": uc, "ocu_name": p.get("ocu_name"),
                                  "urn": urn.unit_urn(ocs_code, uc or ""), "tasks": []})
        u["tasks"].append({"task_code": p.get("task_code"), "task_name": p.get("task_name"),
                           "urn": urn.task_urn(ocs_code, p.get("task_code") or "")})
    for u in units.values():
        u["tasks"].sort(key=lambda t: (t["task_code"] is None, t["task_code"] or ""))
    units_sorted = sorted(units.values(), key=lambda u: (u["ocu_code"] is None, u["ocu_code"] or ""))
    return {"ocs_code": ocs_code, "ocs_name": _resolve_ocs_name(prof), "units": units_sorted}


def get_competencies(client, collection: str, *, ocs_code: str) -> dict | None:
    prof = _profile_point(client, collection, ocs_code)
    if prof is None:
        return None
    ocs_name = _resolve_ocs_name(prof)
    buckets: dict[str, dict[str, dict]] = {"K": {}, "S": {}, "O": {}, "P": {}}
    for p in _task_points(client, collection, ocs_code):
        for blk in (p.get("competency_blocks") or []):
            src = {"ocu_code": p.get("ocu_code"), "ocu_name": p.get("ocu_name"),
                   "task_code": p.get("task_code"), "task_name": p.get("task_name"),
                   "competency_level": blk.get("competency_level")}
            for type_, field, val_key in (("K", "knowledge", "name"), ("S", "skills", "name"),
                                          ("O", "outputs", "name"), ("P", "indicators", "text")):
                for it in (blk.get(field) or []):
                    code = it.get("code")
                    if not code:
                        continue
                    key = urn.item_urn(ocs_code, type_, code)
                    item = buckets[type_].get(key)
                    if item is None:
                        item = {"id": key, "type": type_, "code": code,
                                "name": it.get("name"), "text": it.get("text"),
                                "ocs_code": ocs_code, "ocs_name": ocs_name, "sources": []}
                        buckets[type_][key] = item
                    item["sources"].append(src)
    attitudes = [{"id": urn.item_urn(ocs_code, "A", a.get("code", "")), "type": "A",
                  "code": a.get("code", ""), "name": a.get("name"), "text": None,
                  "ocs_code": ocs_code, "ocs_name": ocs_name, "sources": []}
                 for a in (prof.get("attitudes") or []) if a.get("code")]
    return {
        "ocs_code": ocs_code,
        "knowledge": list(buckets["K"].values()), "skills": list(buckets["S"].values()),
        "outputs": list(buckets["O"].values()), "indicators": list(buckets["P"].values()),
        "attitudes": attitudes,
    }


def get_occupation(client, collection: str, *, ocs_code: str) -> dict | None:
    p = _profile_point(client, collection, ocs_code)
    if p is None:
        return None
    return {
        "ocs_code": p.get("ocs_code", ""),
        "urn": urn.occupation_urn(p.get("ocs_code", "")),
        "ocs_name": p.get("ocs_name") or {"job_category_name": None, "occupation_name": None},
        "job_categories": p.get("job_categories") or [],
        "occupations": p.get("occupations") or [],
        "industries": p.get("industries") or [],
        "job_description": p.get("job_description") or "",
        "ocs_level": p.get("ocs_level"),
        "attitudes": p.get("attitudes") or [],
        "prerequisites": p.get("prerequisites") or [],
        "supplements": p.get("supplements") or [],
    }


def _project_task(rec) -> dict:
    p = rec.payload or {}
    return {
        "id": str(getattr(rec, "id", "")),
        "urn": urn.task_urn(p.get("ocs_code", ""), p.get("task_code") or ""),
        "ocs_code": p.get("ocs_code", ""), "ocs_name": p.get("ocs_name") or "",
        "ocu_code": p.get("ocu_code"), "ocu_name": p.get("ocu_name"),
        "task_code": p.get("task_code"), "task_name": p.get("task_name"),
        "competency_blocks": p.get("competency_blocks") or [],
    }


def batch_get_tasks(client, collection: str, *, ids: list[str]) -> dict:
    records = client.retrieve(collection_name=collection, ids=list(ids),
                              with_payload=True, with_vectors=False)
    return {"tasks": [_project_task(r) for r in records]}


def search_tasks(client, embedder, collection: str, *, query: str, top_k: int = 10) -> dict:
    assert_compatible(read_manifest(client, collection), embedder.signature)
    vec = embedder.embed_query(query)
    hits = search_mod.hybrid_search(
        client, collection, vec.dense,
        vec.sparse.indices if vec.sparse else [],
        vec.sparse.values if vec.sparse else [],
        level="task", ocs_code=None, is_current=None, limit=top_k)
    out = []
    for h in hits:
        p = h.payload or {}
        oc = p.get("ocs_code", "")
        out.append({"ocs_code": oc, "ocs_name": p.get("ocs_name") or "",
                    "ocu_code": p.get("ocu_code"), "ocu_name": p.get("ocu_name"),
                    "task_code": p.get("task_code"), "task_name": p.get("task_name"),
                    "urn": urn.task_urn(oc, p.get("task_code") or ""), "score": h.score})
    return {"hits": out}


def search_occupations(client, embedder, collection: str, *, query: str, top_k: int = 10) -> dict:
    assert_compatible(read_manifest(client, collection), embedder.signature)
    vec = embedder.embed_query(query)
    hits = search_mod.hybrid_search(
        client, collection, vec.dense,
        vec.sparse.indices if vec.sparse else [],
        vec.sparse.values if vec.sparse else [],
        level="profile", ocs_code=None, is_current=None, limit=top_k)
    out = []
    for h in hits:
        p = h.payload or {}
        oc = p.get("ocs_code", "")
        out.append({"ocs_code": oc, "urn": urn.occupation_urn(oc),
                    "ocs_name": _resolve_ocs_name(p),
                    "job_description": p.get("job_description") or "",
                    "ocs_level": p.get("ocs_level"), "score": h.score})
    return {"hits": out}


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
    index_model = None
    if qdrant_ok:
        try:
            m = read_manifest(client, collection)
            index_model = f"{m.provider}/{m.model}/{m.dim}" if m else None
        except Exception:
            index_model = None
    return {
        "status": status,
        "model_loaded": model_loaded,
        "qdrant": "reachable" if qdrant_ok else "unreachable",
        "collection": collection,
        "index_model": index_model,
    }


def _pairwise_candidates(tasks: list[dict], threshold: float) -> list[dict]:
    """Brute-force cosine over task vectors → undirected candidate pairs >= threshold.
    `tasks`: [{id, ocs_code, task_code, task_name, vector}]. Small set (selected OCS)."""
    if len(tasks) < 2:
        return []
    mat = np.asarray([t["vector"] for t in tasks], dtype=float)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = mat / norms
    sim = unit @ unit.T
    out: list[dict] = []
    n = len(tasks)
    for i in range(n):
        for j in range(i + 1, n):
            score = float(sim[i, j])
            if score >= threshold:
                out.append({
                    "a": {"urn": urn.task_urn(tasks[i]["ocs_code"], tasks[i]["task_code"]),
                          "ocs_code": tasks[i]["ocs_code"], "task_code": tasks[i]["task_code"],
                          "task_name": tasks[i]["task_name"]},
                    "b": {"urn": urn.task_urn(tasks[j]["ocs_code"], tasks[j]["task_code"]),
                          "ocs_code": tasks[j]["ocs_code"], "task_code": tasks[j]["task_code"],
                          "task_name": tasks[j]["task_name"]},
                    "score": round(score, 4)})
    return out


def find_similar_tasks(client, collection: str, *, ocs_codes: list[str],
                       score_threshold: float = 0.85) -> dict:
    flt = models.Filter(must=[
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="task")),
        models.FieldCondition(key="ocs_code", match=models.MatchAny(any=list(ocs_codes))),
    ])
    tasks: list[dict] = []
    offset = None
    while True:
        records, offset = client.scroll(
            collection_name=collection, scroll_filter=flt,
            with_payload=True, with_vectors=True, limit=256, offset=offset)
        for r in records:
            p = r.payload or {}
            vec = r.vector
            if isinstance(vec, dict):           # named vectors → take dense
                vec = vec.get("dense") or next(iter(vec.values()), None)
            if vec is None:
                continue
            tasks.append({"id": str(getattr(r, "id", "")), "ocs_code": p.get("ocs_code", ""),
                          "task_code": p.get("task_code") or "", "task_name": p.get("task_name") or "",
                          "vector": vec})
        if offset is None:
            break
    return {"candidates": _pairwise_candidates(tasks, score_threshold)}
