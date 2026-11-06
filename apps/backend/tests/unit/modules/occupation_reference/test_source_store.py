"""Immutable publication and pinned reads using the real Qdrant in-memory SDK."""

import json
from contextlib import closing
from dataclasses import replace

import httpx
import pytest
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException

from caliburn.modules.occupation_reference.application.errors import (
    ReferenceIndexError,
    ReferenceNotFoundError,
    ReferenceProviderError,
    ReferenceUnavailableError,
)
from caliburn.modules.occupation_reference.application.models import Embedding
from caliburn.modules.occupation_reference.application.search import ReferenceSearch
from caliburn.modules.occupation_reference.infrastructure.qdrant.store import (
    MANIFEST_ID,
    QdrantReferenceStore,
    index_references,
)
from tests.unit.modules.occupation_reference.source_support import (
    FixedEmbedder,
    FixedReranker,
    source_document,
)

pytestmark = pytest.mark.filterwarnings("ignore:Payload indexes have no effect")


def test_indexed_sources_are_searchable_and_readable_in_full() -> None:
    doc = source_document()
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        assert (
            index_references(database, "references", [doc], embedder, batch_size=2) == 5
        )
        search = ReferenceSearch(
            QdrantReferenceStore(database, "references", embedder.signature),
            embedder,
            FixedReranker(),
        )
        result = search.search("網頁")
        assert result.candidate_count == 1
        assert result.hits[0].document == search.read(doc.reference_id) == doc
        assert len(result.hits[0].document.tasks) == 3
        assert max(embedder.batch_sizes) <= 2
        with pytest.raises(ReferenceNotFoundError):
            search.read("bad-locator")


def test_task_read_returns_the_complete_pinned_group() -> None:
    doc = source_document()
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        index_references(database, "references", [doc], embedder)
        search = ReferenceSearch(
            QdrantReferenceStore(database, "references", embedder.signature),
            embedder,
            FixedReranker(),
        )
        task = search.read_task(doc.reference_id, "u1-t1")
        assert task.reference_id == doc.reference_id
        assert task.source_sha256 == doc.source_sha256
        assert task.entry == doc.tasks[0]
        assert [
            (item.code, item.name) for item in task.entry.group.task_codes or []
        ] == [
            ("T1", "介面製作"),
            ("T2", "流程整合"),
            (None, "資料串接"),
        ]
        blocks = task.entry.group.competency_blocks or []
        assert len(blocks) == 2
        assert [(item.code, item.name) for item in blocks[0].knowledge or []] == [
            (None, "工程識圖")
        ]
        assert [(item.code, item.name) for item in blocks[0].skills or []] == [
            (None, "資料閱讀")
        ]
        assert search.read_task(doc.reference_id, "u1-t3").entry == doc.tasks[2]


def test_task_read_rejects_unknown_task_within_the_selected_reference() -> None:
    doc = source_document()
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        index_references(database, "references", [doc], embedder)
        search = ReferenceSearch(
            QdrantReferenceStore(database, "references", embedder.signature),
            embedder,
            FixedReranker(),
        )
        with pytest.raises(ReferenceNotFoundError, match="task not found"):
            search.read_task(doc.reference_id, "u9-t1")


def test_unready_reference_index_cannot_serve_reads() -> None:
    doc = source_document()
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        index_references(database, "references", [doc], embedder)
        database.delete(
            "references", models.PointIdsList(points=[MANIFEST_ID]), wait=True
        )
        search = ReferenceSearch(
            QdrantReferenceStore(database, "references", embedder.signature),
            embedder,
            FixedReranker(),
        )
        with pytest.raises(ReferenceIndexError, match="ready manifest"):
            search.read(doc.reference_id)


def test_changed_source_and_signature_are_rejected_without_switching_versions() -> None:
    doc = source_document()
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        index_references(database, "references", [doc], embedder)
        different = replace(embedder.signature, revision="weights:other;policy:1")
        with pytest.raises(ReferenceIndexError, match="differs"):
            QdrantReferenceStore(database, "references", different).validate_index()
        database.set_payload(
            "references", {"source_utf8": doc.source_utf8 + "\n"}, [doc.reference_id]
        )
        with pytest.raises(ReferenceIndexError, match="identity differs"):
            QdrantReferenceStore(database, "references", embedder.signature).read(
                doc.reference_id
            )


