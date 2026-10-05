"""Initial retrieval depth only; no reranker, provider or production imports."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXPERIMENTS = HERE.parents[1]
PRIOR = EXPERIMENTS / "2026-10-05-memory-public-unit-retrieval/run-01"
UNION = EXPERIMENTS / "2026-10-05-rerank-union-candidate-replay/run-01"
VALIDATOR = EXPERIMENTS / "2026-10-04-a-interview-occupation-retrieval/run-01/pipeline.py"
DEPTHS = (20, 40, 80)
AMBIGUOUS = {("F05", "AVA2172-001v4"), ("H03", "MMP1324-001v4")}


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


def candidate_union(dense, task, count):
    if count <= 0 or len(dense) < count or len(task) < count:
        raise ValueError("invalid parent depth")
    if len(set(dense)) != len(dense) or len(set(task)) != len(task):
        raise ValueError("duplicate parent in route")
    return sorted(set(dense[:count]) | set(task[:count]))


def facet_state(facets, targets, candidates):
    known, retained = set(), set()
    for target in targets:
        if not set(target["main_work"]) <= set(facets):
            raise ValueError("judged facet is not a fixed employee facet")
        known.update(target["main_work"])
        if target["id"] in candidates:
            retained.update(target["main_work"])
    return {"known": [f for f in facets if f in known],
            "retained": [f for f in facets if f in retained],
            "missing": [f for f in facets if f in known - retained],
            "unassessed": [f for f in facets if f not in known],
            "known_coverage": len(retained) / len(known) if known else None}


def check_seals():
    results = []
    for directory in (PRIOR, UNION):
        seal = read(directory / "artifact-hashes.json")
        for relative, expected in seal["files"].items():
            path = directory / relative
            if path.stat().st_size != expected["bytes"] or sha(path) != expected["sha256"]:
                raise ValueError("prior sealed artifact changed: " + str(path))
        results.append({"path": directory.relative_to(ROOT).as_posix(), "files": len(seal["files"]),
                        "manifest_sha256": sha(directory / "artifact-hashes.json"), "mismatches": 0})
    return results


def freeze():
    seals = check_seals()
    files = [PRIOR / name for name in ("all-rankings.json", "graded-results.json", "cases.json",
        "queries.json", "corpus.json", "results.json", "verification-final.json", "input-manifest.json", "artifact-hashes.json")]
    files += [UNION / name for name in ("query-unions.json", "verification.json", "artifact-hashes.json")]
    files += [VALIDATOR, HERE / "protocol.md", HERE / "evaluate.py", HERE / "verify.py", HERE / "test_depth.py",
              ROOT / "docs/plans/2026-10-05-initial-retrieval-depth.md"]
    dump("input-manifest.json", {"inputs": {p.relative_to(ROOT).as_posix():
        {"sha256": sha(p), "bytes": p.stat().st_size} for p in files},
        "depths": DEPTHS, "embedding_dimension": 1024, "source": "frozen verified exact cosine rankings",
        "judgment_pool_pairs": 158, "known_grade3_pairs": 12,
        "ambiguous_pairs": [list(key) for key in sorted(AMBIGUOUS)], "new_provider_calls": 0,
        "scope": "initial candidates only, no new rerank or final K5"})
    dump("prior-seals-before.json", seals)
    print(f"Frozen {len(files)} inputs; {sum(r['files'] for r in seals)} prior artifacts valid")


def check_manifest():
    for relative, expected in read(HERE / "input-manifest.json")["inputs"].items():
        path = ROOT / relative
        if path.stat().st_size != expected["bytes"] or sha(path) != expected["sha256"]:
            raise ValueError("frozen input changed: " + relative)


def main():
    check_manifest()
    cases = {r["case_id"]: r for r in read(PRIOR / "cases.json")}
    queries = read(PRIOR / "queries.json")
    docs = {r["id"]: r for r in read(PRIOR / "corpus.json")}
    all_rankings = read(PRIOR / "all-rankings.json")
    ranking = {(r["query_id"], r["representation"]): r["parents"] for r in all_rankings}
    assert len(ranking) == 40
    lookup = {}
    for key, parents in ranking.items():
        assert len(parents) == 805 and {p["id"] for p in parents} == set(docs)
        assert parents == sorted(parents, key=lambda p: (-p["score"], p["id"]))
        lookup[key] = {p["id"]: {"rank": i, "score": p["score"]} for i, p in enumerate(parents, 1)}
    spec = importlib.util.spec_from_file_location("fixed_depth_validation", VALIDATOR)
    validation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validation)
    book = {}
    for r in read(PRIOR / "graded-results.json"):
        for p in r["selected"]:
            key = (r["case_id"], p["id"])
            if key in book:
                assert book[key]["judgment"] == p["judgment"]
            book[key] = p
    assert len(book) == 158
    targets = []
    for (case_id, ident), p in sorted(book.items()):
        judgment = p["judgment"]
        validation.validate_judgment(judgment, cases[case_id]["employee_statement"], docs[ident]["text"])
        if judgment["grade"] == 3:
            assert set(judgment["main_work"]) <= set(cases[case_id]["major_work_facets"])
            targets.append({"case_id": case_id, "id": ident, "title": docs[ident]["title"],
                "main_work": judgment["main_work"], "judgment": judgment,
                "employee_sha256": text_sha(cases[case_id]["employee_statement"]),
                "document_sha256": text_sha(docs[ident]["text"]),
                "source": (PRIOR / "graded-results.json").relative_to(ROOT).as_posix(),
                "sensitivity_excluded": (case_id, ident) in AMBIGUOUS,
                "quote_recovered_in_prior": p["quote_recovered"]})
    assert len(targets) == 12
    query_controls = {r["query_id"]: r for r in read(UNION / "query-unions.json")}
    results, ranks, minimum, controls = [], [], [], []
    missing_pairs_by_depth = {n: [] for n in DEPTHS}
    cached = {(r["query_id"], p["id"]) for r in query_controls.values() for p in r["candidates"]}
    for case_id, case in cases.items():
        own = [t for t in targets if t["case_id"] == case_id]
        clear = [t for t in own if not t["sensitivity_excluded"]]
        for variant in ("O", "B2"):
            qids = [q["query_id"] for q in queries if q["case_id"] == case_id and q["input_variant"] == variant]
            target_depths = {}
            for target in own:
                paths = [{"query_id": qid, "D": lookup[(qid, "document")][target["id"]],
                          "T": lookup[(qid, "task")][target["id"]]} for qid in qids]
                required = min(path[route]["rank"] for path in paths for route in ("D", "T"))
                target_depths[target["id"]] = required
                ranks.append({"case_id": case_id, "variant": variant, "id": target["id"],
                    "title": target["title"], "paths": paths, "minimum_N": required,
                    "sensitivity_excluded": target["sensitivity_excluded"]})
            def minimum_facets(target_list):
                values = {f: min((target_depths[t["id"]] for t in target_list if f in t["main_work"]), default=None)
                          for f in case["major_work_facets"]}
                known = [n for n in values.values() if n is not None]
                return {"facets": values, "minimum_N_for_known_facets": max(known) if known else None,
                        "unassessed_facets": [f for f, n in values.items() if n is None]}
            minimum.append({"case_id": case_id, "variant": variant,
                "minimum_N_all_known_grade3": max(target_depths.values()) if target_depths else None,
                "minimum_N_clear_grade3": max((target_depths[t["id"]] for t in clear), default=None),
                "work_facets": minimum_facets(own), "clear_work_facets": minimum_facets(clear)})
            for n in DEPTHS:
                pools, employee_ids = [], set()
                for qid in qids:
                    dparents, tparents = ranking[(qid, "document")], ranking[(qid, "task")]
                    dids, tids = [r["id"] for r in dparents], [r["id"] for r in tparents]
                    union = candidate_union(dids, tids, n)
                    employee_ids.update(union)
                    pools.append({"query_id": qid, "D": [{"rank": i, "id": p["id"], "score": p["score"]} for i, p in enumerate(dparents[:n], 1)],
                        "T": [{"rank": i, "id": p["id"], "score": p["score"]} for i, p in enumerate(tparents[:n], 1)],
                        "union_ids": union, "union_parents": len(union)})
                    if n == 20:
                        assert set(union) == {p["id"] for p in query_controls[qid]["candidates"]}
                        controls.append({"query_id": qid, "candidate_ids_unchanged": True, "parents": len(union)})
                    for ident in union:
                        if (qid, ident) not in cached:
                            missing_pairs_by_depth[n].append({"case_id": case_id, "query_id": qid,
                                "document_id": ident, "query_sha256": text_sha(next(q["text"] for q in queries if q["query_id"] == qid)),
                                "document_sha256": text_sha(docs[ident]["text"])})
                def target_state(target_list):
                    known = [t["id"] for t in target_list]
                    retained = [ident for ident in known if ident in employee_ids]
                    return {"known_ids": known, "retained_ids": retained,
                            "missing_ids": [ident for ident in known if ident not in employee_ids],
                            "known_coverage": len(retained) / len(known) if known else None}
                results.append({"case_id": case_id, "variant": variant, "depth_each_route": n, "query_ids": qids,
                    "query_pools": pools, "employee_candidate_ids": sorted(employee_ids),
                    "employee_unique_parents": len(employee_ids), "rerank_pair_workload": sum(p["union_parents"] for p in pools),
                    "known_grade3": target_state(own), "known_work_facets": facet_state(case["major_work_facets"], own, employee_ids),
                    "clear_grade3_sensitivity": target_state(clear),
                    "clear_work_facets_sensitivity": facet_state(case["major_work_facets"], clear, employee_ids)})
    summary = []
    for variant in ("O", "B2"):
        for n in DEPTHS:
            rows = [r for r in results if r["variant"] == variant and r["depth_each_route"] == n]
            entry = {"variant": variant, "depth_each_route": n, "cases": len(rows),
                     "query_count": sum(len(r["query_ids"]) for r in rows),
                     "employee_parent_count_sum": sum(r["employee_unique_parents"] for r in rows),
                     "rerank_pair_workload": sum(r["rerank_pair_workload"] for r in rows)}
            for key in ("known_grade3", "clear_grade3_sensitivity", "known_work_facets", "clear_work_facets_sensitivity"):
                reference = "grade3" in key
                retained_key, known_key = ("retained_ids", "known_ids") if reference else ("retained", "known")
                entry[key] = {"retained": sum(len(r[key][retained_key]) for r in rows),
                              "known": sum(len(r[key][known_key]) for r in rows),
                              "unassessed_case_count": sum(r[key]["known_coverage"] is None for r in rows)}
                if not reference:
                    entry[key]["unassessed_facet_count"] = sum(len(r[key]["unassessed"]) for r in rows)
            summary.append(entry)
    dump("targets.json", targets)
    dump("results.json", results)
    dump("target-ranks.json", ranks)
    dump("minimum-depth.json", minimum)
    dump("control-checks.json", controls)
    dump("summary.json", summary)
    dump("missing-rerank-cache-pairs.json", {str(n): rows for n, rows in missing_pairs_by_depth.items()})
    dump("scope.json", {"cases": 8, "input_variants": 2, "depths": DEPTHS, "groups": 48,
        "judgment_pool_pairs": len(book), "known_primary_pairs": len(targets),
        "new_provider_calls": 0, "new_embedding_inferences": 0, "new_db_queries": 0,
        "new_rerank_inferences": 0, "new_external_cost_usd": 0, "fresh_latency_measured": False,
        "full_corpus_qrels_available": False, "scope": "known assessed-pool and facet retention in cached exact initial rankings"})
    print(f"48 depth groups saved; 12 fixed known primary pairs; {len(controls)} N20 controls; no new inference")


if __name__ == "__main__":
    if sys.argv[1:] == ["--freeze"]:
        freeze()
    elif not sys.argv[1:]:
        main()
    else:
        raise SystemExit("Usage: evaluate.py [--freeze]")
