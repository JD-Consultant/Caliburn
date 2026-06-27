"""Embedding service contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from jd_ocs_indexer.models.chunk import SparseVector


@dataclass
class EmbeddedVector:
    dense: list[float]
    sparse: SparseVector | None = None


class EmbeddingService(Protocol):
    provider: str
    dense_size: int
    supports_sparse: bool

    def embed_texts(self, texts: list[str]) -> list[EmbeddedVector]:
        ...

    def embed_query(self, text: str) -> EmbeddedVector:
        ...
