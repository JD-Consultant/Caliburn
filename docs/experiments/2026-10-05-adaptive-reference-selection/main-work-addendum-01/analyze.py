"""Reassess frozen retrieval results by main-work facets; standard library only."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SEALED = HERE.parent / "run-01"
EXPERIMENTS = HERE.parents[1]
CASES = EXPERIMENTS / "2026-10-05-memory-public-unit-retrieval/run-01/cases.json"
TARGETS = EXPERIMENTS / "2026-10-05-initial-retrieval-depth/run-01/targets.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fingerprint(path):
    value = path.read_bytes()
    return {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}


def write(output, name, value):
    with (output / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def verify_seal():
    manifest = read(SEALED / "artifact-hashes.json")
    for name, expected in manifest["files"].items():
        assert fingerprint(SEALED / name) == expected, name
    return {"files_checked": len(manifest["files"]), "mismatches": 0}


def independently_verify(rows):
    """Recount selections without importing the original analysis implementation."""
    pools = {case: {row["id"]: row for row in pool}
             for case, pool in read(SEALED / "candidate-pools.json").items()}
    cases = {row["case_id"]: row for row in read(CASES)}
    targets = read(TARGETS)
    lookup = {row["id"]: row for row in rows}
    assert len(lookup) == len(rows)
    initial_sizes = Counter()
    for row in read(SEALED / "first-stage/results.json"):
        initial_sizes[row["policy_id"]] += len(row["selectedIDs"])
    checked = set()
    per_case = {}
    for line in (SEALED / "composed-selections.jsonl").read_text(encoding="utf-8").splitlines():
        selection = json.loads(line)
        key = selection["id"]
        assert key not in checked
        checked.add(key)
        aggregate = lookup[key]
        assert aggregate["candidate_pairs"] == initial_sizes[aggregate["first_policy"]]
        assert set(selection["selectedIDs"]) == set(cases)
        counts = Counter()
        original_facets = sensitivity_facets = original_references = sensitivity_references = 0
        original_total = sensitivity_total = 0
        outcomes = []
        for case, ids in selection["selectedIDs"].items():
            assert len(ids) == len(set(ids)) <= aggregate["final_policy"]["limit"]
            case_grades = Counter()
            for doc_id in ids:
                judgment = pools[case][doc_id]["judgment"]
                case_grades["ungraded" if judgment is None else str(judgment["grade"])] += 1
            counts.update(case_grades)
            facets = set(cases[case]["major_work_facets"])
            local = [row for row in targets if row["case_id"] == case]
            safe = [row for row in local if not row["sensitivity_excluded"]]
            known = {facet for row in local for facet in row["main_work"]} & facets
            safe_known = {facet for row in safe for facet in row["main_work"]} & facets
            found = {facet for row in local if row["id"] in ids for facet in row["main_work"]} & known
            safe_found = {facet for row in safe if row["id"] in ids for facet in row["main_work"]} & safe_known
            original_facets += len(found)
            sensitivity_facets += len(safe_found)
            original_total += len(known)
            sensitivity_total += len(safe_known)
            original_references += sum(row["id"] in ids for row in local)
            sensitivity_references += sum(row["id"] in ids for row in safe)
            outcomes.append({"case_id": case, "selected_ids": ids,
                             "grades": {grade: case_grades[grade] for grade in ("0", "1", "2", "3", "ungraded")},
                             "known_facets_supported": sorted(found), "known_facets_missing": sorted(known - found),
                             "sensitivity_facets_supported": sorted(safe_found),
                             "sensitivity_facets_missing": sorted(safe_known - safe_found),
                             "unassessed_facets": sorted(facets - known)})
        assert aggregate["selected_count"] == sum(counts.values()), key
        assert aggregate["grades"] == {grade: counts[grade] for grade in ("0", "1", "2", "3", "ungraded")}, key
        assert aggregate["known_facets_supported"] == original_facets, key
        assert aggregate["known_facets_total"] == original_total, key
        assert aggregate["known_grade3_retained"] == original_references, key
        assert aggregate["sensitivity"]["known_facets_supported"] == sensitivity_facets, key
        assert aggregate["sensitivity"]["known_facets_total"] == sensitivity_total, key
        assert aggregate["sensitivity"]["known_grade3_retained"] == sensitivity_references, key
        per_case[key] = outcomes
    assert checked == set(lookup)
    return per_case


def weak(row):
    return row["grades"]["0"] + row["grades"]["1"]


def objective(row):
    return weak(row), row["selected_count"], row["candidate_pairs"]


def report_group(rows, maximize_facets=False):
    key = lambda row: ((-row["known_facets_supported"],) if maximize_facets else ()) + objective(row)
    ordered = sorted(rows, key=lambda row: key(row) + (row["id"],))
    return {"eligible_count": len(ordered),
            "optimal_tie_ids": [row["id"] for row in ordered if key(row) == key(ordered[0])],
            "top_rows": ordered[:10]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=HERE,
                        help="Use a new directory for reruns; output files are never overwritten.")
    args = parser.parse_args()
    output = args.output.resolve()
    assert not output.is_relative_to(SEALED), "Sealed run-01 is read-only."
    output.mkdir(parents=True, exist_ok=True)
    before = verify_seal()
    input_paths = [SEALED / name for name in (
        "artifact-hashes.json", "composed-summary.json", "composed-selections.jsonl",
        "candidate-pools.json", "first-stage/results.json")]
    input_paths += [CASES, TARGETS, HERE / "analyze.py", HERE / "README.md"]
    input_hashes = {str(path.relative_to(ROOT)): fingerprint(path) for path in input_paths}
    rows = read(SEALED / "composed-summary.json")
    case_outcomes = independently_verify(rows)
    universe = [row for row in rows if row["final_policy"]["limit"] <= 5 and row["grades"]["ungraded"] == 0]
    groups = {
        "original_facets_8_of_8": report_group([row for row in universe if row["known_facets_supported"] >= 8]),
        "original_facets_at_least_7_of_8": report_group([row for row in universe if row["known_facets_supported"] >= 7]),
        "sensitivity_facets_8_of_8": report_group([row for row in universe if row["sensitivity"]["known_facets_supported"] >= 8]),
        "sensitivity_facets_at_least_7_of_8": report_group([row for row in universe if row["sensitivity"]["known_facets_supported"] >= 7]),
        "zero_grade0_grade1": report_group([row for row in universe if weak(row) == 0], maximize_facets=True),
    }
    assert len(rows) == 7038 and len(universe) == 3325
    assert groups["original_facets_8_of_8"]["eligible_count"] == 68
    assert weak(groups["original_facets_8_of_8"]["top_rows"][0]) == 11
    assert groups["original_facets_at_least_7_of_8"]["eligible_count"] == 108
    assert weak(groups["original_facets_at_least_7_of_8"]["top_rows"][0]) == 2
    assert groups["sensitivity_facets_8_of_8"]["eligible_count"] == 0
    assert groups["sensitivity_facets_at_least_7_of_8"]["eligible_count"] == 108
    assert groups["zero_grade0_grade1"]["top_rows"][0]["known_facets_supported"] == 5
    selected_keys = {key for group in groups.values() for key in group["optimal_tie_ids"]}
    selected_keys.add("T_absolute_floor_0.7_floor3::top1")
    summary = {"scope": "Post-hoc objective reassessment, same eight historical cases; no new model inference.",
               "all_combinations": len(rows), "eligible_universe": len(universe),
               "universe_filter": "Final cap <= 5; no ungraded final outputs. No requirement to preserve each known grade3 document.",
               "objective_order": ["Meet specified known-main-facet coverage", "Minimize grade0+grade1 count", "Minimize final document count", "Minimize initial candidate pairs"],
               "zero_weak_objective": "First maximize known main facets, then apply count/workload tie breaks.",
               "groups": groups}
    after = verify_seal()
    assert input_hashes == {str(path.relative_to(ROOT)): fingerprint(path) for path in input_paths}
    write(output, "input-manifest.json", input_hashes)
    write(output, "summary.json", summary)
    write(output, "selected-case-outcomes.json", {key: case_outcomes[key] for key in sorted(selected_keys)})
    write(output, "verification.json", {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sealed_before": before, "sealed_after": after,
        "input_hashes_unchanged": True, "independently_recounted_combinations": len(case_outcomes),
        "independently_recounted_case_selections": len(case_outcomes) * 8,
        "checks": ["Initial candidate pair counts", "Selected IDs unique and within cap", "Original grade histograms",
                   "Original and sensitivity known-facet sets and reference counts", "Expected filtering/objective results"],
        "model_calls": 0, "provider_calls": 0, "production_changes": 0})
    artifacts = {str(path.relative_to(output)): fingerprint(path) for path in sorted(output.rglob("*"))
                 if path.is_file() and path.name != "artifact-hashes.json" and "__pycache__" not in path.parts}
    write(output, "artifact-hashes.json", {"created_at": datetime.now(timezone.utc).isoformat(), "files": artifacts})
    print(json.dumps({"checked": len(rows), "eligible": len(universe),
                      "group_counts": {key: value["eligible_count"] for key, value in groups.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
