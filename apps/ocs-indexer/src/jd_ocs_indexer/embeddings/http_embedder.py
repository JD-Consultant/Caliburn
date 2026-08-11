"""HTTP embedder adapter — calls the `apps/embedder` BGE-M3 service (ADR 0012).

Implements the EmbeddingService port (3c) so the indexer needs no torch/FlagEmbedding
in-process. Reports the same signature as the former in-process embedder
(bge-m3 / BAAI/bge-m3 / 1024), so the existing ocs_v4 manifest stays compatible.
"""
from __future__ import annotations

import httpx

from jd_ocs_indexer.embeddings.base import EmbeddedVector, EmbeddingSignature
from jd_ocs_indexer.models.chunk import SparseVector

MODEL_NAME = "BAAI/bge-m3"
REVISION = 1


class HttpEmbedder:
    provider = "bge-m3"
    dense_size = 1024
    supports_sparse = True

    def __init__(self, base_url: str, *, timeout_s: float = 120.0, client: httpx.Client | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._client = client or httpx.Client(base_url=self._base, timeout=timeout_s)

    @property
    def signature(self) -> EmbeddingSignature:
        return EmbeddingSignature(
            provider=self.provider, model=MODEL_NAME, dim=self.dense_size, revision=REVISION
        )

    def embed_texts(self, texts: list[str]) -> list[EmbeddedVector]:
        if not texts:
            return []
        resp = self._client.post("/embed", json={"texts": texts})
        resp.raise_for_status()
        results: list[EmbeddedVector] = []
        for item in resp.json()["embeddings"]:
            sp = item.get("sparse") or {}
            results.append(
                EmbeddedVector(
                    dense=[float(x) for x in item["dense"]],
                    sparse=SparseVector(
                        indices=[int(i) for i in sp.get("indices", [])],
                        values=[float(v) for v in sp.get("values", [])],
                    ),
                )
            )
        return results

    def embed_query(self, text: str) -> EmbeddedVector:
        return self.embed_texts([text])[0]
