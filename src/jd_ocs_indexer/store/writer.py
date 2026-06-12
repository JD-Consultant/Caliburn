"""Qdrant collection bootstrap + batch upsert."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from jd_ocs_indexer.models.chunk import EmbeddedChunk
from jd_ocs_indexer.store.ids import point_id
from jd_ocs_indexer.store.schema import (
    PAYLOAD_INDEXES,
    dense_vector_params,
    sparse_vector_params,
)


@dataclass
class UpsertReport:
    upserted: int = 0
    batches: int = 0
    retries: int = 0


# Transient HTTP statuses worth retrying — proxy/upstream blips, not Qdrant data errors
_RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, ResponseHandlingException):
        return True
    if isinstance(exc, UnexpectedResponse):
        return exc.status_code in _RETRYABLE_STATUSES
    return False


class QdrantWriter:
    def __init__(
        self,
        client: QdrantClient,
        collection: str,
        *,
        dense_size: int = 1024,
        supports_sparse: bool = True,
        batch_size: int = 64,
        max_retries: int = 4,
        retry_base_delay: float = 2.0,
    ) -> None:
        self.client = client
        self.collection = collection
        self.dense_size = dense_size
        self.supports_sparse = supports_sparse
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self._retries = 0

    # ---- collection bootstrap ----

    def ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config={"dense": dense_vector_params(self.dense_size)},
                sparse_vectors_config=(
                    {"sparse": sparse_vector_params()} if self.supports_sparse else None
                ),
            )

    def ensure_payload_indexes(self) -> None:
        for field_name, field_schema in PAYLOAD_INDEXES:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field_name,
                    field_schema=field_schema,
                )
            except Exception:
                # idempotent: index may already exist
                continue

    # ---- upsert ----

    def upsert(self, chunks: Iterable[EmbeddedChunk]) -> UpsertReport:
        self._retries = 0
        report = UpsertReport()
        batch: list[models.PointStruct] = []

        for ch in chunks:
            batch.append(self._to_point(ch))
            if len(batch) >= self.batch_size:
                self._flush(batch)
                report.upserted += len(batch)
                report.batches += 1
                batch = []

        if batch:
            self._flush(batch)
            report.upserted += len(batch)
            report.batches += 1

        report.retries = self._retries
        return report

    def _flush(self, batch: list[models.PointStruct]) -> None:
        """Upsert a batch, retrying transient proxy / upstream failures.

        Backs off exponentially (base * 2^attempt). On the final attempt,
        re-raises so the caller's manifest stays consistent — partial flushes
        are never silently swallowed.
        """
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                self.client.upsert(
                    collection_name=self.collection,
                    points=batch,
                    wait=True,
                )
                return
            except Exception as exc:
                if attempt >= self.max_retries or not _is_retryable(exc):
                    raise
                last_exc = exc
                self._retries += 1
                delay = self.retry_base_delay * (2 ** attempt)
                time.sleep(delay)
        # unreachable — loop either returns or raises
        assert last_exc is not None
        raise last_exc

    def delete_by_chunk_keys(self, chunk_keys: list[str]) -> None:
        if not chunk_keys:
            return
        ids = [point_id(k) for k in chunk_keys]
        self.client.delete(
            collection_name=self.collection,
            points_selector=models.PointIdsList(points=ids),
            wait=True,
        )

    # ---- helpers ----

    def _to_point(self, ch: EmbeddedChunk) -> models.PointStruct:
        vectors: dict[str, object] = {"dense": ch.dense}
        if self.supports_sparse and ch.sparse is not None:
            vectors["sparse"] = models.SparseVector(
                indices=ch.sparse.indices,
                values=ch.sparse.values,
            )
        return models.PointStruct(
            id=point_id(ch.record.chunk_key),
            vector=vectors,
            payload=ch.record.payload,
        )
