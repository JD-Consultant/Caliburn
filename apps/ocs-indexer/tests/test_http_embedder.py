import json

import httpx

from jd_ocs_indexer.embeddings.base import EmbeddingSignature
from jd_ocs_indexer.embeddings.http_embedder import HttpEmbedder


def _handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    embs = [
        {"dense": [0.1] * 1024, "sparse": {"indices": [1, 2], "values": [0.5, 0.7]}}
        for _ in body["texts"]
    ]
    return httpx.Response(200, json={"embeddings": embs})


def _embedder(handler) -> HttpEmbedder:
    client = httpx.Client(base_url="http://embedder", transport=httpx.MockTransport(handler))
    return HttpEmbedder("http://embedder", client=client)


def test_signature_matches_manifest():
    assert _embedder(_handler).signature == EmbeddingSignature("bge-m3", "BAAI/bge-m3", 1024, 1)


def test_maps_dense_and_sparse():
    e = _embedder(_handler)
    out = e.embed_texts(["a", "b"])
    assert len(out) == 2
    assert len(out[0].dense) == 1024
    assert out[0].sparse.indices == [1, 2]
    assert out[0].sparse.values == [0.5, 0.7]
    q = e.embed_query("hi")
    assert len(q.dense) == 1024


def test_empty_texts_no_call():
    e = _embedder(lambda r: httpx.Response(500))  # would error if called
    assert e.embed_texts([]) == []
