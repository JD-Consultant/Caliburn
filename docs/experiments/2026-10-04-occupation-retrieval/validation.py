"""Development-only calibration, held-out results, and actual Qdrant correctness."""

import time
from uuid import uuid4

import numpy as np
from qdrant_client import QdrantClient, models

from evaluation import fuse_rankings, ranking_check
from experiment import group_summary, record, save_outcome
from prepare import write_json


def fused(output, depth, constant):
    return fuse_rankings(output["dense"], output["sparse"], depth, constant)


def parameter_and_database_checks(run, corpus, probes, rep, method, documents, queries, outputs):
    docs, doc_sparse, _ = documents
    query_dense, query_sparse, query_tokens = queries
    development = [case for case in probes if case["split"] == "development"]
    grid = []
    for depth in [10, 25, 50, 100]:
        for constant in [2, 20, 60, 100]:
            rows = [record(run, "rrf-grid", case, f"depth{depth}-k{constant}",
                           fused(outputs[case["case_id"]], depth, constant), query_tokens[probes.index(case)], corpus)
                    for case in development]
            grid.append({"depth": depth, "constant": constant, **group_summary(rows)})
    chosen = max(grid, key=lambda row: (row["ndcg_10"], row["mrr"], -row["depth"], -row["constant"]))
    write_json(run / "rrf-grid.json", {"grid": grid, "chosen_development_only": chosen})

    def ranking_for(case):
        return (fused(outputs[case["case_id"]], chosen["depth"], chosen["constant"])
                if method == "rrf" else outputs[case["case_id"]][method])

    # top-k is a candidate shortlist choice, not acceptance or employee fit percentage.
    counts = []
    positives = [case for case in development if case["grades"]]
    for k in [1, 3, 5, 10]:
        covered = sum(any(case["grades"].get(key, 0) >= 2
                          for key, _ in ranking_for(case)[:k]) for case in positives)
        all_primary = sum(all(any(key == target for key, _ in ranking_for(case)[:k])
                              for target, grade in case["grades"].items() if grade == 3)
                          for case in positives)
        counts.append({"k": k, "any_acceptable_cases": covered,
                       "all_primary_roles_cases": all_primary, "positive_cases": len(positives)})
    best_coverage = max(row["all_primary_roles_cases"] for row in counts)
    selected_k = next(row["k"] for row in counts if row["all_primary_roles_cases"] == best_coverage)
    heldout = [record(run, "holdout", case, method, ranking_for(case),
                      query_tokens[probes.index(case)], corpus)
               for case in probes if case["split"] == "holdout"]
    save_outcome(run, "holdout", heldout, {"metrics": group_summary(heldout), "representation": rep,
                    "method": method, "top_k_grid": counts, "selected_k": selected_k,
                    "holdout_any_acceptable_at_selected_k": sum(
                        any(case["grades"].get(key, 0) >= 2 for key, _ in ranking_for(case)[:selected_k])
                        for case in probes if case["split"] == "holdout" and case["grades"]),
                    "holdout_all_primary_at_selected_k": sum(
                        all(any(target == key for key, _ in ranking_for(case)[:selected_k])
                            for target, grade in case["grades"].items() if grade == 3)
                        for case in probes if case["split"] == "holdout" and case["grades"])})

    # Keep threshold on dense cosine even when final retrieval is RRF.
    # A useful reject gate must retain >=80% positive dev cases with zero dev false accepts.
    threshold_grid = []
    for threshold in map(float, np.arange(0.35, 0.901, 0.025)):
        positive_accepts = negative_accepts = 0
        for case in development:
            accepts = outputs[case["case_id"]]["dense"][0][1] >= threshold
            if case["grades"]:
                positive_accepts += accepts
            else:
                negative_accepts += accepts
        threshold_grid.append({"threshold": round(float(threshold), 3),
                               "positive_accepts": positive_accepts, "negative_accepts": negative_accepts})
    viable = [row for row in threshold_grid if row["negative_accepts"] == 0
              and row["positive_accepts"] / len(positives) >= 0.8]
    threshold = viable[0]["threshold"] if viable else None
    decisions = [{"case_id": case["case_id"], "split": case["split"],
                  "expected_abstain": not bool(case["grades"]),
                  "reason": case.get("abstain_reason"),
                  "dense_top1_score": outputs[case["case_id"]]["dense"][0][1],
                  "selected_threshold_accepts": None if threshold is None else
                      outputs[case["case_id"]]["dense"][0][1] >= threshold}
                 for case in probes]
    write_json(run / "threshold.json", {"development_grid": threshold_grid,
               "provisional_threshold": threshold, "decisions": decisions,
               "limitation": "Only 3 dev and 3 holdout negatives; no production confidence or fit probability"})

    database_check(run, corpus, probes, docs, doc_sparse, query_dense, query_sparse,
                   outputs, chosen)


