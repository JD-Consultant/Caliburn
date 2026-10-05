"""Qdrant reference adapter and immutable index build; no HTTP or employee state."""

from __future__ import annotations

import math
from dataclasses import asdict
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, ValidationError
from qdrant_client import QdrantClient, models

from jd_ocs_indexer.embeddings.base import EmbeddingService, EmbeddingSignature
from jd_ocs_indexer.references.errors import (
    ReferenceIndexError,
    ReferenceNotFoundError,
    ReferenceProviderError,
)
from jd_ocs_indexer.references.service import Candidate
from jd_ocs_indexer.references.source import (
    PREPROCESSING,
    ReferenceDocument,
    build_reference,
)

MANIFEST_ID = str(uuid5(NAMESPACE_URL, "caliburn:occupation-references:manifest"))


class IndexManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = "manifest"
    preprocessing: str
    provider: str
    model: str
    dim: int
    revision: int
    document_count: int
    point_count: int


class SourcePayload(BaseModel):
    kind: str
    reference_id: str
    source_sha256: str
    source_file: str
    source_utf8: str


class ChunkPayload(BaseModel):
    kind: str
    reference_id: str
    task_id: str | None = None


class QdrantReferenceStore:
    def __init__(
        self,
        client: QdrantClient,
        collection: str,
        signature: EmbeddingSignature,
    ) -> None:
        self.client = client
        self.collection = collection
        self.signature = signature

    def validate_index(self) -> None:
        points = self.client.retrieve(self.collection, ids=[MANIFEST_ID], with_vectors=False)
        if len(points) != 1:
            raise ReferenceIndexError("reference index has no ready manifest")
        try:
            manifest = IndexManifest.model_validate(points[0].payload)
        except ValidationError as exc:
            raise ReferenceIndexError("reference manifest is invalid") from exc
        expected = asdict(self.signature)
        if (
            manifest.preprocessing != PREPROCESSING
            or manifest.kind != "manifest"
            or any(getattr(manifest, key) != value for key, value in expected.items())
        ):
            raise ReferenceIndexError("reference index model or preprocessing differs")

    def search(self, dense: list[float], *, route: str, limit: int) -> list[Candidate]:
        if route not in {"document", "task"}:
            raise ValueError("unknown reference retrieval route")
        kinds = ["document"] if route == "document" else ["task", "overview"]
        groups = self.client.query_points_groups(
            collection_name=self.collection,
            query=dense,
            using="dense",
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="kind",
                        match=models.MatchAny(any=kinds),
                    )
                ]
            ),
            group_by="reference_id",
            group_size=3,
            limit=limit,
            with_payload=True,
            search_params=models.SearchParams(exact=True),
        ).groups
        candidates = []
        for group in groups:
            if not isinstance(group.id, str) or not group.hits:
                raise ReferenceProviderError("invalid reference search group")
            try:
                payloads = [ChunkPayload.model_validate(hit.payload) for hit in group.hits]
            except ValidationError as exc:
                raise ReferenceProviderError("invalid reference search payload") from exc
            if any(p.reference_id != group.id or p.kind not in kinds for p in payloads):
                raise ReferenceProviderError("reference group identity differs")
            candidates.append(
                Candidate(
                    group.id,
                    max(hit.score for hit in group.hits),
                    tuple(dict.fromkeys(p.task_id for p in payloads if p.task_id)),
                    any(p.kind == "overview" for p in payloads),
                )
            )
        return sorted(candidates, key=lambda hit: (-hit.cosine, hit.reference_id))

    def read(self, reference_id: str) -> ReferenceDocument:
        # Invalid/non-UUID external locators are not sent into Qdrant's id parser.
        from uuid import UUID

        try:
            UUID(reference_id)
        except ValueError as exc:
            raise ReferenceNotFoundError("reference not found") from exc
        records = self.client.retrieve(self.collection, ids=[reference_id], with_vectors=False)
        if not records:
            raise ReferenceNotFoundError("reference not found")
        try:
            payload = SourcePayload.model_validate(records[0].payload)
            doc = build_reference(payload.source_utf8, source_file=payload.source_file)
        except (ValueError, ValidationError) as exc:
            raise ReferenceIndexError("stored public source is invalid") from exc
        if (
            payload.kind != "document"
            or payload.reference_id != reference_id
            or doc.reference_id != reference_id
            or doc.source_sha256 != payload.source_sha256
        ):
            raise ReferenceIndexError("stored public source identity differs")
        return doc


