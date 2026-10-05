"""Experiment-only runtime inspection around the existing HTTP embedding app."""

import importlib.metadata
import os
import sys

import uvicorn
from huggingface_hub import snapshot_download
from pydantic import BaseModel

sys.path.insert(0, "/app")

revision = os.environ["EVAL_MODEL_REVISION"]
model_path = snapshot_download(
    "BAAI/bge-m3",
    revision=revision,
    allow_patterns=[
        "config.json", "pytorch_model.bin", "tokenizer*", "sentencepiece.bpe.model",
        "special_tokens_map.json", "colbert_linear.pt", "sparse_linear.pt",
    ],
)
os.environ["MODEL_ID"] = model_path

import app as embedding_app  # noqa: E402


class Texts(BaseModel):
    texts: list[str]


@embedding_app.app.get("/runtime")
def runtime():
    return {
        "model": "BAAI/bge-m3", "revision": revision,
        "device": embedding_app.DEVICE, "fp16": embedding_app.USE_FP16,
        "max_length": embedding_app.MAX_LENGTH,
        "batch_size": embedding_app.BATCH_SIZE,
        "packages": {name: importlib.metadata.version(name) for name in
                     ["torch", "transformers", "FlagEmbedding", "huggingface-hub"]},
    }


@embedding_app.app.post("/token-lengths")
def token_lengths(req: Texts):
    tokenizer = embedding_app._get_model().tokenizer
    return {"lengths": [len(tokenizer.encode(text, truncation=False))
                        for text in req.texts]}


uvicorn.run(embedding_app.app, host="0.0.0.0", port=80)
