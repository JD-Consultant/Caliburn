"""CPU-only, source-bound analysis of frozen retrieval scores. No providers."""

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXP = HERE.parents[1]
PRIOR = EXP / "2026-10-05-memory-public-unit-retrieval/run-01"
UNION = EXP / "2026-10-05-rerank-union-candidate-replay/run-01"
DEPTH = EXP / "2026-10-05-initial-retrieval-depth/run-01"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(name, value):
    with (HERE / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def check_seals():
    checks = []
    for folder in (PRIOR, UNION, DEPTH):
        manifest = read(folder / "artifact-hashes.json")
        for relative, expected in manifest["files"].items():
            path = folder / relative
            assert path.stat().st_size == expected["bytes"], str(path)
            assert digest(path) == expected["sha256"], str(path)
        checks.append({"path": str(folder.relative_to(ROOT)),
                       "files_checked": len(manifest["files"]), "mismatches": 0})
    return checks


def select(pool, policy):
    if not pool:
        return []
    limit = policy["limit"]
    kind = policy["kind"]
    parameter = policy.get("parameter")
    if kind == "fixed":
        return pool[:limit]
    if kind == "absolute":
        return [row for row in pool if row["score"] >= parameter][:limit]
    if kind == "relative":
        return [row for row in pool if pool[0]["score"] - row["score"] <= parameter][:limit]
    if kind == "gap":
        for index in range(1, min(len(pool), limit)):
            if pool[index - 1]["score"] - pool[index]["score"] >= parameter:
                return pool[:index]
        return pool[:limit]
    raise ValueError(kind)


def policies():
    result = [{"id": f"top{k}", "kind": "fixed", "limit": k}
              for k in (1, 2, 3, 4, 5, 10, 40)]
    parameters = {
        "absolute": [x / 2 for x in range(-16, 1)],
        "relative": [0.1, 0.25, 0.5, 1, 1.5, 2, 3, 4, 6],
        "gap": [0.1, 0.25, 0.5, 1, 2],
    }
    for kind, values in parameters.items():
        for limit in (5, 10):
            for value in values:
                result.append({"id": f"{kind}_{value:g}_cap{limit}",
                               "kind": kind, "parameter": value, "limit": limit})
    return result


def metric(case_id, selected, targets, facets):
    ids = {row["id"] for row in selected}
    local = [row for row in targets if row["case_id"] == case_id]
    known = {facet for row in local for facet in row["main_work"]} & set(facets)
    supported = {facet for row in local if row["id"] in ids
                 for facet in row["main_work"]} & known
    counts = Counter("ungraded" if row["judgment"] is None else str(row["judgment"]["grade"])
                     for row in selected)
    return {
        "case_id": case_id, "selected_count": len(selected),
        "grades": {key: counts[key] for key in ("0", "1", "2", "3", "ungraded")},
        "known_grade3_retained": [row["id"] for row in local if row["id"] in ids],
        "known_grade3_missing": [row["id"] for row in local if row["id"] not in ids],
        "known_facets_supported": sorted(supported),
        "known_facets_missing": sorted(known - supported),
        "unassessed_facets": sorted(set(facets) - known),
    }


def aggregate(rows):
    return {
        "selected_count": sum(row["selected_count"] for row in rows),
        "average_per_case": sum(row["selected_count"] for row in rows) / len(rows),
        "range": [min(row["selected_count"] for row in rows), max(row["selected_count"] for row in rows)],
        "empty_cases": [row["case_id"] for row in rows if not row["selected_count"]],
        "grades": {key: sum(row["grades"][key] for row in rows) for key in ("0", "1", "2", "3", "ungraded")},
        "known_grade3_retained": sum(len(row["known_grade3_retained"]) for row in rows),
        "known_grade3_total": sum(len(row["known_grade3_retained"]) + len(row["known_grade3_missing"]) for row in rows),
        "known_facets_supported": sum(len(row["known_facets_supported"]) for row in rows),
        "known_facets_total": sum(len(row["known_facets_supported"]) + len(row["known_facets_missing"]) for row in rows),
    }


def main():
    before = check_seals()
    paths = [UNION / "query-unions.json", UNION / "results.json", PRIOR / "graded-results.json",
             PRIOR / "corpus.json", PRIOR / "cases.json", DEPTH / "targets.json",
             UNION / "input-manifest.json", HERE / "protocol.md", HERE / "analyze.py"]
    dump("input-manifest.json", {str(path.relative_to(ROOT)): {
        "sha256": digest(path), "bytes": path.stat().st_size} for path in paths})
    cases = {row["case_id"]: row for row in read(PRIOR / "cases.json")}
    corpus = {row["id"]: row for row in read(PRIOR / "corpus.json")}
    targets = read(DEPTH / "targets.json")
    for row in targets:
        assert hashlib.sha256(cases[row["case_id"]]["employee_statement"].encode()).hexdigest() == row["employee_sha256"]
        assert hashlib.sha256(corpus[row["id"]]["text"].encode()).hexdigest() == row["document_sha256"]
    judgments = {}
    for group in read(PRIOR / "graded-results.json") + read(UNION / "results.json"):
        for row in group["selected"]:
            key = (group["case_id"], row["id"])
            judgment = row["judgment"]
            if key in judgments:
                assert judgments[key]["grade"] == judgment["grade"]
                assert judgments[key]["main_work"] == judgment["main_work"]
            judgments[key] = judgment
    pools = {}
    for group in read(UNION / "query-unions.json"):
        if group["variant"] != "O":
            continue
        pool = [{**row, "rank": rank, "title": corpus[row["id"]]["title"],
                 "judgment": judgments.get((group["case_id"], row["id"]))}
                for rank, row in enumerate(group["candidates"], 1)]
        assert len(pool) == len({row["id"] for row in pool})
        assert all(math.isfinite(row["score"]) for row in pool)
        assert all(a["score"] >= b["score"] for a, b in zip(pool, pool[1:]))
        pools[group["case_id"]] = pool
    assert set(cases) == set(pools)
    for group in read(UNION / "results.json"):
        if group["method"] == "O-U-R":
            assert [row["id"] for row in pools[group["case_id"]][:5]] == [row["id"] for row in group["selected"]]
    dump("candidate-pools.json", pools)
    grid = policies()
    dump("policies.json", grid)
    results = []
    summary = []
    safe_targets = [row for row in targets if not row["sensitivity_excluded"]]
    for policy in grid:
        rows = []
        sensitive = []
        for case_id, pool in pools.items():
            selected = select(pool, policy)
            row = metric(case_id, selected, targets, cases[case_id]["major_work_facets"])
            row["selected_ids"] = [item["id"] for item in selected]
            row["excluded_ids"] = [item["id"] for item in pool if item not in selected]
            rows.append(row)
            sensitive.append(metric(case_id, selected, safe_targets, cases[case_id]["major_work_facets"]))
        results.append({"policy": policy, "cases": rows})
        summary.append({"policy": policy, **aggregate(rows), "sensitivity": aggregate(sensitive)})
    dump("results.json", results)
    dump("summary.json", summary)
    by_policy = {row["policy"]["id"]: row for row in results}
    baseline = {row["case_id"]: row for row in by_policy["top5"]["cases"]}
    folds = []
    for kind in ("absolute", "relative", "gap"):
        for test_case in cases:
            options = []
            for policy in grid:
                if policy["kind"] != kind or policy["limit"] != 5:
                    continue
                training = [row for row in by_policy[policy["id"]]["cases"] if row["case_id"] != test_case]
                if all(set(baseline[row["case_id"]]["known_grade3_retained"]) <= set(row["known_grade3_retained"]) for row in training):
                    options.append((sum(row["selected_count"] for row in training), policy))
            policy = min(options, key=lambda item: item[0])[1] if options else grid[4]
            row = next(row for row in by_policy[policy["id"]]["cases"] if row["case_id"] == test_case)
            folds.append({"kind": kind, "test_case": test_case, "chosen_policy": policy,
                          "fallback": not options, "test_result": row,
                          "additional_lost_baseline_grade3": sorted(set(baseline[test_case]["known_grade3_retained"]) - set(row["known_grade3_retained"]))})
    dump("cross-case-check.json", {"folds": folds, "summary": {
        kind: aggregate([row["test_result"] for row in folds if row["kind"] == kind])
        for kind in ("absolute", "relative", "gap")}})
    diagnostic = []
    for case_id, pool in pools.items():
        base_ids = set(baseline[case_id]["known_grade3_retained"])
        minimum = max((row["rank"] for row in pool if row["id"] in base_ids), default=0)
        local_targets = {row["id"] for row in targets if row["case_id"] == case_id}
        diagnostic.append({"case_id": case_id, "minimum_prefix_for_baseline_grade3": minimum,
                           "minimum_prefix_for_all_known_grade3": max((row["rank"] for row in pool if row["id"] in local_targets), default=None),
                           "oracle_metric": metric(case_id, pool[:minimum], targets, cases[case_id]["major_work_facets"]),
                           "known_grade3_positions": [{"id": row["id"], "rank": row["rank"], "score": row["score"], "distance_from_best": pool[0]["score"] - row["score"]} for row in pool if row["id"] in local_targets]})
    dump("diagnostics.json", {"cases": diagnostic, "oracle_aggregate": aggregate([row["oracle_metric"] for row in diagnostic])})
    after = check_seals()
    assert before == after
    dump("verification.json", {"prior_seals_before": before, "prior_seals_after": after,
                              "source_bound_target_count": len(targets), "unique_reused_judgments": len(judgments),
                              "baseline_groups_reproduced": len(cases), "policies": len(grid),
                              "new_provider_calls": 0, "new_embedding_or_rerank_calls": 0, "external_cost_usd": 0})
    print(json.dumps({"cases": len(cases), "policies": len(grid), "candidate_pairs": sum(map(len, pools.values()))}))
    for row in summary:
        if row["policy"]["id"] in ("top1", "top3", "top5", "top10", "top40", "absolute_-4_cap5", "relative_1_cap5", "gap_0.5_cap5"):
            print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
