"""Independent arithmetic and provenance audit; no selection helpers imported."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PRIOR = HERE.parents[1] / "2026-10-05-memory-public-unit-retrieval/run-01"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def text_sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def check_files(root, entries):
    for relative, expected in entries.items():
        path = root / relative
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        assert path.stat().st_size == expected["bytes"] and actual == expected["sha256"], relative


def independent_merge(pools, queries):
    if len(pools) == 1:
        return [dict(row) for row in pools[0]]
    values = {}
    for query, pool in zip(queries, pools, strict=True):
        assert len({row["id"] for row in pool}) == len(pool)
        for rank, row in enumerate(pool):
            contribution = 1 / (2 + rank)
            value = values.setdefault(row["id"], {"id": row["id"], "fusion_score": 0, "contributions": []})
            value["fusion_score"] += contribution
            value["contributions"].append({"query_id": query, "zero_based_rank": rank, "contribution": contribution})
    return sorted(values.values(), key=lambda row: (-row["fusion_score"], row["id"]))


def main():
    check_files(ROOT, read(HERE / "input-manifest.json")["inputs"])
    prior_seal = read(PRIOR / "artifact-hashes.json")
    check_files(PRIOR, prior_seal["files"])
    queries = {row["query_id"]: row for row in read(PRIOR / "queries.json")}
    documents = {row["id"]: row for row in read(PRIOR / "corpus.json")}
    cases = {row["case_id"]: row for row in read(PRIOR / "cases.json")}
    pairs = {}
    for line in (PRIOR / "rerank-pairs.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        key = (row["query_id"], row["id"])
        assert key not in pairs
        assert row["query_sha256"] == text_sha(queries[key[0]]["text"])
        assert row["document_sha256"] == text_sha(documents[key[1]]["text"])
        assert math.isfinite(row["logit"]) and row["logit"] == max(w["logit"] for w in row["windows"])
        pairs[key] = row["logit"]
    base = {(row["case_id"], row["method"]): row for row in read(PRIOR / "results.json")}
    old_r = {(row["case_id"], row["method"]): row for row in read(PRIOR / "rerank-results.json")}
    grades = {}
    for result in read(PRIOR / "graded-results.json"):
        for row in result["selected"]:
            key = (result["case_id"], row["id"])
            if key in grades:
                assert grades[key] == row["judgment"]
            grades[key] = row["judgment"]
    expected_pairs, selected_pairs, known_pairs, missing_pairs = set(), set(), set(), set()
    union_by_query = {row["query_id"]: row for row in read(HERE / "query-unions.json")}
    result_rows = read(HERE / "results.json")
    assert len(result_rows) == 16
    for result in result_rows:
        case_id, variant = result["case_id"], result["method"].split("-")[0]
        dense, task = base[(case_id, variant + "-D")], base[(case_id, variant + "-T")]
        assert result["query_ids"] == dense["query_ids"] == task["query_ids"]
        expected_pools = []
        for qid, dpool, tpool in zip(result["query_ids"], dense["query_pools"], task["query_pools"], strict=True):
            assert queries[qid]["case_id"] == case_id and queries[qid]["input_variant"] == variant
            assert len(dpool) == len(tpool) == 20
            provenance = {}
            for route, pool in (("D", dpool), ("T", tpool)):
                assert len({row["id"] for row in pool}) == 20
                for rank, row in enumerate(pool, 1):
                    provenance.setdefault(row["id"], {})[route] = rank
            full_pool = [{"id": ident, "route_ranks": routes, "score": pairs[(qid, ident)]}
                         for ident, routes in provenance.items()]
            full_pool.sort(key=lambda row: (-row["score"], row["id"]))
            assert union_by_query[qid]["candidates"] == full_pool
            assert union_by_query[qid]["parents"] == len(full_pool)
            expected_pools.append(full_pool)
            expected_pairs.update((qid, row["id"]) for row in full_pool)
        assert result["query_pools"] == expected_pools
        merged = independent_merge(expected_pools, result["query_ids"])
        assert result["merged_ranking"] == merged
        assert [row["id"] for row in result["selected"]] == [row["id"] for row in merged[:5]]
        assert len({row["id"] for row in result["selected"]}) == 5
        for rank, row in enumerate(result["selected"], 1):
            key = (case_id, row["id"])
            selected_pairs.add(key)
            assert row["rank"] == rank and row["name"] == documents[key[1]]["title"]
            if key in grades:
                assert row["judgment"] == grades[key] and row["judgment_reused"]
                for evidence in row["judgment"]["evidence"]:
                    assert evidence["employee_quote"] in cases[case_id]["employee_statement"]
                    assert evidence["reference_quote"] in documents[key[1]]["text"]
                known_pairs.add(key)
            else:
                assert row["judgment"] is None and not row["judgment_reused"]
                missing_pairs.add(key)
    assert expected_pairs == set(pairs)
    assert len(union_by_query) == 20
    for key, previous in old_r.items():
        source = base[(key[0], key[1][:-2])]
        pools = [sorted([{"id": row["id"], "score": pairs[(qid, row["id"])]} for row in pool],
                        key=lambda row: (-row["score"], row["id"]))
                 for qid, pool in zip(source["query_ids"], source["query_pools"], strict=True)]
        assert pools == previous["query_pools"]
        assert independent_merge(pools, source["query_ids"]) == previous["merged_ranking"]
    jobs = read(HERE / "new-judge-jobs.json")
    assert {(j["case_id"], j["document_id"]) for j in jobs} == missing_pairs
    for job in jobs:
        assert job["employee"] == cases[job["case_id"]]["employee_statement"]
        assert job["reference"] == documents[job["document_id"]]["text"]
    used = read(HERE / "reused-judgments.json")
    assert {(j["case_id"], j["document_id"]) for j in used} == known_pairs
    for row in used:
        assert row["employee_sha256"] == text_sha(cases[row["case_id"]]["employee_statement"])
        assert row["document_sha256"] == text_sha(documents[row["document_id"]]["text"])
        assert row["judgment"] == grades[(row["case_id"], row["document_id"])]
    workload = read(HERE / "workload.json")
    assert workload["new_union_pairs"] == len(expected_pairs)
    assert workload["old_M_R_pairs"] == 400
    assert workload["pair_count_multiplier"] == len(expected_pairs) / 400
    assert not workload["fresh_latency_measured"] and workload["new_external_cost_usd"] == 0
    summary = read(HERE / "result-summary.json")
    assert summary["unique_selected_pairs"] == len(selected_pairs)
    assert summary["reused_grades"] == len(known_pairs) and summary["missing_grades"] == len(missing_pairs)
    result = {"groups": len(result_rows), "positions": 80, "query_pools": len(union_by_query),
              "cached_source_bound_pairs": len(expected_pairs), "unique_selected_pairs": len(selected_pairs),
              "known_grades": len(known_pairs), "missing_grades": len(missing_pairs),
              "old_rerank_controls_unchanged": len(old_r), "prior_sealed_files_unchanged": len(prior_seal["files"]),
              "fresh_gpu_or_db_time_measured": False, "provider_calls": 0,
              "scope": "cached finite-case candidate retention ablation; not holdout or JD completeness"}
    with (HERE / "verification.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
