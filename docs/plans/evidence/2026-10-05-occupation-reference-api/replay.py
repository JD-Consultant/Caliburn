"""Replay the new API with frozen sources/vectors/logits; no provider/network calls."""

from __future__ import annotations

import hashlib
import argparse
import json
from contextlib import closing
from pathlib import Path

import httpx
import numpy as np
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from jd_ocs_indexer.api.app import create_app
from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.embeddings.http_embedder import HttpEmbedder
from jd_ocs_indexer.references.service import ReferenceSearch
from jd_ocs_indexer.references.source import build_reference
from jd_ocs_indexer.references.store import QdrantReferenceStore, index_references
from jd_ocs_indexer.reranking.http_reranker import MODEL, REVISION, HttpReranker

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXPERIMENTS = ROOT / "docs/experiments"
PUBLIC = EXPERIMENTS / "2026-10-04-public-chunk-retrieval/run-01"
MEMORY = EXPERIMENTS / "2026-10-05-memory-public-unit-retrieval/run-01"
UNION = EXPERIMENTS / "2026-10-05-rerank-union-candidate-replay/run-01"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qdrant-url")
    parser.add_argument("--collection", default="reference_api_replay")
    parser.add_argument("--output", default="replay-result.json")
    arguments = parser.parse_args()
    inputs = [EXPERIMENTS / "2026-10-04-occupation-retrieval/corpus.json",
              PUBLIC / "chunks.json", MEMORY / "query-vectors.json", MEMORY / "queries.json",
              MEMORY / "rerank-pairs.jsonl", UNION / "results.json"]
    sources = read(inputs[0])
    bodies = {item["id"]: item["text"] for item in read(MEMORY / "corpus.json")}
    documents = []
    for item in sources:
        source_bytes = (ROOT / item["source"]).read_bytes()
        if hashlib.sha256(source_bytes).hexdigest() != item["source_sha256"]:
            raise ValueError("frozen source differs: " + item["id"])
        document = build_reference(source_bytes.decode("utf-8"), source_file=item["source"])
        if document.document_text != bodies[item["id"]]:
            raise ValueError("D body differs: " + item["id"])
        documents.append(document)
    frozen_chunks = read(PUBLIC / "chunks.json")
    task_chunks = [item for item in frozen_chunks if item["representation"] == "task"]
    actual_bodies = sorted((doc.ocs_code, chunk.text) for doc in documents for chunk in doc.chunks)
    expected_bodies = sorted((item["parent_id"], item["text"]) for item in task_chunks)
    if actual_bodies != expected_bodies:
        raise ValueError("T bodies differ")
    vectors = {}
    for path in sorted((PUBLIC / "vector-batches").glob("*.npz")):
        inputs.append(path)
        with np.load(path, allow_pickle=False) as batch:
            vectors.update({str(key): vector.tolist() for key, vector in zip(batch["hashes"], batch["dense"], strict=True)})
    queries = [item for item in read(MEMORY / "queries.json") if item["input_variant"] == "O"]
    query_vectors = {item["query_id"]: item["dense"] for item in read(MEMORY / "query-vectors.json")}
    vectors.update({sha(item["text"]): query_vectors[item["query_id"]] for item in queries})
    logits = {}
    for line in (MEMORY / "rerank-pairs.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        logits[item["query_sha256"], item["document_sha256"]] = item["logit"]

    def handler(request):
        body = json.loads(request.content)
        if request.url.path == "/embed":
            return httpx.Response(200, json={
                "model": "BAAI/bge-m3", "dim": 1024, "revision": 1,
                "model_revision": "5617a9f61b028005a4858fdac845db406aefb181",
                "embeddings": [{"dense": vectors[sha(text)]} for text in body["texts"]],
            })
        return httpx.Response(200, json={"model": MODEL, "revision": REVISION,
            "scores": [logits[sha(body["query"]), sha(text)] for text in body["documents"]]})

    expected = {item["case_id"]: [hit["id"] for hit in item["selected"]]
                for item in read(UNION / "results.json") if item["method"] == "O-U-R"}
    records = []
    database_client = QdrantClient(url=arguments.qdrant_url, timeout=120, trust_env=False) if arguments.qdrant_url else QdrantClient(":memory:")
    with closing(database_client) as database, httpx.Client(
        base_url="http://frozen-model", transport=httpx.MockTransport(handler),
    ) as model_client:
        embedder = HttpEmbedder("http://frozen-model", client=model_client)
        points = index_references(database, arguments.collection, documents, embedder)
        search = ReferenceSearch(QdrantReferenceStore(database, arguments.collection, embedder.signature),
                                 embedder, HttpReranker("http://frozen-model", client=model_client))
        app = create_app(settings=load_settings(), client=database, embedder=embedder, reference_search=search)
        with TestClient(app) as client:
            for query in queries:
                response = client.post("/occupation-references:search", json={"query": query["text"]})
                if response.status_code != 200:
                    raise ValueError("API replay failed: " + str(response.status_code))
                body = response.json()
                selected = [hit["reference"]["ocs_code"] for hit in body["references"]]
                if selected != expected[query["case_id"]]:
                    raise ValueError(f"rank differs for {query['case_id']}: {selected}")
                for hit in body["references"]:
                    reference = hit["reference"]
                    base = f"/occupation-references/{reference['reference_id']}"
                    if client.get(base).json() != reference:
                        raise ValueError("fixed source read differs from search")
                    for unit in reference["units"]:
                        for task in unit["tasks"]:
                            task_response = client.get(base + "/tasks/" + task["task_id"])
                            if task_response.status_code != 200:
                                raise ValueError("catalog task cannot be read")
                records.append({"case_id": query["case_id"], "query_sha256": sha(query["text"]),
                                "response": body, "prior_top5_identical": True})
    result = {"scope": "new_API_Qdrant_cached_vectors_and_logits_no_fresh_provider",
              "backend": "server" if arguments.qdrant_url else "QdrantLocal",
              "collection": arguments.collection,
              "source_documents": len(documents), "task_chunks": len(task_chunks), "indexed_points": points,
              "groups": len(records), "records": records,
              "input_hashes": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}}
    with (HERE / arguments.output).open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({"source_documents": len(documents), "task_chunks": len(task_chunks),
                      "groups": len(records), "prior_top5_identical": True}))


if __name__ == "__main__":
    main()
