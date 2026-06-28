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


class EmbeddingMismatchError(RuntimeError):
    """Index was built with a different embedding model than the live embedder."""


def assert_compatible(manifest: "EmbeddingSignature | None", current: "EmbeddingSignature") -> None:
    """Fail fast when the query embedder does not match the index's.

    `None` manifest (pre-manifest index) is a soft allow with a warning; a
    provider/model/dim mismatch is a hard error; a revision-only difference warns.
    """
    import logging

    log = logging.getLogger("jd_ocs_indexer")
    if manifest is None:
        log.warning("No embedding manifest in collection; cannot verify compatibility (pre-manifest index?).")
        return
    if (manifest.provider, manifest.model, manifest.dim) != (current.provider, current.model, current.dim):
        raise EmbeddingMismatchError(
            f"index embedder {manifest.provider}/{manifest.model}/{manifest.dim} "
            f"!= query embedder {current.provider}/{current.model}/{current.dim}"
        )
    if manifest.revision != current.revision:
        log.warning("Embedding revision differs (index r%s vs query r%s).", manifest.revision, current.revision)


class EmbeddingService(Protocol):
    provider: str
    dense_size: int
    supports_sparse: bool
    signature: EmbeddingSignature

    def embed_texts(self, texts: list[str]) -> list[EmbeddedVector]:
        ...

    def embed_query(self, text: str) -> EmbeddedVector:
        ...
