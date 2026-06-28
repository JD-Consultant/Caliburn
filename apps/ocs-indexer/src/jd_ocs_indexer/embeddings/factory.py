"""Embedding service factory — the single construction site for the embedder."""
from __future__ import annotations

from jd_ocs_indexer.config import Settings
from jd_ocs_indexer.embeddings.base import EmbeddingService


def make_embedder(settings: Settings, *, batch_size: int | None = None) -> EmbeddingService:
    from jd_ocs_indexer.embeddings.bge_m3 import BGEM3Embedder  # lazy: avoid torch on import

    return BGEM3Embedder(
        model_name=settings.bge_m3_model,
        device=settings.bge_m3_device,
        use_fp16=settings.bge_m3_use_fp16,
        batch_size=batch_size if batch_size is not None else settings.bge_m3_batch_size,
    )
