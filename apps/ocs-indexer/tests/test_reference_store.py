"""Real Qdrant SDK integration for independent reference indexing and reads."""

from contextlib import closing
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from jd_ocs_indexer.api.app import create_app
from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.references.errors import ReferenceIndexError
from jd_ocs_indexer.references.service import ReferenceSearch
from jd_ocs_indexer.references.store import (
    MANIFEST_ID,
    QdrantReferenceStore,
    index_references,
)
from qdrant_client import QdrantClient, models
from tests.test_reference_retrieval import Ranker, source_document


def test_real_qdrant_search_and_fixed_source_task_reads(stub_embedder):
    doc = source_document()
    with closing(QdrantClient(":memory:")) as database:
        assert index_references(database, "references", [doc], stub_embedder, batch_size=2) == 5
        store = QdrantReferenceStore(database, "references", stub_embedder.signature)
        service = ReferenceSearch(store, stub_embedder, Ranker())
        app = create_app(
            settings=load_settings(),
            embedder=stub_embedder,
            client=database,
            reference_search=service,
        )
        with TestClient(app) as client:
            response = client.post("/occupation-references:search", json={"query": "網頁"})
            assert response.status_code == 200, response.text
            hit = response.json()["references"][0]
            assert len(hit["reference"]["units"][0]["tasks"]) == 3
            assert hit["retrieval_evidence"]["task_applicability"] == "not_evaluated"
            assert response.json()["retrieval_policy"]["candidate_count"] == 1
            base = f"/occupation-references/{doc.reference_id}"
            assert client.get(base).json() == hit["reference"]
            task = client.get(base + "/tasks/u1-t1").json()
            assert len(task["names"]) == 2
            assert task["competency_blocks"][0]["knowledge"] == [{"code": None, "name": "工程識圖"}]
            assert client.get(base + "/tasks/u1-t3").status_code == 200
            assert client.get(base + "/tasks/u9-t1").status_code == 404
            assert client.get("/occupation-references/bad-locator").status_code == 404
        # The API borrows this client and must leave it usable.
        assert database.count("references", exact=True).count == 6


def test_unready_reference_index_cannot_serve_reads(stub_embedder):
    doc = source_document()
    with closing(QdrantClient(":memory:")) as database:
        index_references(database, "references", [doc], stub_embedder)
        database.delete("references", models.PointIdsList(points=[MANIFEST_ID]), wait=True)
        search = ReferenceSearch(
            QdrantReferenceStore(database, "references", stub_embedder.signature),
            stub_embedder,
            Ranker(),
        )
        with pytest.raises(ReferenceIndexError):
            search.read(doc.reference_id)


def test_changed_source_and_signature_are_rejected_without_switching_versions(
    stub_embedder,
):
    doc = source_document()
    with closing(QdrantClient(":memory:")) as database:
        index_references(database, "references", [doc], stub_embedder)
        bad_signature = replace(stub_embedder.signature, revision=2)
        with pytest.raises(ReferenceIndexError):
            QdrantReferenceStore(database, "references", bad_signature).validate_index()
        database.set_payload(
            "references", {"source_utf8": doc.source_utf8 + "\n"}, [doc.reference_id]
        )
        with pytest.raises(ReferenceIndexError):
            QdrantReferenceStore(database, "references", stub_embedder.signature).read(
                doc.reference_id
            )


def test_index_does_not_overwrite_existing_collection_or_duplicate_versions(
    stub_embedder,
):
    doc = source_document()
    with closing(QdrantClient(":memory:")) as database:
        with pytest.raises(ValueError, match="one source"):
            index_references(database, "references", [doc, doc], stub_embedder)
        assert not database.collection_exists("references")
        index_references(database, "references", [doc], stub_embedder)
        with pytest.raises(ReferenceIndexError, match="new collection"):
            index_references(database, "references", [doc], stub_embedder)
