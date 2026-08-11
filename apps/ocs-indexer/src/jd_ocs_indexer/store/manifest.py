"""Embedding-identity manifest: one reserved point per collection.

Stored as a single point (fixed id) with payload chunk_level="_manifest" so it is
naturally excluded from profile/task searches. Single source of truth for "which
embedder built this index"; read it to validate compatibility before querying.
"""
from __future__ import annotations

from datetime import datetime, timezone

from qdrant_client.http import models

from jd_ocs_indexer.embeddings.base import EmbeddingSignature

MANIFEST_POINT_ID = "00000000-0000-0000-0000-0000000a11fe"  # reserved sentinel
MANIFEST_LEVEL = "_manifest"


def write_manifest(client, collection: str, sig: EmbeddingSignature, *, built_at: str | None = None) -> None:
    payload = {
        "chunk_level": MANIFEST_LEVEL,
        "built_at": built_at or datetime.now(timezone.utc).isoformat(),
        "embedding": {"provider": sig.provider, "model": sig.model, "dim": sig.dim, "revision": sig.revision},
    }
    client.upsert(
        collection_name=collection,
        wait=True,
        points=[models.PointStruct(id=MANIFEST_POINT_ID, vector={"dense": [0.0] * sig.dim}, payload=payload)],
    )


def read_manifest(client, collection: str) -> EmbeddingSignature | None:
    recs = client.retrieve(
        collection_name=collection, ids=[MANIFEST_POINT_ID], with_payload=True, with_vectors=False
    )
    if not recs:
        return None
    emb = (recs[0].payload or {}).get("embedding") or {}
    if not emb:
        return None
    return EmbeddingSignature(
        provider=emb.get("provider", ""),
        model=emb.get("model", ""),
        dim=int(emb.get("dim", 0)),
        revision=int(emb.get("revision", 0)),
    )