def test_legacy_integer_revision_does_not_identify_local_model_weights() -> None:
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        index_references(database, "references", [source_document()], embedder)
        database.set_payload("references", {"revision": 1}, [MANIFEST_ID])
        with pytest.raises(ReferenceIndexError, match="manifest is invalid"):
            QdrantReferenceStore(
                database, "references", embedder.signature
            ).validate_index()


def test_legacy_wrapped_text_index_cannot_serve_searches_or_reads() -> None:
    doc = source_document(overview="quality\ncontrol")
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        index_references(database, "references", [doc], embedder)
        database.set_payload(
            "references", {"preprocessing": "ocs_top_body_v1"}, [MANIFEST_ID]
        )
        search = ReferenceSearch(
            QdrantReferenceStore(database, "references", embedder.signature),
            embedder,
            FixedReranker(),
        )
        with pytest.raises(ReferenceIndexError, match="preprocessing differs"):
            search.search("quality control")
        with pytest.raises(ReferenceIndexError, match="preprocessing differs"):
            search.read(doc.reference_id)


def test_index_does_not_overwrite_existing_collection_or_duplicate_versions() -> None:
    doc = source_document()
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        with pytest.raises(ValueError, match="one source"):
            index_references(database, "references", [doc, doc], embedder)
        assert not database.collection_exists("references")
        index_references(database, "references", [doc], embedder)
        with pytest.raises(ReferenceIndexError, match="new collection"):
            index_references(database, "references", [doc], embedder)


class FailingEmbedder(FixedEmbedder):
    def embed_texts(self, texts: list[str]) -> list[Embedding]:
        if self.batch_sizes:
            raise ReferenceProviderError("embedding failed")
        return super().embed_texts(texts)


def test_failed_embedding_leaves_collection_unready_and_cannot_resume() -> None:
    doc = source_document()
    embedder = FailingEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        with pytest.raises(ReferenceProviderError, match="embedding failed"):
            index_references(database, "references", [doc], embedder, batch_size=2)
        store = QdrantReferenceStore(database, "references", embedder.signature)
        with pytest.raises(ReferenceIndexError, match="ready manifest"):
            store.validate_index()
        with pytest.raises(ReferenceIndexError, match="new collection"):
            index_references(database, "references", [doc], FixedEmbedder())


def test_failed_upsert_leaves_collection_unready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        original_upsert = database.upsert
        written_batches = 0

        def fail_after_first_batch(
            collection_name: str, points: list[models.PointStruct], *, wait: bool
        ) -> models.UpdateResult:
            nonlocal written_batches
            if written_batches:
                raise ResponseHandlingException(httpx.ConnectError("offline"))
            written_batches += 1
            return original_upsert(collection_name, points=points, wait=wait)

        monkeypatch.setattr(database, "upsert", fail_after_first_batch)
        with pytest.raises(ReferenceUnavailableError):
            index_references(
                database, "references", [source_document()], embedder, batch_size=2
            )
        store = QdrantReferenceStore(database, "references", embedder.signature)
        with pytest.raises(ReferenceIndexError, match="ready manifest"):
            store.validate_index()


def test_count_mismatch_prevents_ready_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:

        def missing_points(collection_name: str, *, exact: bool) -> models.CountResult:
            return models.CountResult(count=0)

        monkeypatch.setattr(database, "count", missing_points)
        with pytest.raises(ReferenceIndexError, match="point count differs"):
            index_references(database, "references", [source_document()], embedder)
        store = QdrantReferenceStore(database, "references", embedder.signature)
        with pytest.raises(ReferenceIndexError, match="ready manifest"):
            store.validate_index()


