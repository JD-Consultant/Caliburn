"""Caliburn embedder service — BGE-M3 (dense + sparse) over HTTP.

A thin FastAPI wrapper around FlagEmbedding's BGEM3FlagModel, run as its own Linux
GPU container so torch lives outside the app processes (ADR 0012). Produces the
SAME dense + sparse vectors as the former in-process BGEM3Embedder — the sparse
mapping mirrors jd_ocs_indexer.embeddings.bge_m3._sparse_from_lexical_weights.
"""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from reranking import score_documents

MODEL_ID = os.getenv("MODEL_ID", "BAAI/bge-m3")
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
DEVICE = os.getenv("DEVICE", "cuda")
USE_FP16 = os.getenv("USE_FP16", "true").lower() in {"1", "true", "yes", "on"}
MAX_LENGTH = int(os.getenv("MAX_LENGTH", "8192"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))
DENSE_SIZE = 1024

_model: Any = None
_reranker: Any = None
_model_lock = threading.Lock()
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
RERANKER_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _get_reranker() -> Any:
    global _reranker
    if _reranker is None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            RERANKER_MODEL,
            revision=RERANKER_REVISION,
            trust_remote_code=False,
        )
        model = (
            AutoModelForSequenceClassification.from_pretrained(
                RERANKER_MODEL,
                revision=RERANKER_REVISION,
                trust_remote_code=False,
                torch_dtype=torch.float16 if USE_FP16 and DEVICE != "cpu" else torch.float32,
                attn_implementation="sdpa",
            )
            .to(DEVICE)
            .eval()
        )
        _reranker = (tokenizer, model)
    return _reranker


def _get_model() -> Any:
    global _model
    if _model is None:
        from FlagEmbedding import BGEM3FlagModel  # heavy import, container-only
        from huggingface_hub import snapshot_download

        model_path = (
            snapshot_download(
                MODEL_ID,
                revision=MODEL_REVISION,
                allow_patterns=[
                    "config.json",
                    "pytorch_model.bin",
                    "tokenizer*",
                    "sentencepiece.bpe.model",
                    "special_tokens_map.json",
                    "colbert_linear.pt",
                    "sparse_linear.pt",
                ],
            )
            if MODEL_ID == "BAAI/bge-m3"
            else MODEL_ID
        )
        _model = BGEM3FlagModel(model_path, use_fp16=USE_FP16, devices=DEVICE)
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
    global _model, _reranker
    try:
        # Startup failures must release any model loaded before the failing stage.
        _get_model().encode(
            ["warmup"], return_dense=True, return_sparse=True, return_colbert_vecs=False
        )
        if RERANKER_ENABLED:
            _get_reranker()
        yield
    finally:
        _model = None
        _reranker = None


app = FastAPI(title="caliburn embedder (BGE-M3)", version="1.0", lifespan=lifespan)


class EmbedRequest(BaseModel):
    texts: list[str]


class RerankRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=12_000)
    documents: list[str] = Field(min_length=1, max_length=32)

    @field_validator("query")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must contain work content")
        return value


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "dim": DENSE_SIZE,
        "device": DEVICE,
        "reranker_loaded": _reranker is not None,
        "reranker_model": RERANKER_MODEL,
        "reranker_revision": RERANKER_REVISION,
    }


@app.post("/embed")
def embed(req: EmbedRequest) -> dict:
    if not req.texts:
        return {
            "embeddings": [],
            "model": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "dim": DENSE_SIZE,
            "revision": 1,
        }
    with _model_lock:
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
            {
                "dense": _to_float_list(dense_vecs[i]),
                "sparse": _sparse_from_lexical_weights(sparse),
            }
        )
    return {
        "embeddings": embeddings,
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "dim": DENSE_SIZE,
        "revision": 1,
    }


@app.post("/rerank")
def rerank(req: RerankRequest) -> dict:
    if not RERANKER_ENABLED:
        raise HTTPException(503, detail={"code": "reranker_disabled"})
    with _model_lock:
        tokenizer, model = _get_reranker()
        import torch

        def encode(text: str) -> list[int]:
            return tokenizer.encode(text, add_special_tokens=False, truncation=False)

        def pair_score(query: list[int], document: list[int]) -> float:
            ids = tokenizer.build_inputs_with_special_tokens(query, document)
            if len(ids) > 8192:
                raise RuntimeError("reranker pair exceeds model token capacity")
            inputs = {
                "input_ids": torch.tensor([ids], device=DEVICE),
                "attention_mask": torch.ones((1, len(ids)), device=DEVICE, dtype=torch.long),
            }
            with torch.inference_mode():
                return float(model(**inputs, return_dict=True).logits.flatten()[0].float().item())

        try:
            scores = score_documents(req.query, req.documents, encode=encode, pair_score=pair_score)
        except ValueError as exc:
            raise HTTPException(422, detail={"code": "query_too_long"}) from exc
    return {"model": RERANKER_MODEL, "revision": RERANKER_REVISION, "scores": scores}
