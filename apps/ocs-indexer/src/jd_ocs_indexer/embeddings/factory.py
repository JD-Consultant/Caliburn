"""Embedding service factory — the single construction site for the embedder.

Returns the HTTP adapter to the `apps/embedder` BGE-M3 service (ADR 0012); the
indexer no longer runs torch/FlagEmbedding in-process. `batch_size` is accepted
for call-site compatibility but is handled by the service.
"""
from __future__ import annotations

from jd_ocs_indexer.config import Settings
from jd_ocs_indexer.embeddings.base import EmbeddingService


def make_embedder(settings: Settings, *, batch_size: int | None = None) -> EmbeddingService:
    from jd_ocs_indexer.embeddings.http_embedder import HttpEmbedder

    return HttpEmbedder(settings.embedder_url)
