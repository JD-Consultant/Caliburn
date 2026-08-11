import pytest

from jd_ocs_indexer.api import service
from jd_ocs_indexer.embeddings.base import (
    EmbeddingMismatchError,
    EmbeddingSignature,
    assert_compatible,
)


def test_assert_compatible_raises_on_model_diff():
    cur = EmbeddingSignature("bge-m3", "BAAI/bge-m3", 1024, 1)
    with pytest.raises(EmbeddingMismatchError):
        assert_compatible(EmbeddingSignature("bge-m3", "other/model", 1024, 1), cur)


def test_assert_compatible_allows_match_and_missing():
    cur = EmbeddingSignature("bge-m3", "BAAI/bge-m3", 1024, 1)
    assert_compatible(cur, cur)   # exact match → ok
    assert_compatible(None, cur)  # no manifest (pre-manifest index) → soft allow


def test_search_tasks_raises_on_mismatch(make_qdrant, stub_embedder, fake_point):
    mani = fake_point(payload={
        "chunk_level": "_manifest",
        "embedding": {"provider": "stub", "model": "DIFFERENT", "dim": 1024, "revision": 1},
    })
    client = make_qdrant(retrieve_points=[mani], query_points=[])
    with pytest.raises(EmbeddingMismatchError):
        service.search_tasks(client, stub_embedder, "ocs_v3", query="x")
