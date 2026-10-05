"""Real local GPU HTTP protocol smoke; run only in the network-disabled container."""

import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

import numpy as np
import torch
from fastapi.testclient import TestClient

sys.path.insert(0, "/app")
import app

EXPERIMENTS = Path("/experiments")
MEMORY = EXPERIMENTS / "2026-10-05-memory-public-unit-retrieval/run-01"
UNION = EXPERIMENTS / "2026-10-05-rerank-union-candidate-replay/run-01"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    torch.set_num_threads(4)
    query = next(item for item in read(MEMORY / "queries.json") if item["query_id"] == "F01-whole-1")
    vector = next(item["dense"] for item in read(MEMORY / "query-vectors.json") if item["query_id"] == query["query_id"])
    result = next(item for item in read(UNION / "results.json") if item["case_id"] == "F01" and item["method"] == "O-U-R")
    ids = [item["id"] for item in result["selected"]]
    corpus = {item["id"]: item["text"] for item in read(MEMORY / "corpus.json")}
    logits = {item["id"]: item["logit"] for line in (MEMORY / "rerank-pairs.jsonl").read_text().splitlines()
              if (item := json.loads(line))["query_id"] == query["query_id"]}
    with TestClient(app.app) as client:
        embedded = client.post("/embed", json={"texts": [query["text"]]})
        if embedded.status_code != 200:
            raise RuntimeError("real embedding protocol failed")
        body = embedded.json()
        if (body["model"], body["dim"], body["revision"]) != ("BAAI/bge-m3", 1024, 1):
            raise RuntimeError("real embedding identity differs")
        if body["model_revision"] != "5617a9f61b028005a4858fdac845db406aefb181":
            raise RuntimeError("real embedding weights differ")
        actual_vector = body["embeddings"][0]["dense"]
        vector_error = float(np.max(np.abs(np.asarray(actual_vector) - np.asarray(vector))))
        if vector_error > 0.001:
            raise RuntimeError("embedding differs from frozen runtime")
        reranked = client.post("/rerank", json={"query": query["text"], "documents": [corpus[key] for key in ids]})
        if reranked.status_code != 200:
            raise RuntimeError("real reranker protocol failed")
        scores = reranked.json()["scores"]
        error = max(abs(score - logits[key]) for score, key in zip(scores, ids, strict=True))
        if error > 0.01:
            raise RuntimeError("fresh reranker logits differ from frozen runtime")
        health = client.get("/health").json()
    record = {"network": "none", "fresh_embedding_queries": 1, "fresh_rerank_pairs": len(ids),
              "embedding_max_absolute_error": vector_error, "rerank_max_absolute_error": error,
              "query_sha256": hashlib.sha256(query["text"].encode()).hexdigest(),
              "document_ids": ids, "fresh_logits": scores, "health": health,
              "packages": {key: importlib.metadata.version(key) for key in ["torch", "transformers", "FlagEmbedding", "fastapi"]}}
    Path("/evidence/model-smoke-result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
