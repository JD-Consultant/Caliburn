"""Cross frozen first-stage selections with cached reranker cutoffs only."""

import hashlib
import importlib.util
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name, data):
    with (HERE / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    spec = importlib.util.spec_from_file_location("replay_methods", HERE / "analyze.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    first = read(HERE / "first-stage/results.json")
    policies = read(HERE / "policies.json")
    pools = read(HERE / "candidate-pools.json")
    cases = {row["case_id"]: row for row in read(module.PRIOR / "cases.json")}
    targets = read(module.DEPTH / "targets.json")
    safe_targets = [row for row in targets if not row["sensitivity_excluded"]]
    baseline = {case_id: module.metric(case_id, pool[:5], targets, cases[case_id]["major_work_facets"])
                for case_id, pool in pools.items()}
    lookup = {case_id: {row["id"]: row for row in pool} for case_id, pool in pools.items()}
    grouped = defaultdict(dict)
    for row in first:
        assert row["case_id"] not in grouped[row["policy_id"]]
        grouped[row["policy_id"]][row["case_id"]] = row
    eligible = {}
    missing = []
    missing_pairs = set()
    for policy_id, rows in grouped.items():
        assert set(rows) == set(cases)
        unavailable = []
        for case_id, row in rows.items():
            ids = row["selectedIDs"]
            assert len(ids) == len(set(ids))
            for doc_id in ids:
                if doc_id not in lookup[case_id]:
                    unavailable.append({"case_id": case_id, "document_id": doc_id})
                    missing_pairs.add((case_id, doc_id))
        if unavailable:
            missing.append({"policy_id": policy_id, "missing_count": len(unavailable),
                            "reason": "Not all selected query-document pairs have frozen rerank scores"})
        else:
            eligible[policy_id] = rows
    write("composition-availability.json", {"first_stage_policies": len(grouped),
        "fully_cached_policies": sorted(eligible), "incomplete_policies": missing,
        "unique_missing_pairs": [{"case_id": c, "document_id": d} for c, d in sorted(missing_pairs)]})
    paths = [HERE / "first-stage/results.json", HERE / "first-stage/policies.json",
             HERE / "policies.json", HERE / "candidate-pools.json", HERE / "scope-update.md",
             HERE / "compose.py", module.PRIOR / "cases.json", module.DEPTH / "targets.json"]
    write("composition-inputs.json", {str(path.relative_to(ROOT)): {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size} for path in paths})
    summaries = []
    case_results = {}
    with (HERE / "composed-selections.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for first_id, rows in eligible.items():
            first_pool = {case_id: [row for row in pools[case_id] if row["id"] in set(rows[case_id]["selectedIDs"])] for case_id in cases}
            initial_metrics = {case_id: module.metric(case_id, pool, targets, cases[case_id]["major_work_facets"])
                               for case_id, pool in first_pool.items()}
            for final_policy in policies:
                key = f"{first_id}::{final_policy['id']}"
                evaluated = []
                sensitive = []
                selected_ids = {}
                for case_id, pool in first_pool.items():
                    selected = module.select(pool, final_policy)
                    row = module.metric(case_id, selected, targets, cases[case_id]["major_work_facets"])
                    row["initial_selected_count"] = len(pool)
                    row["initial_missing_grade3"] = initial_metrics[case_id]["known_grade3_missing"]
                    row["lost_baseline_grade3"] = sorted(set(baseline[case_id]["known_grade3_retained"]) - set(row["known_grade3_retained"]))
                    evaluated.append(row)
                    sensitive.append(module.metric(case_id, selected, safe_targets, cases[case_id]["major_work_facets"]))
                    selected_ids[case_id] = [item["id"] for item in selected]
                summary = {"id": key, "first_policy": first_id, "final_policy": final_policy,
                           "candidate_pairs": sum(map(len, first_pool.values())),
                           "initial_known_grade3": sum(len(row["known_grade3_retained"]) for row in initial_metrics.values()),
                           "lost_baseline_grade3_count": sum(len(row["lost_baseline_grade3"]) for row in evaluated),
                           **module.aggregate(evaluated), "sensitivity": module.aggregate(sensitive)}
                summaries.append(summary)
                if final_policy["limit"] <= 5:
                    case_results[key] = evaluated
                stream.write(json.dumps({"id": key, "selectedIDs": selected_ids}, ensure_ascii=False, separators=(",", ":")) + "\n")
    write("composed-summary.json", summaries)
    admissible = [row for row in summaries if row["final_policy"]["limit"] <= 5
                  and row["initial_known_grade3"] == 12
                  and row["lost_baseline_grade3_count"] == 0 and row["grades"]["ungraded"] == 0]

    def vector(row):
        return (row["candidate_pairs"], row["grades"]["0"] + row["grades"]["1"],
                -row["known_grade3_retained"], -row["grades"]["2"], row["selected_count"])

    frontier = [row for row in admissible if not any(
        all(a <= b for a, b in zip(vector(other), vector(row)))
        and any(a < b for a, b in zip(vector(other), vector(row))) for other in admissible)]
    write("composed-frontier.json", {"criteria": "Preserve all initial known grade3 and every baseline-final known grade3; no ungraded final; cap<=5. Minimize pairs, grade0/1, and selected; maximize grade3 and grade2. Not a deployable best proof.",
                                    "rows": frontier})
    folds = []
    for test_case in cases:
        options = []
        for key, rows in case_results.items():
            train = [row for row in rows if row["case_id"] != test_case]
            if all(not row["initial_missing_grade3"] and not row["lost_baseline_grade3"]
                   and row["grades"]["ungraded"] == 0 for row in train):
                objective = (sum(row["initial_selected_count"] for row in train),
                             sum(row["grades"]["0"] + row["grades"]["1"] for row in train),
                             sum(row["selected_count"] for row in train), key)
                options.append((objective, key))
        assert options, "Baseline-equivalent policy must remain feasible"
        chosen = min(options)[1]
        outcome = next(row for row in case_results[chosen] if row["case_id"] == test_case)
        folds.append({"test_case": test_case, "chosen_policy": chosen, "test_result": outcome})
    write("composed-cross-case.json", {"folds": folds, "summary": module.aggregate([row["test_result"] for row in folds]),
        "candidate_pairs": sum(row["test_result"]["initial_selected_count"] for row in folds),
        "initial_missing_grade3": sum(len(row["test_result"]["initial_missing_grade3"]) for row in folds),
        "additional_lost_baseline_grade3": sum(len(row["test_result"]["lost_baseline_grade3"]) for row in folds)})
    print(json.dumps({"initial_policies": len(grouped), "fully_cached": len(eligible),
                      "combinations": len(summaries), "admissible": len(admissible), "frontier": len(frontier)}))
    for row in sorted(admissible, key=lambda row: (row["candidate_pairs"], row["grades"]["0"] + row["grades"]["1"], row["selected_count"]))[:5]:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
