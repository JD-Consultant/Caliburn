"""BGE-M3 embedding adapter.

Produces dense (1024d) + sparse (BGE-M3 lexical_weights) vectors via the
FlagEmbedding `BGEM3FlagModel`. Loaded lazily so import doesn't drag in torch
unless we actually embed.
"""

from __future__ import annotations

from typing import Any

from jd_ocs_indexer.embeddings.base import EmbeddedVector, EmbeddingSignature
from jd_ocs_indexer.models.chunk import SparseVector


class BGEM3Embedder:
    provider = "bge-m3"
    dense_size = 1024
    supports_sparse = True
    REVISION = 1

    @property
    def signature(self) -> EmbeddingSignature:
        return EmbeddingSignature(
            provider=self.provider,
            model=self.model_name,
            dim=self.dense_size,
            revision=self.REVISION,
        )

    def __init__(
        self,
        *,
        model_name: str = "BAAI/bge-m3",
        device: str = "cpu",
        use_fp16: bool = False,
        batch_size: int = 8,
        max_length: int = 8192,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.use_fp16 = use_fp16
        self.batch_size = batch_size
        self.max_length = max_length
        self._model: Any | None = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            from FlagEmbedding import BGEM3FlagModel  # heavy import

            self._model = BGEM3FlagModel(
                self.model_name,
                use_fp16=self.use_fp16,
                devices=self.device,
            )
        return self._model

    def embed_texts(self, texts: list[str]) -> list[EmbeddedVector]:
        if not texts:
            return []
        model = self._ensure_model()
        out = model.encode(
            texts,
            batch_size=self.batch_size,
            max_length=self.max_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense_vecs = out["dense_vecs"]
        sparse_weights = out["lexical_weights"]

        results: list[EmbeddedVector] = []
        for i, _ in enumerate(texts):
            dense = _to_float_list(dense_vecs[i])
            sparse_dict = sparse_weights[i] if sparse_weights is not None else {}
            sparse = _sparse_from_lexical_weights(sparse_dict)
            results.append(EmbeddedVector(dense=dense, sparse=sparse))
        return results

    def embed_query(self, text: str) -> EmbeddedVector:
        return self.embed_texts([text])[0]


def _to_float_list(vec: Any) -> list[float]:
    # numpy array or list
    if hasattr(vec, "tolist"):
        return [float(x) for x in vec.tolist()]
    return [float(x) for x in vec]


def _sparse_from_lexical_weights(weights: dict) -> SparseVector | None:
    """Convert BGE-M3 lexical_weights dict (token_id -> weight) to sparse vector."""
    if not weights:
        return SparseVector(indices=[], values=[])
    indices: list[int] = []
    values: list[float] = []
    for k, v in weights.items():
        try:
            idx = int(k)
        except (TypeError, ValueError):
            continue
        try:
            val = float(v)
        except (TypeError, ValueError):
            continue
        if val == 0.0:
            continue
        indices.append(idx)
        values.append(val)
    return SparseVector(indices=indices, values=values)
