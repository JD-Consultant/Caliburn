"""New API with real local Qdrant and GPU HTTP dependencies; one fixed synthetic case."""

import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from jd_ocs_indexer.api.app import create_app
from jd_ocs_indexer.config import load_settings

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXPERIMENTS = ROOT / "docs/experiments"


def main():
    memory = EXPERIMENTS / "2026-10-05-memory-public-unit-retrieval/run-01"
    union = EXPERIMENTS / "2026-10-05-rerank-union-candidate-replay/run-01"
    query = next(
        item for item in json.loads((memory / "queries.json").read_text(encoding="utf-8"))
        if item["query_id"] == "F01-whole-1"
    )
    expected = next(
        [hit["id"] for hit in item["selected"]]
        for item in json.loads((union / "results.json").read_text(encoding="utf-8"))
        if item["case_id"] == "F01" and item["method"] == "O-U-R"
    )
    model_url = "http://127.0.0.1:16341"
    with httpx.Client(base_url=model_url, trust_env=False, timeout=2) as model:
        ready = model.get("/health")
        ready.raise_for_status()
        health = ready.json()
    settings = replace(
        load_settings(), qdrant_url="http://127.0.0.1:16340", qdrant_api_key=None,
        reference_collection="reference_api_replay_02", reference_candidate_limit=20,
        embedder_url=model_url, reranker_url=model_url,
    )
    started = time.perf_counter()
    with TestClient(create_app(settings=settings)) as client:
        response = client.post("/occupation-references:search", json={"query": query["text"]})
        if response.status_code != 200:
            raise RuntimeError(f"live reference API failed: {response.status_code}")
        body = response.json()
        selected = [hit["reference"]["ocs_code"] for hit in body["references"]]
        if selected != expected:
            raise RuntimeError(f"live top5 differs: {selected}")
        task_reads = 0
        for hit in body["references"]:
            reference = hit["reference"]
            base = f"/occupation-references/{reference['reference_id']}"
            if client.get(base).json() != reference:
                raise RuntimeError("live fixed source differs")
            for unit in reference["units"]:
                for task in unit["tasks"]:
                    if client.get(base + "/tasks/" + task["task_id"]).status_code != 200:
                        raise RuntimeError("live task read failed")
                    task_reads += 1
    record = {
        "scope": "API_TestClient_with_real_Qdrant_and_GPU_HTTP_dependencies",
        "fresh_query_embeddings": 1,
        "fresh_rerank_pairs": body["retrieval_policy"]["candidate_count"],
        "index_vectors": "frozen_805_document_8068_task_vectors",
        "prior_top5_identical": True, "case_id": "F01", "task_reads": task_reads,
        "elapsed_seconds_single_observation_not_benchmark": time.perf_counter() - started,
        "query_sha256": hashlib.sha256(query["text"].encode("utf-8")).hexdigest(),
        "health": health, "response": body,
    }
    with (HERE / "live-search-result.json").open("x", encoding="utf-8") as output:
        json.dump(record, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({key: record[key] for key in [
        "fresh_query_embeddings", "fresh_rerank_pairs", "prior_top5_identical", "task_reads",
        "elapsed_seconds_single_observation_not_benchmark",
    ]}))


if __name__ == "__main__":
    main()
