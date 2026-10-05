"""Isolated cached-score selection replay; no provider/service imports."""
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXPERIMENTS = HERE.parents[1]
PRIOR = EXPERIMENTS / "2026-10-05-memory-public-unit-retrieval/run-01"
FUSION = EXPERIMENTS / "2026-10-04-query-chunk-cross-retrieval/run-01/fusion.py"
VALIDATION = EXPERIMENTS / "2026-10-04-a-interview-occupation-retrieval/run-01/pipeline.py"
MODEL_SHA = "d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286"
REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dump(name, value):
    with (HERE / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def union_candidates(dense, task):
    candidates = {}
    for route, pool in (("D", dense), ("T", task)):
        if len({row["id"] for row in pool}) != len(pool):
            raise ValueError("duplicate parent in route")
        for rank, row in enumerate(pool, 1):
            item = candidates.setdefault(row["id"], {"id": row["id"], "route_ranks": {}})
            item["route_ranks"][route] = rank
    return [candidates[key] for key in sorted(candidates)]


def order_by_logit(candidates, scores):
    ranked = []
    for row in candidates:
        if row["id"] not in scores:
            raise ValueError("missing score for source-bound query")
        score = scores[row["id"]]
        if not math.isfinite(score):
            raise ValueError("logit must be finite")
        ranked.append({**row, "score": score})
    return sorted(ranked, key=lambda row: (-row["score"], row["id"]))


def checked_logit(row, query_hash, document_hash):
    if row["query_sha256"] != query_hash or row["document_sha256"] != document_hash:
        raise ValueError("cached source hash mismatch")
    if not math.isfinite(row["logit"]):
        raise ValueError("logit must be finite")
    return row["logit"]


def check_prior():
    manifest = read(PRIOR / "artifact-hashes.json")
    for relative, expected in manifest["files"].items():
        path = PRIOR / relative
        if path.stat().st_size != expected["bytes"] or sha(path) != expected["sha256"]:
            raise ValueError("prior sealed artifact changed: " + relative)
    return {"files_checked": len(manifest["files"]), "mismatches": 0,
            "manifest_sha256": sha(PRIOR / "artifact-hashes.json")}


def freeze():
    before = check_prior()
    files = [PRIOR / name for name in (
        "results.json", "rerank-results.json", "rerank-pairs.jsonl", "queries.json",
        "corpus.json", "cases.json", "graded-results.json", "gpu-runtime.json",
        "verification-final.json", "artifact-hashes.json")]
    files += [FUSION, VALIDATION, HERE / "protocol.md", HERE / "replay.py",
              HERE / "test_replay.py", HERE / "verify.py",
              ROOT / "docs/plans/2026-10-05-rerank-union-candidate-replay.md"]
    dump("input-manifest.json", {"inputs": {
        path.relative_to(ROOT).as_posix(): {"sha256": sha(path), "bytes": path.stat().st_size}
        for path in files}, "model_sha256": MODEL_SHA, "model_revision": REVISION,
        "score_kind": "previously observed FP16 full-document cross-encoder quality logit",
        "candidate_depth_each_route": 20, "final_max_documents": 5,
        "query_fusion": "zero-based RRF k2 across full reranked union pools"})
    dump("prior-seal-check-before.json", before)
    print(f"Frozen {len(files)} input/code files; {before['files_checked']} prior seals valid")


def check_manifest():
    for relative, expected in read(HERE / "input-manifest.json")["inputs"].items():
        path = ROOT / relative
        if path.stat().st_size != expected["bytes"] or sha(path) != expected["sha256"]:
            raise ValueError("frozen input changed: " + relative)


def main():
    check_manifest()
    fusion = load("prior_union_fusion", FUSION).merge_pools
    validate = load("prior_union_validation", VALIDATION).validate_judgment
    runtime = read(PRIOR / "gpu-runtime.json")
    assert runtime["model_sha256"] == MODEL_SHA and runtime["revision"] == REVISION
    queries = {row["query_id"]: row for row in read(PRIOR / "queries.json")}
    docs = {row["id"]: row for row in read(PRIOR / "corpus.json")}
    cases = {row["case_id"]: row for row in read(PRIOR / "cases.json")}
    pair_rows = [json.loads(line) for line in (PRIOR / "rerank-pairs.jsonl").read_text(encoding="utf-8").splitlines()]
    pairs = {(row["query_id"], row["id"]): row for row in pair_rows}
    assert len(pairs) == len(pair_rows)
    for (qid, ident), row in pairs.items():
        checked_logit(row, text_sha(queries[qid]["text"]), text_sha(docs[ident]["text"]))
    scores = {key: row["logit"] for key, row in pairs.items()}
    base = read(PRIOR / "results.json")
    prior_r = {(row["case_id"], row["method"]): row for row in read(PRIOR / "rerank-results.json")}
    controls = []
    for result in base:
        pools = [order_by_logit([{"id": p["id"]} for p in pool],
                  {p["id"]: scores[(qid, p["id"])] for p in pool})
                 for qid, pool in zip(result["query_ids"], result["query_pools"], strict=True)]
        previous = prior_r[(result["case_id"], result["method"] + "-R")]
        assert pools == previous["query_pools"]
        assert fusion(pools, result["query_ids"]) == previous["merged_ranking"]
        controls.append({"case_id": result["case_id"], "method": previous["method"], "identical": True})
    base_map = {(row["case_id"], row["method"]): row for row in base}
    grade_book = {}
    for result in read(PRIOR / "graded-results.json"):
        for selected in result["selected"]:
            key = (result["case_id"], selected["id"])
            if key in grade_book:
                assert grade_book[key]["judgment"] == selected["judgment"]
            grade_book[key] = selected
    new_results, missing_jobs, union_records, selected_pairs = [], [], [], set()
    comparisons, used = [], {}
    for case_id, case in cases.items():
        for variant in ("O", "B2"):
            dense, task = base_map[(case_id, variant + "-D")], base_map[(case_id, variant + "-T")]
            assert dense["query_ids"] == task["query_ids"]
            pools = []
            for qid, dpool, tpool in zip(dense["query_ids"], dense["query_pools"], task["query_pools"], strict=True):
                assert len(dpool) == len(tpool) == 20
                union = union_candidates(dpool, tpool)
                ranked = order_by_logit(union, {row["id"]: scores[(qid, row["id"])] for row in union})
                pools.append(ranked)
                union_records.append({"case_id": case_id, "variant": variant, "query_id": qid,
                    "parents": len(union), "old_M_R_parents": 20, "candidates": ranked})
            merged = fusion(pools, dense["query_ids"])
            selected = []
            for rank, row in enumerate(merged[:5], 1):
                ident = row["id"]
                key = (case_id, ident)
                item = {**row, "name": docs[ident]["title"], "rank": rank}
                if key in grade_book:
                    original = grade_book[key]
                    validate(original["judgment"], case["employee_statement"], docs[ident]["text"])
                    item.update({"judgment": original["judgment"], "judgment_reused": True,
                        "quote_recovered_in_prior": original["quote_recovered"],
                        "judgment_source": (PRIOR / "graded-results.json").relative_to(ROOT).as_posix()})
                    used[key] = {"case_id": case_id, "document_id": ident,
                        "employee_sha256": text_sha(case["employee_statement"]),
                        "document_sha256": text_sha(docs[ident]["text"]), "judgment": original["judgment"]}
                else:
                    item.update({"judgment": None, "judgment_reused": False})
                    if key not in selected_pairs:
                        job = {"job_id": f"pending-{len(missing_jobs)+1:03}", "case_id": case_id,
                               "document_id": ident, "employee": case["employee_statement"],
                               "main_facets": case["major_work_facets"], "reference": docs[ident]["text"],
                               "source_group": case["source_group"]}
                        if "interview_context" in case:
                            job["interview_context"] = case["interview_context"]
                        missing_jobs.append(job)
                selected_pairs.add(key)
                selected.append(item)
            previous = prior_r[(case_id, variant + "-M-R")]
            old_ids = [row["id"] for row in previous["selected"]]
            new_ids = [row["id"] for row in selected]
            new_results.append({"case_id": case_id, "method": variant + "-U-R", "query_ids": dense["query_ids"],
                "query_pools": pools, "merged_ranking": merged, "selected": selected})
            comparisons.append({"case_id": case_id, "method": variant + "-U-R", "baseline": variant + "-M-R",
                "same_top5_sequence": old_ids == new_ids, "old_ids": old_ids, "new_ids": new_ids,
                "added_ids": [ident for ident in new_ids if ident not in old_ids],
                "removed_ids": [ident for ident in old_ids if ident not in new_ids]})
    union_pair_set = {(row["query_id"], p["id"]) for row in union_records for p in row["candidates"]}
    assert union_pair_set == set(pairs), "union and prior source-bound cache must cover exactly the same pairs"
    cost = {"queries": len(union_records), "new_union_pairs": len(union_pair_set),
            "old_M_R_pairs": 20 * len(union_records),
            "pair_count_multiplier": len(union_pair_set) / (20 * len(union_records)),
            "new_gpu_inferences": 0, "new_db_queries": 0, "new_provider_calls": 0,
            "new_external_cost_usd": 0, "fresh_latency_measured": False,
            "scope": "candidate-pair workload only; cached replay has no measured fresh GPU/DB/end-to-end latency"}
    dump("results.json", new_results)
    dump("query-unions.json", union_records)
    dump("control-checks.json", controls)
    dump("comparison.json", comparisons)
    dump("reused-judgments.json", list(used.values()))
    dump("new-judge-jobs.json", missing_jobs)
    dump("workload.json", cost)
    dump("result-summary.json", {"cases": len(cases), "methods": 2, "positions": len(new_results) * 5,
        "unique_selected_pairs": len(selected_pairs), "reused_grades": len(used), "missing_grades": len(missing_jobs),
        "prior_controls_unchanged": len(controls), "query_union_min": min(row["parents"] for row in union_records),
        "query_union_max": max(row["parents"] for row in union_records),
        "scope": "observed synthetic cases; cached scores and reused judgments; not holdout or JD completeness"})
    print(f"Replayed {len(new_results)} groups; {len(selected_pairs)} unique selected pairs, {len(missing_jobs)} ungraded; {len(controls)} identical controls")


if __name__ == "__main__":
    if sys.argv[1:] == ["--freeze"]:
        freeze()
    elif not sys.argv[1:]:
        main()
    else:
        raise SystemExit("Usage: replay.py [--freeze]")
