"""User-facing query helpers built on Qdrant primitives.

Layered above `smoke_query`: smoke_query stays as raw validation; this module
adds payload-filtered dense search and hybrid (RRF) fusion of dense + sparse
named vectors for the `query` CLI command.
"""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models

from jd_ocs_indexer.validation.smoke_query import Hit, _to_hit


def _level_filter(level: str | None, ocs_code: str | None) -> models.Filter | None:
    musts: list[models.Condition] = []
    if level:
        musts.append(
            models.FieldCondition(
                key="chunk_level",
                match=models.MatchValue(value=level),
            )
        )
    if ocs_code:
        musts.append(
            models.FieldCondition(
                key="ocs_code",
                match=models.MatchValue(value=ocs_code),
            )
        )
    return models.Filter(must=musts) if musts else None


def dense_search(
    client: QdrantClient,
    collection: str,
    dense: list[float],
    *,
    level: str | None = None,
    ocs_code: str | None = None,
    limit: int = 10,
) -> list[Hit]:
    results = client.query_points(
        collection_name=collection,
        query=dense,
        using="dense",
        query_filter=_level_filter(level, ocs_code),
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
    limit: int = 10,
    prefetch_limit: int = 50,
) -> list[Hit]:
    """Reciprocal Rank Fusion of dense + sparse using Qdrant's built-in fusion."""
    flt = _level_filter(level, ocs_code)
    prefetch: list[Any] = [
        models.Prefetch(
            query=dense,
            using="dense",
            limit=prefetch_limit,
            filter=flt,
        ),
    ]
    if sparse_indices:
        prefetch.append(
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_indices,
                    values=sparse_values,
                ),
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
