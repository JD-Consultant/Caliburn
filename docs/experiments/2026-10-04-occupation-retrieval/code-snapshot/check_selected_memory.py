"""Check the chosen retrieval with the earlier whole-employee B2 snapshots."""

import json
import sys
from pathlib import Path

from qdrant_client import QdrantClient, models

from evaluation import fuse_rankings, ranking_check
from experiment import Embeddings, group_summary, record, save_outcome, sorted_ranking, sparse_scores
from prepare import HERE, write_json


def check(run):
    complete = json.loads((run / "complete.json").read_text(encoding="utf-8"))
    selected = json.loads((run / "rrf-grid.json").read_text(encoding="utf-8"))["chosen_development_only"]
    corpus = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    collection = json.loads((run / "collection.json").read_text(encoding="utf-8"))["name"]
    output = run / "selected-memory-summary.json"
    if output.exists():
        raise ValueError("Supplemental outcomes already exist")
    model = Embeddings()
    rep = complete["selected_representation"]
    docs, sparse_docs, _ = model.get([row["texts"][rep] for row in corpus], "selected-corpus")
    queries, sparse_queries, tokens = model.get([case["inputs"][complete["selected_input"]] for case in cases], "selected-B2")
    client = QdrantClient(url="http://127.0.0.1:6335", timeout=60, trust_env=False)
    rows = []
    checks = []
    for case, dense, sparse, length in zip(cases, queries, sparse_queries, tokens, strict=True):
        dense_rank = sorted_ranking(docs @ dense, corpus)
        sparse_rank = sorted_ranking(sparse_scores(sparse, sparse_docs), corpus)
        if complete["selected_method"] == "dense":
            expected = dense_rank
            results = client.query_points(collection, query=dense.tolist(), using="dense", limit=10,
                search_params=models.SearchParams(exact=True), with_payload=True).points
        else:
            expected = fuse_rankings(dense_rank, sparse_rank, selected["depth"], selected["constant"])
            results = client.query_points(collection, prefetch=[
                models.Prefetch(query=dense.tolist(), using="dense", limit=selected["depth"],
                                params=models.SearchParams(exact=True)),
                models.Prefetch(query=models.SparseVector(indices=list(sparse), values=list(sparse.values())),
                                using="sparse", limit=selected["depth"])],
                query=models.RrfQuery(rrf=models.Rrf(k=selected["constant"])), limit=10, with_payload=True).points
        actual = [(point.payload["ocs_code"], point.score) for point in results]
        checks.append({"case_id": case["case_id"], **ranking_check(actual, expected, 10)})
        rows.append(record(run, "selected-memory", case,
                           "B2+" + rep + "+" + complete["selected_method"] + "-exact", actual, length, corpus))
    save_outcome(run, "selected-memory", rows, {"metrics": group_summary(rows), "database_checks": checks,
                 "scope": "Same pilot employee snapshots under selected method; not unseen-employee validation"})
    write_json(run / "selected-memory-script.json", {"script": Path(__file__).name,
        "sha256": __import__("hashlib").sha256(Path(__file__).read_bytes()).hexdigest()})
    model.client.close()
    client.close()


if __name__ == "__main__":
    check(HERE / sys.argv[1])
