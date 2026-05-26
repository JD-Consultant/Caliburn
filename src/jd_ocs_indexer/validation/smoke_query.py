"""CLI smoke query helpers.

Output shape is not a stable API — it's only used to confirm:
  - count by chunk_level
  - retrieve by ocs_code
  - filter by K/S code
  - dev-only vector probe (dense + sparse)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models


@dataclass
class Hit:
    chunk_key: str
    chunk_level: str
    ocs_code: str
    job_title: str
    score: float | None
    payload: dict


def _to_hit(p: Any) -> Hit:
    payload = p.payload or {}
    return Hit(
        chunk_key=payload.get("chunk_key", ""),
        chunk_level=payload.get("chunk_level", ""),
        ocs_code=payload.get("ocs_code", ""),
        job_title=payload.get("job_title", ""),
        score=getattr(p, "score", None),
        payload=payload,
    )


def retrieve_by_ocs_code(
    client: QdrantClient,
    collection: str,
    ocs_code: str,
    limit: int = 200,
) -> list[Hit]:
    flt = models.Filter(
        must=[
            models.FieldCondition(
                key="ocs_code",
                match=models.MatchValue(value=ocs_code),
            )
        ]
    )
    records, _ = client.scroll(
        collection_name=collection,
        scroll_filter=flt,
        with_payload=True,
        with_vectors=False,
        limit=limit,
    )
    return [_to_hit(r) for r in records]


def filter_by_ks_code(
    client: QdrantClient,
    collection: str,
    *,
    knowledge: list[str] | None = None,
    skill: list[str] | None = None,
    limit: int = 50,
) -> list[Hit]:
    musts: list[models.FieldCondition] = [
        models.FieldCondition(
            key="chunk_level",
            match=models.MatchValue(value="block"),
        )
    ]
    if knowledge:
        musts.append(
            models.FieldCondition(
                key="k_codes",
                match=models.MatchAny(any=list(knowledge)),
            )
        )
    if skill:
        musts.append(
            models.FieldCondition(
                key="s_codes",
                match=models.MatchAny(any=list(skill)),
            )
        )
    flt = models.Filter(must=musts)
    records, _ = client.scroll(
        collection_name=collection,
        scroll_filter=flt,
        with_payload=True,
        with_vectors=False,
        limit=limit,
    )
    return [_to_hit(r) for r in records]


def probe_dense(
    client: QdrantClient,
    collection: str,
    dense: list[float],
    limit: int = 10,
) -> list[Hit]:
    results = client.query_points(
        collection_name=collection,
        query=dense,
        using="dense",
        limit=limit,
        with_payload=True,
    )
    return [_to_hit(p) for p in results.points]


def probe_sparse(
    client: QdrantClient,
    collection: str,
    indices: list[int],
    values: list[float],
    limit: int = 10,
) -> list[Hit]:
    results = client.query_points(
        collection_name=collection,
        query=models.SparseVector(indices=indices, values=values),
        using="sparse",
        limit=limit,
        with_payload=True,
    )
    return [_to_hit(p) for p in results.points]
