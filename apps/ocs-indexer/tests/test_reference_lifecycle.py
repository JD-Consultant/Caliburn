"""Resources are owned by the composition root and closed on startup failure too."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from jd_ocs_indexer.api.app import create_app
from jd_ocs_indexer.config import load_settings
from tests.conftest import FakeQdrant, StubEmbedder


def test_owned_resources_close_when_reference_configuration_fails(monkeypatch):
    closed = []

    class OwnedEmbedder(StubEmbedder):
        def close(self):
            closed.append("embedder")

    class OwnedStore(FakeQdrant):
        def close(self):
            closed.append("qdrant")

    class OwnedRanker:
        def __init__(self, url):
            pass

        def close(self):
            closed.append("reranker")

    monkeypatch.setattr(
        "jd_ocs_indexer.embeddings.factory.make_embedder", lambda *a, **kw: OwnedEmbedder()
    )
    monkeypatch.setattr("jd_ocs_indexer.store.qdrant_client.make_client", lambda **kw: OwnedStore())
    monkeypatch.setattr("jd_ocs_indexer.reranking.http_reranker.HttpReranker", OwnedRanker)
    settings = replace(
        load_settings(), reference_collection="references", reference_candidate_limit=81
    )
    with pytest.raises(ValueError, match="candidate_limit"):
        with TestClient(create_app(settings=settings)):
            pass
    assert closed == ["reranker", "qdrant", "embedder"]
