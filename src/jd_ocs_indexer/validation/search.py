"""User-facing query helpers built on Qdrant primitives.

Layered above `smoke_query`: adds payload-filtered dense search and hybrid
(RRF) fusion of dense + sparse named vectors. `build_filter` is the single
filter constructor shared by the CLI `query` command and the HTTP API.
"""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models

from jd_ocs_indexer.validation.smoke_query import Hit, _to_hit


def build_filter(
    *,
    level: str | None = None,
    ocs_code: str | None = None,
    is_current: bool | None = None,
    k_codes: list[str] | None = None,
    s_codes: list[str] | None = None,
    attitude_codes: list[str] | None = None,
) -> models.Filter | None:
    musts: list[models.Condition] = []
    if level:
        musts.append(models.FieldCondition(key="chunk_level", match=models.MatchValue(value=level)))
    if ocs_code:
        musts.append(models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)))
    if is_current is not None:
        musts.append(models.FieldCondition(key="is_current", match=models.MatchValue(value=is_current)))
    if k_codes:
        musts.append(models.FieldCondition(key="k_codes", match=models.MatchAny(any=list(k_codes))))
    if s_codes:
        musts.append(models.FieldCondition(key="s_codes", match=models.MatchAny(any=list(s_codes))))
    if attitude_codes:
        musts.append(
            models.FieldCondition(key="attitude_codes", match=models.MatchAny(any=list(attitude_codes)))
        )
    return models.Filter(must=musts) if musts else None


def dense_search(
    client: QdrantClient,
    collection: str,
    dense: list[float],
    *,
    level: str | None = None,
    ocs_code: str | None = None,
    is_current: bool | None = None,
    k_codes: list[str] | None = None,
    s_codes: list[str] | None = None,
    attitude_codes: list[str] | None = None,
    limit: int = 10,
) -> list[Hit]:
    flt = build_filter(
        level=level, ocs_code=ocs_code, is_current=is_current,
        k_codes=k_codes, s_codes=s_codes, attitude_codes=attitude_codes,
    )
    results = client.query_points(
        collection_name=collection,
        query=dense,
        using="dense",
        query_filter=flt,
        limit=limit,
        with_payload=True,
    )
    return [_to_hit(p) for p in results.points]


def hybrid_search(
    client: QdrantClient,
    collection: str,
    dense: list[float],
    sparse_indices: list[int],
    sparse_values: list[float],
    *,
    level: str | None = None,
    ocs_code: str | None = None,
    is_current: bool | None = None,
    k_codes: list[str] | None = None,
    s_codes: list[str] | None = None,
    attitude_codes: list[str] | None = None,
    limit: int = 10,
    prefetch_limit: int = 50,
) -> list[Hit]:
    """Reciprocal Rank Fusion of dense + sparse using Qdrant's built-in fusion."""
    flt = build_filter(
        level=level, ocs_code=ocs_code, is_current=is_current,
        k_codes=k_codes, s_codes=s_codes, attitude_codes=attitude_codes,
    )
    prefetch: list[Any] = [
        models.Prefetch(query=dense, using="dense", limit=prefetch_limit, filter=flt),
    ]
    if sparse_indices:
        prefetch.append(
            models.Prefetch(
                query=models.SparseVector(indices=sparse_indices, values=sparse_values),
                using="sparse",
                limit=prefetch_limit,
                filter=flt,
            )
        )
    results = client.query_points(
        collection_name=collection,
        prefetch=prefetch,
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
        with_payload=True,
    )
    return [_to_hit(p) for p in results.points]
