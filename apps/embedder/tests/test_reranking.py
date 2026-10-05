"""Full-document window coverage without importing GPU model dependencies."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reranking import score_documents, token_windows


def test_rerank_request_schema_rejects_blank_and_unbounded_requests():
    import app
    from fastapi.testclient import TestClient

    # No lifespan/model startup is needed to verify HTTP request validation.
    client = TestClient(app.app)
    for body in (
        {"query": " ", "documents": ["body"]},
        {"query": "work", "documents": []},
        {"query": "work", "documents": ["body"] * 33},
    ):
        assert client.post("/rerank", json=body).status_code == 422


def test_windows_cover_last_token_and_overlap_without_query_truncation():
    tokens = list(range(20))
    windows = token_windows([100, 101], tokens, max_tokens=12, overlap=2)
    assert windows == [
        tokens[0:6],
        tokens[4:10],
        tokens[8:14],
        tokens[12:18],
        tokens[16:20],
    ]
    with pytest.raises(ValueError):
        token_windows(list(range(10)), tokens, max_tokens=12, overlap=2)


def test_full_document_score_includes_tail_and_keeps_input_order():
    scores = score_documents(
        "q",
        ["000000000009", "1"],
        encode=lambda text: list(map(ord, text)),
        pair_score=lambda query, passage: max(passage) - 48,
        max_tokens=10,
        overlap=1,
    )
    assert scores == [9, 1]


def test_invalid_window_score_is_not_returned():
    with pytest.raises(RuntimeError, match="non-finite"):
        score_documents(
            "q",
            ["x"],
            encode=lambda text: [1],
            pair_score=lambda query, passage: float("nan"),
        )


def test_gpu_startup_failure_releases_already_loaded_model(monkeypatch):
    import asyncio

    import app

    class Model:
        def encode(self, *args, **kwargs):
            return {}

    model = Model()
    monkeypatch.setattr(app, "_model", model)
    monkeypatch.setattr(app, "RERANKER_ENABLED", True)

    def fail():
        raise RuntimeError("model startup failed")

    monkeypatch.setattr(app, "_get_reranker", fail)

    async def start():
        async with app.lifespan(app.app):
            pass

    with pytest.raises(RuntimeError, match="startup failed"):
        asyncio.run(start())
    assert app._model is None
    assert app._reranker is None
