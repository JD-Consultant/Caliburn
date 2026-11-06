"""Dense model ports and the complete identity required by a reference index."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmbeddingSignature:
    """Weights and inference policy must both be fixed in the revision string.

    Compatibility requires every field to match. Legacy integer revisions do
    not identify this module's local model implementation and are rejected.
    """

    provider: str
    model: str
    dim: int
    revision: str


@dataclass(frozen=True)
class Embedding:
    dense: list[float]


class Embedder(Protocol):
    @property
    def signature(self) -> EmbeddingSignature: ...

    def embed_texts(self, texts: list[str]) -> list[Embedding]: ...

    def embed_query(self, text: str) -> Embedding: ...


class Reranker(Protocol):
    @property
    def model(self) -> str: ...

    @property
    def revision(self) -> str: ...

    def score(self, query: str, documents: list[str]) -> list[float]: ...
