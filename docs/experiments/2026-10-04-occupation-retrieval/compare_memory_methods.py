"""Exploratory correction: compare retrieval on the actual selected whole B2."""

import json
import sys

from evaluation import fuse_rankings
from experiment import Embeddings, group_summary, record, save_outcome, sorted_ranking, sparse_scores
from prepare import HERE, sha, write_json


def compare(run_name):
    run = HERE / run_name
    run.mkdir(exist_ok=False)
    corpus = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    model = Embeddings()
    queries, sparse_queries, tokens = model.get([case["inputs"]["B_b2"] for case in cases], "selected-B2")
    write_json(run / "manifest.json", {"purpose": "Whole B2 comparison after observing short-probe mismatch; exploratory",
        "base_manifest_sha256": sha(HERE / "manifest.json"), "runtime": model.runtime,
        "script_sha256": sha(HERE / "compare_memory_methods.py"),
        "fixed_rrf_depth": 50, "fixed_rrf_constant": 60})
    rows = []
    for rep in ["top", "topks"]:
        docs, sparse_docs, _ = model.get([row["texts"][rep] for row in corpus], rep)
        for case, query, sparse, length in zip(cases, queries, sparse_queries, tokens, strict=True):
            dense_ranking = sorted_ranking(docs @ query, corpus)
            sparse_ranking = sorted_ranking(sparse_scores(sparse, sparse_docs), corpus)
            for method, ranking in [("dense", dense_ranking), ("sparse", sparse_ranking),
                                    ("rrf", fuse_rankings(dense_ranking, sparse_ranking, 50, 60))]:
                rows.append(record(run, "memory-method", case, rep + "-" + method, ranking, length, corpus))
    summaries = {arm: group_summary([row for row in rows if row["arm"] == arm])
                 for arm in sorted({row["arm"] for row in rows})}
    summaries["provisional_choice"] = max(summaries, key=lambda arm: (
        summaries[arm]["ndcg_10"], summaries[arm]["mrr"]))
    save_outcome(run, "memory-method", rows, summaries)
    write_json(run / "cache-reference.json", {"path": model.path.relative_to(HERE).as_posix(),
        "sha256": sha(model.path), "byte_prefix_length": model.path.stat().st_size})
    model.client.close()


if __name__ == "__main__":
    compare(sys.argv[1])
