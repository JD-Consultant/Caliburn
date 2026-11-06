"""Isolated real-Qdrant publication, search and failure behavior through HTTP."""

import os
from collections.abc import Iterator
from dataclasses import replace
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from caliburn.modules.occupation_reference.application.errors import (
    ReferenceIndexError,
    ReferenceProviderError,
)
from caliburn.modules.occupation_reference.application.models import Embedding
from caliburn.modules.occupation_reference.application.search import ReferenceSearch
from caliburn.modules.occupation_reference.infrastructure.qdrant.store import (
    QdrantReferenceStore,
    index_references,
)
from tests.unit.modules.occupation_reference.source_support import (
    FixedEmbedder,
    FixedReranker,
    source_document,
)
from tests.unit.modules.occupation_reference.test_http_queries import reference_app


@pytest.fixture
def database() -> Iterator[tuple[QdrantClient, str]]:
    url = os.environ.get("CALIBURN_REBUILD_TEST_QDRANT_URL")
    if not url:
        pytest.skip("set CALIBURN_REBUILD_TEST_QDRANT_URL for real Qdrant tests")
    parsed = urlparse(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
    ):
        pytest.fail("Qdrant tests require a loopback URL without credentials or query")
    # Qdrant's Windows gridstore still meets legacy path limits on long roots.
    collection = f"cr_{uuid4().hex}"
    client = QdrantClient(url=url, timeout=10, check_compatibility=False)
    try:
        yield client, collection
    finally:
        try:
            if client.collection_exists(collection):
                client.delete_collection(collection)
        finally:
            client.close()


def test_real_server_search_reads_and_immutable_publication(
    database: tuple[QdrantClient, str],
) -> None:
    client, collection = database
    document = source_document()
    embedder = FixedEmbedder()
    index_references(client, collection, [document], embedder, batch_size=2)
    service = ReferenceSearch(
        QdrantReferenceStore(client, collection, embedder.signature),
        embedder,
        FixedReranker(),
    )
    with TestClient(reference_app(service)) as http:
        response = http.post("/occupation-references:search", json={"query": "網頁"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["retrieval_policy"]["candidate_count"] == 1
        reference = result["references"][0]["reference"]
        assert reference["reference_id"] == document.reference_id
        assert len(reference["units"][0]["tasks"]) == 3
        base = f"/occupation-references/{document.reference_id}"
        assert http.get(base).json() == reference
        assert len(http.get(base + "/tasks/u1-t1").json()["competency_blocks"]) == 2
        assert http.get(base + "/tasks/u1-t3").status_code == 200
        assert http.get(base + "/tasks/u1-t4").status_code == 404
    with pytest.raises(ReferenceIndexError, match="new collection"):
        index_references(client, collection, [document], embedder)
    assert service.read(document.reference_id) == document
    wrong_model = replace(embedder.signature, revision="other-weights")
    with pytest.raises(ReferenceIndexError):
        QdrantReferenceStore(client, collection, wrong_model).validate_index()


def test_failed_real_server_build_remains_unpublished(
    database: tuple[QdrantClient, str],
) -> None:
    client, collection = database

    class FailingEmbedder(FixedEmbedder):
        def embed_texts(self, texts: list[str]) -> list[Embedding]:
            if self.batch_sizes:
                raise ReferenceProviderError("injected model failure")
            return super().embed_texts(texts)

    embedder = FailingEmbedder()
    with pytest.raises(ReferenceProviderError):
        index_references(
            client, collection, [source_document()], embedder, batch_size=1
        )
    assert client.count(collection, exact=True).count == 1
    service = ReferenceSearch(
        QdrantReferenceStore(client, collection, embedder.signature),
        embedder,
        FixedReranker(),
    )
    with TestClient(reference_app(service)) as http:
        response = http.post("/occupation-references:search", json={"query": "網頁"})
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "reference_index_incompatible"


def test_missing_real_collection_is_an_index_error(
    database: tuple[QdrantClient, str],
) -> None:
    client, collection = database
    embedder = FixedEmbedder()
    service = ReferenceSearch(
        QdrantReferenceStore(client, collection, embedder.signature),
        embedder,
        FixedReranker(),
    )
    with TestClient(reference_app(service)) as http:
        assert http.get(f"/occupation-references/{uuid4()}").status_code == 409