def database_check(run, corpus, probes, docs, doc_sparse, query_dense, query_sparse, outputs, chosen):
    client = QdrantClient(url="http://127.0.0.1:6335", timeout=60, trust_env=False)
    name = f"ocs_eval_{uuid4().hex}"
    # Force a real HNSW graph even on this small set; defaults could remain full-scan.
    client.create_collection(name, vectors_config={"dense": models.VectorParams(
        size=1024, distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams()},
        optimizers_config=models.OptimizersConfigDiff(indexing_threshold=1, default_segment_number=1),
        hnsw_config=models.HnswConfigDiff(m=16, ef_construct=100, full_scan_threshold=10))
    for start in range(0, len(corpus), 64):
        points = [models.PointStruct(id=index, vector={"dense": docs[index].tolist(),
                       "sparse": models.SparseVector(indices=list(doc_sparse[index]),
                                                      values=list(doc_sparse[index].values()))},
                       payload={"ocs_code": corpus[index]["id"], "title": corpus[index]["title"]})
                  for index in range(start, min(start + 64, len(corpus)))]
        client.upsert(name, points, wait=True)
    began = time.monotonic()
    info = client.get_collection(name)
    while (info.indexed_vectors_count or 0) < len(corpus):
        if time.monotonic() - began > 60:
            raise RuntimeError(f"HNSW not fully built: {info.indexed_vectors_count}")
        time.sleep(1)
        info = client.get_collection(name)
    write_json(run / "collection.json", {"name": name, "server": client.info().model_dump(mode="json"),
               "configuration": info.model_dump(mode="json"), "index_wait_seconds": time.monotonic() - began})
    rows = []
    for index, case in enumerate(probes):
        vector = query_dense[index].tolist()
        expected = outputs[case["case_id"]]["dense"]
        expected_scores = dict(expected)
        for exact, ef in [(True, None), (False, 16), (False, 64), (False, 128)]:
            latencies = []
            results = None
            for _ in range(3):
                began = time.perf_counter()
                results = client.query_points(name, query=vector, using="dense", limit=10,
                    with_payload=True, search_params=models.SearchParams(exact=exact, hnsw_ef=ef)).points
                latencies.append(time.perf_counter() - began)
            ids = [result.payload["ocs_code"] for result in results]
            target = {key for key, _ in expected[:10]}
            tie_eligible = {key for key, score in expected if score >= expected[9][1] - 1e-6}
            row = {"case_id": case["case_id"], "split": case["split"], "exact": exact,
                   "hnsw_ef": ef, "top10_set_recall": len(set(ids) & target) / 10,
                   "top10_tie_eligible_fraction": sum(key in tie_eligible for key in ids) / 10,
                   "maximum_score_error": max(abs(result.score - expected_scores[result.payload["ocs_code"]])
                                               for result in results),
                   "milliseconds": [seconds * 1000 for seconds in latencies],
                   "results": [{"id": point.payload["ocs_code"], "score": point.score} for point in results]}
            if exact:
                row["ranking_check"] = ranking_check(
                    [(point.payload["ocs_code"], point.score) for point in results], expected, 10, 1e-5)
            rows.append(row)
            if exact and not row["ranking_check"]["correct"]:
                write_json(run / "database-failure.json", row)
                raise ValueError("Qdrant exact disagreed with complete cosine baseline")
        sp = models.SparseVector(indices=list(query_sparse[index]), values=list(query_sparse[index].values()))
        results = client.query_points(name, prefetch=[
            models.Prefetch(query=vector, using="dense", limit=chosen["depth"],
                            params=models.SearchParams(exact=True)),
            models.Prefetch(query=sp, using="sparse", limit=chosen["depth"])],
            query=models.RrfQuery(rrf=models.Rrf(k=chosen["constant"])),
            limit=10, with_payload=True).points
        expected_fused = fused(outputs[case["case_id"]], chosen["depth"], chosen["constant"])
        scores = dict(expected_fused)
        error = max(abs(point.score - scores.get(point.payload["ocs_code"], 0)) for point in results)
        check = ranking_check([(point.payload["ocs_code"], point.score) for point in results], expected_fused, 10, 1e-6)
        correct = check["correct"]
        rows.append({"case_id": case["case_id"], "split": case["split"], "method": "rrf-exact",
                     "maximum_score_error": error, "ties_accounted_correct": correct, "ranking_check": check,
                     "results": [{"id": point.payload["ocs_code"], "score": point.score} for point in results]})
        # Preserve the mismatch, don't change labels or silently ignore it.
        if not correct:
            write_json(run / "database-rrf-failure.json", rows[-1])
    write_json(run / "database.json", rows)
    dev = [row for row in rows if row["split"] == "development" and not row.get("exact")
           and "hnsw_ef" in row]
    candidates = []
    for ef in [16, 64, 128]:
        selected = [row for row in dev if row["hnsw_ef"] == ef]
        candidates.append({"hnsw_ef": ef,
                           "mean_top10_recall": float(np.mean([row["top10_set_recall"] for row in selected])),
                           "mean_tie_eligible": float(np.mean([row["top10_tie_eligible_fraction"] for row in selected])),
                           "median_ms": float(np.median([value for row in selected for value in row["milliseconds"]]))})
    preferred = next((row for row in candidates if row["mean_tie_eligible"] >= 0.99), None)
    write_json(run / "database-summary.json", {"development_ef_grid": candidates,
        "selected_hnsw_ef": preferred["hnsw_ef"] if preferred else None,
        "exact_queries": len(probes), "rrf_correct_queries": sum(row.get("ties_accounted_correct", False) for row in rows),
        "all_queries": len(probes), "scope": "805 profiles, localhost, no load-test or multi-tenant assurance"})
    client.close()
