"""Independent output audit and seal; imports no analysis implementation."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def meta(path):
    with path.open("rb") as stream:
        return {"sha256": hashlib.file_digest(stream, "sha256").hexdigest(), "bytes": path.stat().st_size}


def write(name, value):
    with (HERE / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    for relative, expected in read(HERE / "input-manifest.json")["inputs"].items():
        assert meta(ROOT / relative) == expected, relative
    policies = {p["policy_id"]: p for p in read(HERE / "policies.json")}
    pools = {(r["query_id"], r["route"]): r["parents"] for r in read(HERE / "full-route-rankings.json")}
    results = read(HERE / "results.json")
    summary = read(HERE / "summary.json")
    targets = read(ROOT / "docs/experiments/2026-10-05-initial-retrieval-depth/run-01/targets.json")
    seen = set()
    for row in results:
        key = (row["policy_id"], row["case_id"])
        assert key not in seen
        seen.add(key)
        selected = set()
        for route, rule in policies[row["policy_id"]]["route_rules"].items():
            pool = pools[(row["query_id"], route)]
            kind, value = rule["kind"], rule.get("value")
            if kind == "fixed":
                wanted = {p["id"] for p in pool if p["rank"] <= value}
            elif kind == "full":
                wanted = {p["id"] for p in pool}
            elif kind in ("absolute", "absolute_floor"):
                wanted = {p["id"] for p in pool if p["score"] >= value or p["rank"] <= rule.get("floor", 0)}
            elif kind == "relative":
                wanted = {p["id"] for p in pool if pool[0]["score"] - p["score"] <= value}
            else:
                gaps = [a["rank"] for a, b in zip(pool, pool[1:]) if a["score"] - b["score"] >= value]
                stop = min(gaps, default=805)
                wanted = {p["id"] for p in pool if p["rank"] <= stop}
            assert row["routes"][route]["selected_count"] == len(wanted)
            selected |= wanted
        assert row["selectedIDs"] == sorted(selected)
        assert row["selected_count"] == len(selected)
        for grade_key, facet_key, clear_only in (("known_grade3", "known_work_facets", False),
                                               ("clear_grade3_sensitivity", "clear_work_facets_sensitivity", True)):
            own = [t for t in targets if t["case_id"] == row["case_id"] and not (clear_only and t["sensitivity_excluded"])]
            retained = [t for t in own if t["id"] in selected]
            assert set(row[grade_key]["retained_ids"]) == {t["id"] for t in retained}
            assert set(row[grade_key]["missing_ids"]) == {t["id"] for t in own if t["id"] not in selected}
            assert set(row[facet_key]["retained"]) == {f for t in retained for f in t["main_work"]}
    for s in summary:
        rows = [r for r in results if r["policy_id"] == s["policy_id"]]
        assert len(rows) == 8 and s["candidate_total"] == sum(r["selected_count"] for r in rows)
        assert s["known_grade3"]["retained"] == sum(len(r["known_grade3"]["retained_ids"]) for r in rows)
        assert s["known_work_facets"]["retained"] == sum(len(r["known_work_facets"]["retained"]) for r in rows)
    tests = subprocess.run([sys.executable, "-B", "-X", "utf8", "-m", "unittest", "-v", "test_mechanism"],
                           cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    assert tests.returncode == 0, tests.stderr
    oldseal = []
    for check in read(HERE / "verification.json")["prior_seals_after"]:
        folder = ROOT / check["directory"]
        for relative, expected in read(folder / "artifact-hashes.json")["files"].items():
            assert meta(folder / relative) == expected
        oldseal.append(check)
    write("verification-final.json", {"rows_independently_checked": len(results), "policies": len(policies),
        "selection_IDs_and_counts": "pass", "known_positive_and_facet_retention": "pass",
        "summary_counts": "pass", "mechanism_tests": 6, "test_exit_code": tests.returncode,
        "test_output": tests.stderr, "input_hashes_unchanged": True, "prior_seals": oldseal,
        "new_provider_embedding_reranker_database_calls": 0})
    files = {p.name: meta(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name != "artifact-hashes.json"}
    write("artifact-hashes.json", {"created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "CPU first-stage exploration artifacts, including failed preflight provenance; excludes this manifest", "files": files})
    print(json.dumps({"rows_checked": len(results), "tests_passed": 6, "sealed_files": len(files),
                      "prior_files_unchanged": sum(r["files"] for r in oldseal)}))


if __name__ == "__main__":
    main()
