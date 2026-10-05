"""Independent invariants and counterexamples for the cached final-stage replay."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def main():
    manifest = read("input-manifest.json")
    for name, expected in manifest.items():
        path = ROOT / name
        assert len(path.read_bytes()) == expected["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected["sha256"]
    spec = importlib.util.spec_from_file_location("selection_replay", HERE / "analyze.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sample = [{"id": "a", "score": 1.0}, {"id": "b", "score": 0.5}, {"id": "c", "score": 0.5}]
    assert module.select(sample, {"kind": "absolute", "parameter": 2, "limit": 5}) == []
    assert len(module.select(sample, {"kind": "absolute", "parameter": 0.5, "limit": 5})) == 3
    assert len(module.select(sample, {"kind": "relative", "parameter": 0.5, "limit": 5})) == 3
    assert len(module.select(sample, {"kind": "gap", "parameter": 0.5, "limit": 5})) == 1
    assert module.select([], {"kind": "relative", "parameter": 0.1, "limit": 5}) == []
    unknown = module.metric("test", [{"id": "ungraded", "judgment": None}], [], ["unknown work"])
    assert unknown["grades"]["0"] == 0 and unknown["grades"]["ungraded"] == 1
    assert unknown["unassessed_facets"] == ["unknown work"]
    pools = read("candidate-pools.json")
    groups = read("results.json")
    counts = 0
    for group in groups:
        for case in group["cases"]:
            ids = case["selected_ids"]
            expected_prefix = [row["id"] for row in pools[case["case_id"]]][:len(ids)]
            assert ids == expected_prefix
            assert len(ids) <= group["policy"]["limit"]
            assert len(ids) == sum(case["grades"].values())
            assert not (set(case["known_grade3_retained"]) & set(case["known_grade3_missing"]))
            assert len(ids) + len(case["excluded_ids"]) == len(pools[case["case_id"]])
            counts += 1
    for row in read("summary.json"):
        expected = next(group["cases"] for group in groups if group["policy"] == row["policy"])
        assert row["selected_count"] == sum(len(case["selected_ids"]) for case in expected)
        assert row["known_grade3_total"] == 12
        assert row["known_facets_total"] == 8
    result = {"input_hashes_checked": len(manifest), "selection_groups_checked": counts,
              "counterexamples_checked": 6, "failures": 0, "new_provider_calls": 0}
    with (HERE / "independent-verification.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
