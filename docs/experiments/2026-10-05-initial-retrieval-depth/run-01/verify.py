"""Independent parent aggregation, prefix, target and facet audit."""
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PRIOR = HERE.parents[1] / "2026-10-05-memory-public-unit-retrieval/run-01"
UNION = HERE.parents[1] / "2026-10-05-rerank-union-candidate-replay/run-01"
EXCLUDED = {("F05", "AVA2172-001v4"), ("H03", "MMP1324-001v4")}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_files(root, entries):
    for relative, expected in entries.items():
        path = root / relative
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        assert path.stat().st_size == expected["bytes"] and actual == expected["sha256"], relative


def main(output="verification.json"):
    check_files(ROOT, read(HERE / "input-manifest.json")["inputs"])
    sealed = 0
    for directory in (PRIOR, UNION):
        entries = read(directory / "artifact-hashes.json")["files"]
        check_files(directory, entries)
        sealed += len(entries)
    queries = {q["query_id"]: q for q in read(PRIOR / "queries.json")}
    cases = {c["case_id"]: c for c in read(PRIOR / "cases.json")}
    docs = {d["id"]: d for d in read(PRIOR / "corpus.json")}
    ranks, scores, chunk_count = {}, {}, 0
    for row in read(PRIOR / "all-rankings.json"):
        key = (row["query_id"], row["representation"])
        assert key not in ranks
        maximum, counts = {}, {}
        for chunk in row["chunk_scores"]:
            ident, score = chunk["parent_id"], chunk["score"]
            assert math.isfinite(score) and ident in docs
            maximum[ident] = max(maximum.get(ident, float("-inf")), score)
            counts[ident] = counts.get(ident, 0) + 1
            chunk_count += 1
        order = sorted(maximum, key=lambda ident: (-maximum[ident], ident))
        assert len(order) == 805 and set(order) == set(docs)
        assert order == [p["id"] for p in row["parents"]]
        for p in row["parents"]:
            assert p["score"] == p["max_score"] == maximum[p["id"]]
            assert p["available_chunks"] == counts[p["id"]]
        ranks[key] = order
        scores[key] = maximum
    assert len(ranks) == 40 and chunk_count == 177460
    book = {}
    for r in read(PRIOR / "graded-results.json"):
        for p in r["selected"]:
            key = (r["case_id"], p["id"])
            if key in book:
                assert p["judgment"] == book[key]["judgment"]
            book[key] = p
    expected_keys = {key for key, p in book.items() if p["judgment"]["grade"] == 3}
    assert len(book) == 158 and len(expected_keys) == 12
    targets = read(HERE / "targets.json")
    assert {(t["case_id"], t["id"]) for t in targets} == expected_keys
    for t in targets:
        key = (t["case_id"], t["id"])
        assert t["judgment"] == book[key]["judgment"]
        assert t["main_work"] == t["judgment"]["main_work"]
        assert set(t["main_work"]) <= set(cases[key[0]]["major_work_facets"])
        assert t["sensitivity_excluded"] == (key in EXCLUDED)
        assert t["employee_sha256"] == digest(cases[key[0]]["employee_statement"])
        assert t["document_sha256"] == digest(docs[key[1]]["text"])
        for evidence in t["judgment"]["evidence"]:
            assert evidence["employee_quote"] in cases[key[0]]["employee_statement"]
            assert evidence["reference_quote"] in docs[key[1]]["text"]
    previous_unions = {r["query_id"]: {p["id"] for p in r["candidates"]} for r in read(UNION / "query-unions.json")}
    result_rows = read(HERE / "results.json")
    assert len(result_rows) == 48
    results = {(r["case_id"], r["variant"], r["depth_each_route"]): r for r in result_rows}
    assert len(results) == 48
    controls = set()
    for key, result in results.items():
        case_id, variant, depth = key
        qids = [qid for qid, q in queries.items() if q["case_id"] == case_id and q["input_variant"] == variant]
        assert result["query_ids"] == qids and depth in (20, 40, 80)
        candidates, pairs = set(), 0
        for qid, pool in zip(qids, result["query_pools"], strict=True):
            assert pool["query_id"] == qid
            for label, rep in (("D", "document"), ("T", "task")):
                expected = [{"rank": i, "id": ident, "score": scores[(qid, rep)][ident]}
                            for i, ident in enumerate(ranks[(qid, rep)][:depth], 1)]
                assert pool[label] == expected
            union = set(ranks[(qid, "document")][:depth]) | set(ranks[(qid, "task")][:depth])
            assert pool["union_ids"] == sorted(union) and pool["union_parents"] == len(union)
            candidates.update(union)
            pairs += len(union)
            if depth == 20:
                assert union == previous_unions[qid]
                controls.add(qid)
        assert result["employee_candidate_ids"] == sorted(candidates)
        assert result["employee_unique_parents"] == len(candidates)
        assert result["rerank_pair_workload"] == pairs
        own = [t for t in targets if t["case_id"] == case_id]
        for sensitivity in (False, True):
            target_list = [t for t in own if not sensitivity or not t["sensitivity_excluded"]]
            prefix = "clear_" if sensitivity else "known_"
            reference_key = "clear_grade3_sensitivity" if sensitivity else "known_grade3"
            facet_key = "clear_work_facets_sensitivity" if sensitivity else "known_work_facets"
            ids = [t["id"] for t in target_list]
            retained = [ident for ident in ids if ident in candidates]
            assert result[reference_key] == {"known_ids": ids, "retained_ids": retained,
                "missing_ids": [ident for ident in ids if ident not in candidates],
                "known_coverage": len(retained) / len(ids) if ids else None}
            facets = cases[case_id]["major_work_facets"]
            known = {f for t in target_list for f in t["main_work"]}
            supported = {f for t in target_list if t["id"] in candidates for f in t["main_work"]}
            assert result[facet_key] == {"known": [f for f in facets if f in known],
                "retained": [f for f in facets if f in supported],
                "missing": [f for f in facets if f in known - supported],
                "unassessed": [f for f in facets if f not in known],
                "known_coverage": len(supported) / len(known) if known else None}
        if depth == 20:
            assert set(result["employee_candidate_ids"]) <= set(results[(case_id, variant, 40)]["employee_candidate_ids"])
        if depth == 40:
            assert set(result["employee_candidate_ids"]) <= set(results[(case_id, variant, 80)]["employee_candidate_ids"])
    assert len(controls) == 20
    expected_minima = {}
    diagnostic_rows = read(HERE / "target-ranks.json")
    assert len(diagnostic_rows) == 24
    for r in diagnostic_rows:
        qids = results[(r["case_id"], r["variant"], 20)]["query_ids"]
        paths = [{"query_id": qid,
                  "D": {"rank": ranks[(qid, "document")].index(r["id"]) + 1, "score": scores[(qid, "document")][r["id"]]},
                  "T": {"rank": ranks[(qid, "task")].index(r["id"]) + 1, "score": scores[(qid, "task")][r["id"]]}} for qid in qids]
        assert r["paths"] == paths
        best = min(p[route]["rank"] for p in paths for route in ("D", "T"))
        assert r["minimum_N"] == best
        expected_minima[(r["case_id"], r["variant"], r["id"])] = best
    minimum_rows = read(HERE / "minimum-depth.json")
    assert len(minimum_rows) == 16
    for r in minimum_rows:
        own = [t for t in targets if t["case_id"] == r["case_id"]]
        clear = [t for t in own if not t["sensitivity_excluded"]]
        for target_list, nkey, fkey in ((own, "minimum_N_all_known_grade3", "work_facets"),
                                       (clear, "minimum_N_clear_grade3", "clear_work_facets")):
            required = [expected_minima[(r["case_id"], r["variant"], t["id"])] for t in target_list]
            assert r[nkey] == (max(required) if required else None)
            values = {f: min((expected_minima[(r["case_id"], r["variant"], t["id"])] for t in target_list if f in t["main_work"]), default=None)
                      for f in cases[r["case_id"]]["major_work_facets"]}
            numbers = [n for n in values.values() if n is not None]
            assert r[fkey] == {"facets": values, "minimum_N_for_known_facets": max(numbers) if numbers else None,
                              "unassessed_facets": [f for f, n in values.items() if n is None]}
    summaries = read(HERE / "summary.json")
    assert len(summaries) == 6
    for s in summaries:
        own = [r for r in result_rows if r["variant"] == s["variant"] and r["depth_each_route"] == s["depth_each_route"]]
        assert s["rerank_pair_workload"] == sum(r["rerank_pair_workload"] for r in own)
        assert s["employee_parent_count_sum"] == sum(r["employee_unique_parents"] for r in own)
        assert s["query_count"] == sum(len(r["query_ids"]) for r in own)
        for key in ("known_grade3", "clear_grade3_sensitivity", "known_work_facets", "clear_work_facets_sensitivity"):
            reference = "grade3" in key
            a, b = ("retained_ids", "known_ids") if reference else ("retained", "known")
            expected = {"retained": sum(len(r[key][a]) for r in own), "known": sum(len(r[key][b]) for r in own),
                        "unassessed_case_count": sum(r[key]["known_coverage"] is None for r in own)}
            if not reference:
                expected["unassessed_facet_count"] = sum(len(r[key]["unassessed"]) for r in own)
            assert s[key] == expected
    cached = {(qid, ident) for qid, ids in previous_unions.items() for ident in ids}
    missing = read(HERE / "missing-rerank-cache-pairs.json")
    for depth in (20, 40, 80):
        expected = set()
        for r in result_rows:
            if r["depth_each_route"] == depth:
                for pool in r["query_pools"]:
                    expected.update((pool["query_id"], ident) for ident in pool["union_ids"] if (pool["query_id"], ident) not in cached)
        rows = missing[str(depth)]
        assert len(rows) == len(expected) and {(r["query_id"], r["document_id"]) for r in rows} == expected
        for r in rows:
            assert r["query_sha256"] == digest(queries[r["query_id"]]["text"])
            assert r["document_sha256"] == digest(docs[r["document_id"]]["text"])
    scope = read(HERE / "scope.json")
    assert scope["groups"] == 48 and not scope["fresh_latency_measured"] and not scope["full_corpus_qrels_available"]
    assert scope["new_provider_calls"] == scope["new_external_cost_usd"] == 0
    output_result = {"groups": 48, "queries": 20, "parent_rankings_recomputed": 40,
        "chunk_scores_regrouped": chunk_count, "parents_each_ranking": 805,
        "judgment_pool_pairs": 158, "known_grade3_pairs": 12, "target_paths": len(diagnostic_rows),
        "N20_union_controls_unchanged": len(controls), "old_sealed_files_unchanged": sealed,
        "known_work_facets": sum(len({f for t in targets if t['case_id'] == c['case_id'] for f in t['main_work']}) for c in cases.values()),
        "new_provider_calls": 0, "fresh_time_measured": False,
        "scope": "known assessed-pool retention; not full-corpus recall/JD completeness"}
    with (HERE / output).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(output_result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(output_result, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) == 2 else "verification.json")
