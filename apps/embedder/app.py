"""Caliburn embedder service — BGE-M3 (dense + sparse) over HTTP.

A thin FastAPI wrapper around FlagEmbedding's BGEM3FlagModel, run as its own Linux
GPU container so torch lives outside the app processes (ADR 0012). Produces the
SAME dense + sparse vectors as the former in-process BGEM3Embedder — the sparse
mapping mirrors jd_ocs_indexer.embeddings.bge_m3._sparse_from_lexical_weights.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

MODEL_ID = os.getenv("MODEL_ID", "BAAI/bge-m3")
DEVICE = os.getenv("DEVICE", "cuda")
USE_FP16 = os.getenv("USE_FP16", "true").lower() in {"1", "true", "yes", "on"}
MAX_LENGTH = int(os.getenv("MAX_LENGTH", "8192"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))
DENSE_SIZE = 1024

_model: Any = None


def _get_model() -> Any:
    global _model
    if _model is None:
        from FlagEmbedding import BGEM3FlagModel  # heavy import, container-only

        _model = BGEM3FlagModel(MODEL_ID, use_fp16=USE_FP16, devices=DEVICE)
    return _model


def _to_float_list(vec: Any) -> list[float]:
    return [float(x) for x in (vec.tolist() if hasattr(vec, "tolist") else vec)]


def _sparse_from_lexical_weights(weights: dict) -> dict:
    indices: list[int] = []
    values: list[float] = []
    for k, v in (weights or {}).items():
        try:
            idx = int(k)
        except (TypeError, ValueError):
            continue
        try:
            val = float(v)
        except (TypeError, ValueError):
            continue
        if val == 0.0:
            continue
        indices.append(idx)
        values.append(val)
    return {"indices": indices, "values": values}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load + warm the model once at startup (main process, Linux — stable torch).
    _get_model().encode(["warmup"], return_dense=True, return_sparse=True, return_colbert_vecs=False)
    yield


app = FastAPI(title="caliburn embedder (BGE-M3)", version="1.0", lifespan=lifespan)


class EmbedRequest(BaseModel):
    texts: list[str]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL_ID, "dim": DENSE_SIZE, "device": DEVICE}


@app.post("/embed")
def embed(req: EmbedRequest) -> dict:
    if not req.texts:
        return {"embeddings": []}
    out = _get_model().encode(
        req.texts,
        batch_size=BATCH_SIZE,
        max_length=MAX_LENGTH,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )
    dense_vecs = out["dense_vecs"]
    sparse_weights = out["lexical_weights"]
    embeddings = []
    for i in range(len(req.texts)):
        sparse = sparse_weights[i] if sparse_weights is not None else {}
        embeddings.append(
            {"dense": _to_float_list(dense_vecs[i]), "sparse": _sparse_from_lexical_weights(sparse)}
        )
    return {"embeddings": embeddings}