def index_references(
    client: QdrantClient,
    collection: str,
    documents: list[ReferenceDocument],
    embedder: EmbeddingService,
    *,
    batch_size: int = 32,
) -> int:
    """Build only a new collection; failures leave an unready index for inspection."""
    if not documents or batch_size < 1:
        raise ValueError("selected public sources and positive batch_size are required")
    if len({doc.ocs_code for doc in documents}) != len(documents):
        raise ValueError("select one source per OCS code before indexing")
    if client.collection_exists(collection):
        raise ReferenceIndexError("reference indexing requires a new collection")
    client.create_collection(
        collection,
        vectors_config={
            "dense": models.VectorParams(
                size=embedder.signature.dim, distance=models.Distance.COSINE
            ),
        },
    )
    for field_name in ("kind", "reference_id"):
        client.create_payload_index(
            collection, field_name, models.PayloadSchemaType.KEYWORD, wait=True
        )
    pending: list[tuple[str, str, dict[str, object]]] = []
    written = 0

    def flush() -> None:
        nonlocal written
        if not pending:
            return
        texts = [text for _, text, _ in pending if text]
        vectors = embedder.embed_texts(texts) if texts else []
        if len(vectors) != len(texts) or any(
            len(vector.dense) != embedder.signature.dim
            or not all(math.isfinite(value) for value in vector.dense)
            or not any(vector.dense)
            for vector in vectors
        ):
            raise ReferenceProviderError("invalid source embeddings")
        vector_iterator = iter(vectors)
        points = []
        for point_id, text, payload in pending:
            if text:
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector={"dense": next(vector_iterator).dense},
                        payload=payload,
                    )
                )
            else:
                points.append(models.PointStruct(id=point_id, vector={}, payload=payload))
        client.upsert(collection, points=points, wait=True)
        written += len(points)
        pending.clear()

    for doc in documents:
        payload = SourcePayload(
            kind="document",
            reference_id=doc.reference_id,
            source_sha256=doc.source_sha256,
            source_file=doc.source_file,
            source_utf8=doc.source_utf8,
        ).model_dump()
        pending.append((doc.reference_id, doc.document_text, payload))
        for chunk in doc.chunks:
            point_id = str(uuid5(NAMESPACE_URL, f"{doc.reference_id}:{chunk.chunk_id}"))
            pending.append(
                (
                    point_id,
                    chunk.text,
                    ChunkPayload(
                        kind=chunk.kind,
                        reference_id=doc.reference_id,
                        task_id=chunk.task_id,
                    ).model_dump(),
                )
            )
        if len(pending) >= batch_size:
            # Large public documents cannot enlarge a provider batch beyond its configured bound.
            while len(pending) > batch_size:
                remainder = pending[batch_size:]
                del pending[batch_size:]
                flush()
                pending.extend(remainder)
            flush()
    flush()
    if client.count(collection, exact=True).count != written:
        raise ReferenceIndexError("reference point count differs after indexing")
    manifest = IndexManifest(
        preprocessing=PREPROCESSING,
        **asdict(embedder.signature),
        document_count=len(documents),
        point_count=written,
    )
    client.upsert(
        collection,
        points=[
            models.PointStruct(
                id=MANIFEST_ID,
                vector={},
                payload=manifest.model_dump(),
            )
        ],
        wait=True,
    )
    return written
