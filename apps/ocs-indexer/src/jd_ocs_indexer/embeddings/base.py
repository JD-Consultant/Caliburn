"""Embedding service contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from jd_ocs_indexer.models.chunk import SparseVector


@dataclass
class EmbeddedVector:
    dense: list[float]
    sparse: SparseVector | None = None


@dataclass(frozen=True)
class EmbeddingSignature:
    """Stable identity of an embedding space: provider + model + dim + revision.

    `revision` is bumped when preprocessing/normalization changes even if the
    model name does not. Two indexes are query-compatible iff provider/model/dim
    match (revision difference is a soft warning).
    """

    provider: str
    model: str
    dim: int
    revision: int


class EmbeddingService(Protocol):
    provider: str
    dense_size: int
    supports_sparse: bool
    signature: EmbeddingSignature

    def embed_texts(self, texts: list[str]) -> list[EmbeddedVector]:
        ...

    def embed_query(self, text: str) -> EmbeddedVector:
        ...
