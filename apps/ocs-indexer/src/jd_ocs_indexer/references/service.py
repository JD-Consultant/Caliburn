"""Reference search use case: complete D/T union, rerank, then final quota."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from jd_ocs_indexer.embeddings.base import EmbeddingService
from jd_ocs_indexer.references.errors import ReferenceProviderError, ReferenceQueryError
from jd_ocs_indexer.references.source import ReferenceDocument


@dataclass(frozen=True)
class Candidate:
    reference_id: str
    cosine: float
    task_ids: tuple[str, ...] = ()
    overview_matched: bool = False


class ReferenceStore(Protocol):
    def validate_index(self) -> None: ...
    def search(self, dense: list[float], *, route: str, limit: int) -> list[Candidate]: ...
    def read(self, reference_id: str) -> ReferenceDocument: ...


class Reranker(Protocol):
    model: str
    revision: str

    def score(self, query: str, documents: list[str]) -> list[float]: ...


@dataclass(frozen=True)
class ReferenceHit:
    document: ReferenceDocument
    document_cosine: float | None
    task_cosine: float | None
    matched_task_ids: tuple[str, ...]
    overview_matched: bool
    rerank_logit: float


@dataclass(frozen=True)
class SearchResult:
    hits: tuple[ReferenceHit, ...]
    candidate_count: int


class ReferenceSearch:
    """Owns a use case, not transport or client lifecycles; dependencies are borrowed."""

    def __init__(
        self,
        store: ReferenceStore,
        embedder: EmbeddingService,
        reranker: Reranker,
        *,
        candidate_limit: int = 20,
    ) -> None:
        if not 1 <= candidate_limit <= 80:
            raise ValueError("candidate_limit must be between 1 and 80")
        self.store = store
        self.embedder = embedder
        self.reranker = reranker
        self.candidate_limit = candidate_limit

    def search(self, query: str, *, limit: int = 5) -> SearchResult:
        if not query.strip() or len(query) > 12_000 or not 1 <= limit <= 5:
            raise ReferenceQueryError("invalid query or final reference quota")
        self.store.validate_index()
        dense = self.embedder.embed_query(query).dense
        if (
            len(dense) != self.embedder.signature.dim
            or not all(math.isfinite(value) for value in dense)
            or not any(dense)
        ):
            raise ReferenceProviderError("invalid query embedding")
        routes = {}
        for route in ("document", "task"):
            candidates = self.store.search(dense, route=route, limit=self.candidate_limit)
            if (
                len({hit.reference_id for hit in candidates}) != len(candidates)
                or len(candidates) > self.candidate_limit
                or any(not math.isfinite(hit.cosine) for hit in candidates)
            ):
                raise ReferenceProviderError("invalid candidate groups")
            routes[route] = {hit.reference_id: hit for hit in candidates}
        reference_ids = sorted(routes["document"].keys() | routes["task"].keys())
        if not reference_ids:
            return SearchResult((), 0)
        documents = [self.store.read(reference_id) for reference_id in reference_ids]
        scores = self.reranker.score(query, [doc.document_text for doc in documents])
        if len(scores) != len(documents) or not all(math.isfinite(score) for score in scores):
            raise ReferenceProviderError("invalid reranker scores")
        hits = []
        for doc, score in zip(documents, scores, strict=True):
            document_hit = routes["document"].get(doc.reference_id)
            task_hit = routes["task"].get(doc.reference_id)
            task_ids = task_hit.task_ids if task_hit else ()
            if not set(task_ids) <= {task.task_id for task in doc.tasks}:
                raise ReferenceProviderError("candidate task identity does not match its source")
            hits.append(
                ReferenceHit(
                    doc,
                    document_hit.cosine if document_hit else None,
                    task_hit.cosine if task_hit else None,
                    task_ids,
                    task_hit.overview_matched if task_hit else False,
                    score,
                )
            )
        hits.sort(
            key=lambda hit: (
                -hit.rerank_logit,
                hit.document.ocs_code,
                hit.document.reference_id,
            )
        )
        return SearchResult(tuple(hits[:limit]), len(reference_ids))

    def read(self, reference_id: str) -> ReferenceDocument:
        self.store.validate_index()
        return self.store.read(reference_id)