def test_disconnected_store_reports_unavailable() -> None:
    def disconnected(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    embedder = FixedEmbedder()
    with closing(
        QdrantClient(
            url="http://qdrant.test:6333",
            check_compatibility=False,
            transport=httpx.MockTransport(disconnected),
        )
    ) as database:
        search = ReferenceSearch(
            QdrantReferenceStore(database, "references", embedder.signature),
            embedder,
            FixedReranker(),
        )
        with pytest.raises(ReferenceUnavailableError):
            search.read(source_document().reference_id)


@pytest.mark.parametrize(
    "status,expected_error",
    [
        (404, ReferenceIndexError),
        (503, ReferenceUnavailableError),
        (429, ReferenceUnavailableError),
    ],
)
def test_store_http_failures_keep_their_application_meaning(
    status: int, expected_error: type[Exception]
) -> None:
    def failed_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            json={"status": {"error": "synthetic"}},
            headers={"Retry-After": "1"},
        )

    embedder = FixedEmbedder()
    with closing(
        QdrantClient(
            url="http://qdrant.test:6333",
            check_compatibility=False,
            transport=httpx.MockTransport(failed_response),
        )
    ) as database:
        store = QdrantReferenceStore(database, "references", embedder.signature)
        with pytest.raises(expected_error):
            store.validate_index()


@pytest.mark.parametrize("body", [b'{"result": "not source records"}', b"not json"])
def test_malformed_store_response_reports_provider_failure(body: bytes) -> None:
    def malformed_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    embedder = FixedEmbedder()
    with closing(
        QdrantClient(
            url="http://qdrant.test:6333",
            check_compatibility=False,
            transport=httpx.MockTransport(malformed_response),
        )
    ) as database:
        store = QdrantReferenceStore(database, "references", embedder.signature)
        with pytest.raises(ReferenceProviderError):
            store.validate_index()


def test_grouped_search_rejects_nonfinite_score_after_a_finite_hit() -> None:
    reference_id = source_document().reference_id

    def nonfinite_group(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(
                {
                    "result": {
                        "groups": [
                            {
                                "id": reference_id,
                                "hits": [
                                    {
                                        "id": index,
                                        "version": 1,
                                        "score": score,
                                        "payload": {
                                            "kind": "task",
                                            "reference_id": reference_id,
                                            "task_id": f"u1-t{index}",
                                        },
                                    }
                                    for index, score in enumerate(
                                        [0.9, float("nan")], 1
                                    )
                                ],
                            }
                        ]
                    },
                    "status": "ok",
                    "time": 0.01,
                }
            ),
            headers={"Content-Type": "application/json"},
        )

    with closing(
        QdrantClient(
            url="http://qdrant.test:6333",
            check_compatibility=False,
            transport=httpx.MockTransport(nonfinite_group),
        )
    ) as database:
        store = QdrantReferenceStore(database, "references", FixedEmbedder.signature)
        with pytest.raises(ReferenceProviderError, match="search score"):
            store.search([1.0, 0.0], route="task", limit=1)


@pytest.mark.parametrize("location", [{}, {"task_id": None}, {"task_id": ""}])
def test_grouped_search_rejects_task_hits_without_identity(
    location: dict[str, str | None],
) -> None:
    reference_id = source_document().reference_id

    def missing_task_identity(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": {
                    "groups": [
                        {
                            "id": reference_id,
                            "hits": [
                                {
                                    "id": 1,
                                    "version": 1,
                                    "score": 0.9,
                                    "payload": {
                                        "kind": "task",
                                        "reference_id": reference_id,
                                        **location,
                                    },
                                }
                            ],
                        }
                    ]
                },
                "status": "ok",
                "time": 0.01,
            },
        )

    with closing(
        QdrantClient(
            url="http://qdrant.test:6333",
            check_compatibility=False,
            transport=httpx.MockTransport(missing_task_identity),
        )
    ) as database:
        store = QdrantReferenceStore(database, "references", FixedEmbedder.signature)
        with pytest.raises(ReferenceProviderError, match="task identity"):
            store.search([1.0, 0.0], route="task", limit=1)
