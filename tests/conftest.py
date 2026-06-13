"""Shared test fakes + fixtures.

Keeps the real 2GB BGE-M3 model and a live Qdrant out of the unit tests:
`StubEmbedder` returns fixed vectors; `FakeQdrant` returns canned points.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from jd_ocs_indexer.embeddings.base import EmbeddedVector
from jd_ocs_indexer.models.chunk import SparseVector


@dataclass
class FakePoint:
    payload: dict
    score: float | None = None


class StubEmbedder:
    provider = "stub"
    dense_size = 1024
    supports_sparse = True

    def embed_query(self, text: str) -> EmbeddedVector:
        return EmbeddedVector(
            dense=[0.1] * 1024,
            sparse=SparseVector(indices=[1, 2], values=[0.5, 0.7]),
        )

    def embed_texts(self, texts: list[str]) -> list[EmbeddedVector]:
        return [self.embed_query(t) for t in texts]


def _level_of(flt) -> str:
    try:
        for cond in flt.must:
            if getattr(cond, "key", None) == "chunk_level":
                return cond.match.value
    except Exception:
        pass
    return "__total__"


class FakeQdrant:
    """Minimal stand-in for QdrantClient covering the methods service.py uses."""

    def __init__(self, *, query_points=None, scroll_pages=None, counts=None):
        self._qp = list(query_points or [])
        self._scroll_pages = list(scroll_pages or [([], None)])
        self._counts = counts or {}
        self._i = 0

    def query_points(self, **kw):
        return SimpleNamespace(points=list(self._qp))

    def scroll(self, **kw):
        if self._i >= len(self._scroll_pages):
            return [], None  # past the end → always signal done (no infinite loops)
        recs, offset = self._scroll_pages[self._i]
        self._i += 1
        wrapped = [r if isinstance(r, FakePoint) else FakePoint(payload=r) for r in recs]
        return wrapped, offset

    def count(self, **kw):
        flt = kw.get("count_filter")
        key = _level_of(flt) if flt is not None else "__total__"
        return SimpleNamespace(count=self._counts.get(key, 0))

    def get_collections(self):
        return SimpleNamespace(collections=[])


@pytest.fixture
def stub_embedder():
    return StubEmbedder()


@pytest.fixture
def fake_point():
    def _make(*, payload: dict, score: float | None = None):
        return FakePoint(payload=payload, score=score)
    return _make


@pytest.fixture
def make_qdrant():
    def _make(**kw):
        return FakeQdrant(**kw)
    return _make


@pytest.fixture
def make_app(stub_embedder):
    from jd_ocs_indexer.api.app import create_app
    from jd_ocs_indexer.config import load_settings

    def _make(client):
        return create_app(settings=load_settings(), embedder=stub_embedder, client=client)
    return _make
