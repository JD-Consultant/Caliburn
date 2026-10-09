"""Pinned cross-encoder HTTP adapter with count, identity and finite-logit checks."""

from __future__ import annotations

import math

import httpx
from pydantic import BaseModel, ValidationError

from jd_ocs_indexer.references.errors import ReferenceProviderError, ReferenceQueryError

MODEL = "BAAI/bge-reranker-v2-m3"
REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"


class RerankResponse(BaseModel):
    model: str
    revision: str
    scores: list[float]


class HttpReranker:
    model = MODEL
    revision = REVISION

    def __init__(self, base_url: str, *, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), timeout=300, trust_env=False
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def score(self, query: str, documents: list[str]) -> list[float]:
        scores = []
        for start in range(0, len(documents), 32):
            batch = documents[start : start + 32]
            response = self._client.post(
                "/rerank", json={"query": query, "documents": batch}
            )
            if response.status_code == 422:
                try:
                    code = response.json().get("detail", {}).get("code")
                except (ValueError, AttributeError):
                    code = None
                if code == "query_too_long":
                    raise ReferenceQueryError(
                        "query leaves insufficient document token capacity"
                    )
            response.raise_for_status()
            try:
                body = RerankResponse.model_validate(response.json())
            except (ValueError, ValidationError) as exc:
                raise ReferenceProviderError("invalid reranker response") from exc
            if (
                body.model != self.model
                or body.revision != self.revision
                or len(body.scores) != len(batch)
                or not all(math.isfinite(score) for score in body.scores)
            ):
                raise ReferenceProviderError("reranker identity or scores differ")
            scores.extend(body.scores)
        return scores
