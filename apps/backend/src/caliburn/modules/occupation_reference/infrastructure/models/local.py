"""Local BGE models with explicit ownership and no network access."""

from __future__ import annotations

import threading
from pathlib import Path

from caliburn.modules.occupation_reference.application.errors import (
    ReferenceProviderError,
    ReferenceQueryError,
    ReferenceUnavailableError,
)
from caliburn.modules.occupation_reference.application.models import (
    Embedding,
    EmbeddingSignature,
)
from caliburn.modules.occupation_reference.infrastructure.models.reranking import (
    score_documents,
)
from caliburn.modules.occupation_reference.infrastructure.models.runtime import (
    ModelRuntime,
    load_runtime,
)

EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
RERANKER_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"


def embedding_signature(
    *, device: str = "cpu", use_fp16: bool = True
) -> EmbeddingSignature:
    """Describe fixed weights and dense inference without importing model SDKs."""
    return EmbeddingSignature(
        provider="huggingface-local",
        model=EMBEDDING_MODEL,
        dim=1024,
        revision=(
            f"hf:{EMBEDDING_REVISION};transformers-cls-l2-8192-sdpa-v1;"
            f"{_precision(device=device, use_fp16=use_fp16)}"
        ),
    )


def _precision(*, device: str, use_fp16: bool) -> str:
    return "fp16" if use_fp16 and device.split(":", 1)[0] != "cpu" else "fp32"


class LocalModels:
    """Own both local models; construction and metadata do not load weights.

    Invoke synchronous inference through RetrievalWorker in an async app. The
    same lock protects inference and close. A closed owner cannot be reused.
    """

    def __init__(
        self,
        *,
        embedding_path: Path | None = None,
        reranker_path: Path | None = None,
        cache_dir: Path | None = None,
        device: str = "cpu",
        use_fp16: bool = True,
        batch_size: int = 8,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._lock = threading.RLock()
        self._closed = False
        self._signature = embedding_signature(device=device, use_fp16=use_fp16)
        self._revision = (
            f"hf:{RERANKER_REVISION};transformers-full-window-max-logit-"
            f"8192-overlap64-sdpa-v1;{_precision(device=device, use_fp16=use_fp16)}"
        )
        self._embedding_path = embedding_path
        self._reranker_path = reranker_path
        self._cache_dir = cache_dir
        self._device = device
        self._use_fp16 = use_fp16
        self._batch_size = batch_size
        self._embedding: ModelRuntime | None = None
        self._reranker: ModelRuntime | None = None

    @property
    def signature(self) -> EmbeddingSignature:
        return self._signature

    @property
    def model(self) -> str:
        return RERANKER_MODEL

    @property
    def revision(self) -> str:
        return self._revision

    def embed_texts(self, texts: list[str]) -> list[Embedding]:
        with self._lock:
            if self._closed:
                raise ReferenceUnavailableError("local models are closed")
            if not texts:
                return []
            runtime = self._load_embedding()
            embeddings: list[Embedding] = []
            try:
                for start in range(0, len(texts), self._batch_size):
                    embeddings.extend(
                        Embedding(dense)
                        for dense in runtime.embed(
                            texts[start : start + self._batch_size]
                        )
                    )
            except (RuntimeError, ValueError) as exc:
                raise ReferenceProviderError(
                    "local embedding inference failed"
                ) from exc
            return embeddings

    def embed_query(self, text: str) -> Embedding:
        return self.embed_texts([text])[0]

    def score(self, query: str, documents: list[str]) -> list[float]:
        with self._lock:
            if self._closed:
                raise ReferenceUnavailableError("local models are closed")
            runtime = self._load_reranker()
            try:
                return score_documents(
                    query,
                    documents,
                    encode=runtime.encode,
                    pair_score=runtime.pair_score,
                )
            except ReferenceQueryError:
                raise
            except (RuntimeError, ValueError) as exc:
                raise ReferenceProviderError("local reranker inference failed") from exc

    def close(self) -> None:
        with self._lock:
            self._closed = True
            embedding, reranker = self._embedding, self._reranker
            self._embedding = None
            self._reranker = None
            try:
                if embedding is not None:
                    embedding.close()
            finally:
                if reranker is not None:
                    reranker.close()

    def _load_embedding(self) -> ModelRuntime:
        if self._embedding is None:
            self._embedding = load_runtime(
                model=EMBEDDING_MODEL,
                revision=EMBEDDING_REVISION,
                path=self._embedding_path,
                cache_dir=self._cache_dir,
                device=self._device,
                use_fp16=self._use_fp16,
            )
        return self._embedding

    def _load_reranker(self) -> ModelRuntime:
        if self._reranker is None:
            self._reranker = load_runtime(
                model=RERANKER_MODEL,
                revision=RERANKER_REVISION,
                path=self._reranker_path,
                cache_dir=self._cache_dir,
                device=self._device,
                use_fp16=self._use_fp16,
                classification=True,
            )
        return self._reranker
