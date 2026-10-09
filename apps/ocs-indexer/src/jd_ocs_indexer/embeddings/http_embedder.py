"""HTTP embedder adapter — calls the `apps/embedder` BGE-M3 service (ADR 0012).

Implements the EmbeddingService port (3c) so the indexer needs no torch/FlagEmbedding
in-process. Reports the same signature as the former in-process embedder
(bge-m3 / BAAI/bge-m3 / 1024), so the existing ocs_v4 manifest stays compatible.
"""

from __future__ import annotations

import math

import httpx
from pydantic import BaseModel, Field, ValidationError

from jd_ocs_indexer.embeddings.base import (
    EmbeddedVector,
    EmbeddingResponseError,
    EmbeddingSignature,
)
from jd_ocs_indexer.models.chunk import SparseVector

MODEL_NAME = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
REVISION = 1


class SparseResponse(BaseModel):
    indices: list[int] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)


class VectorResponse(BaseModel):
    dense: list[float]
    sparse: SparseResponse | None = None


class EmbeddingResponse(BaseModel):
    model: str
    model_revision: str
    dim: int
    revision: int
    embeddings: list[VectorResponse]


class HttpEmbedder:
    provider = "bge-m3"
    dense_size = 1024
    supports_sparse = True

    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self._base, timeout=timeout_s, trust_env=False
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    @property
    def signature(self) -> EmbeddingSignature:
        return EmbeddingSignature(
            provider=self.provider,
            model=MODEL_NAME,
            dim=self.dense_size,
            revision=REVISION,
        )

    def embed_texts(self, texts: list[str]) -> list[EmbeddedVector]:
        if not texts:
            return []
        resp = self._client.post("/embed", json={"texts": texts})
        resp.raise_for_status()
        try:
            body = EmbeddingResponse.model_validate(resp.json())
        except (ValueError, ValidationError) as exc:
            raise EmbeddingResponseError("invalid embedding response") from exc
        if (body.model, body.model_revision, body.dim, body.revision) != (
            MODEL_NAME,
            MODEL_REVISION,
            self.dense_size,
            REVISION,
        ) or len(body.embeddings) != len(texts):
            raise EmbeddingResponseError("embedding model identity or count differs")
        results: list[EmbeddedVector] = []
        for item in body.embeddings:
            sp = item.sparse or SparseResponse()
            if (
                len(item.dense) != self.dense_size
                or not any(item.dense)
                or not all(math.isfinite(value) for value in item.dense)
                or len(sp.indices) != len(sp.values)
                or any(index < 0 for index in sp.indices)
                or not all(math.isfinite(value) for value in sp.values)
            ):
                raise EmbeddingResponseError("invalid embedding vector")
            results.append(
                EmbeddedVector(
                    dense=item.dense,
                    sparse=SparseVector(indices=sp.indices, values=sp.values),
                )
            )
        return results

    def embed_query(self, text: str) -> EmbeddedVector:
        return self.embed_texts([text])[0]
