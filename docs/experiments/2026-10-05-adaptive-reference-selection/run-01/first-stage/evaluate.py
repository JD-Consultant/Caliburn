"""Bounded CPU replay of sealed cosine rankings; standard library only."""
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
EXP = ROOT / "docs/experiments"
PRIOR = EXP / "2026-10-05-memory-public-unit-retrieval/run-01"
UNION = EXP / "2026-10-05-rerank-union-candidate-replay/run-01"
DEPTH = EXP / "2026-10-05-initial-retrieval-depth/run-01"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(name, value):
    with (HERE / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def filemeta(path):
    return {"sha256": sha(path), "bytes": path.stat().st_size}


def seals():
    result = []
    for folder in (PRIOR, UNION, DEPTH):
        manifest = read(folder / "artifact-hashes.json")
        for relative, expected in manifest["files"].items():
            assert filemeta(folder / relative) == expected, str(folder / relative)
        result.append({"directory": folder.relative_to(ROOT).as_posix(),
                       "files": len(manifest["files"]), "mismatches": 0,
                       "manifest_sha256": sha(folder / "artifact-hashes.json")})
    return result


def select(pool, rule):
    if not pool:
        return []
    kind, value = rule["kind"], rule.get("value")
    if kind == "fixed":
        return pool[:value]
    if kind == "full":
        return pool[:]
    if kind in ("absolute", "absolute_floor"):
        count = sum(p["score"] >= value for p in pool)
        return pool[:max(count, rule.get("floor", 0))]
    if kind == "relative":
        return [p for p in pool if pool[0]["score"] - p["score"] <= value]
    if kind == "gap":
        for i in range(1, len(pool)):
            if pool[i - 1]["score"] - pool[i]["score"] >= value:
                return pool[:i]
        return pool[:]
    raise ValueError(kind)


def policies():
    base = []
    grids = {"fixed": (5, 10, 20, 40, 80),
             "absolute": tuple(i / 1000 for i in range(500, 851, 25)),
             "relative": (.01, .02, .03, .05, .08, .10, .15),
             "gap": (.005, .01, .02, .03, .05)}
    for kind, values in grids.items():
        for value in values:
            base.append({"kind": kind, "value": value})
    for value in grids["absolute"]:
        for floor in (3, 5):
            base.append({"kind": "absolute_floor", "value": value, "floor": floor})
    base.append({"kind": "full"})
    result = []
    for rule in base:
        suffix = rule["kind"] + (f"_{rule['value']:g}" if "value" in rule else "")
        if "floor" in rule:
            suffix += f"_floor{rule['floor']}"
        for mode in ("D", "T", "DT"):
            result.append({"policy_id": mode + "_" + suffix, "mode": mode,
                           "family": rule["kind"], "asymmetric": False,
                           "route_rules": {route: rule.copy() for route in mode}})
    for kind, values in (("fixed", grids["fixed"]),
                         ("absolute", (.60, .65, .70, .75, .80)),
                         ("relative", grids["relative"])):
        for dvalue in values:
            for tvalue in values:
                if dvalue == tvalue:
                    continue
                result.append({"policy_id": f"DT_{kind}_D{dvalue:g}_T{tvalue:g}",
                    "mode": "DT", "family": kind, "asymmetric": True,
                    "route_rules": {"D": {"kind": kind, "value": dvalue},
                                    "T": {"kind": kind, "value": tvalue}}})
    assert len(result) == len({p["policy_id"] for p in result}) == 271
    return result


def target_state(targets, ids):
    known = sorted(t["id"] for t in targets)
    retained = [ident for ident in known if ident in ids]
    return {"known_ids": known, "retained_ids": retained,
            "missing_ids": [ident for ident in known if ident not in ids],
            "known_coverage": len(retained) / len(known) if known else None}


def facet_state(facets, targets, ids):
    known = {f for t in targets for f in t["main_work"]}
    retained = {f for t in targets if t["id"] in ids for f in t["main_work"]}
    assert retained <= known <= set(facets)
    return {"known": [f for f in facets if f in known],
            "retained": [f for f in facets if f in retained],
            "missing": [f for f in facets if f in known - retained],
            "unassessed": [f for f in facets if f not in known],
            "known_coverage": len(retained) / len(known) if known else None}


def assessed_state(case, own, ids):
    clear = [t for t in own if not t["sensitivity_excluded"]]
    return {"known_grade3": target_state(own, ids),
            "known_work_facets": facet_state(case["major_work_facets"], own, ids),
            "clear_grade3_sensitivity": target_state(clear, ids),
            "clear_work_facets_sensitivity": facet_state(case["major_work_facets"], clear, ids)}


def main():
    before = seals()
    sourcefiles = [PRIOR / name for name in ("all-rankings.json", "cases.json", "queries.json", "corpus.json", "artifact-hashes.json")]
    sourcefiles += [UNION / "query-unions.json", UNION / "artifact-hashes.json", DEPTH / "targets.json", DEPTH / "artifact-hashes.json"]
    sourcefiles += [HERE / name for name in ("protocol.md", "evaluate.py", "test_mechanism.py")]
    manifest = {p.relative_to(ROOT).as_posix(): filemeta(p) for p in sourcefiles}
    dump("input-manifest.json", {"created_at": datetime.now(timezone.utc).isoformat(), "inputs": manifest,
        "new_provider_calls": 0, "new_embedding_calls": 0, "new_reranker_calls": 0,
        "new_database_calls": 0, "score_source": "frozen exact CPU cosine, no recomputed embedding"})
    specs = policies()
    dump("policies.json", specs)
    cases = {r["case_id"]: r for r in read(PRIOR / "cases.json")}
    queries = [q for q in read(PRIOR / "queries.json") if q["input_variant"] == "O"]
    targets = read(DEPTH / "targets.json")
    docs = {d["id"]: d for d in read(PRIOR / "corpus.json")}
    assert len(queries) == len(cases) == 8 and len(docs) == 805 and len(targets) == 12
    assert len([t for t in targets if not t["sensitivity_excluded"]]) == 10
    for q in queries:
        employee = cases[q["case_id"]]["employee_statement"]
        if q["case_id"].startswith("H"):
            # Frozen O historical input includes role labels and consultant questions.
            assert "\n".join(s["text"] for s in q["source_spans"] if s.get("speaker") == "employee") == employee
        else:
            assert q["text"] == employee
        assert hashlib.sha256(q["text"].encode()).hexdigest() == q["text_sha256"]
    for t in targets:
        assert hashlib.sha256(docs[t["id"]]["text"].encode()).hexdigest() == t["document_sha256"]
    qids = {q["query_id"] for q in queries}
    routes = {}
    full = []
    for row in read(PRIOR / "all-rankings.json"):
        if row["query_id"] not in qids:
            continue
        maxima = {}
        for c in row["chunk_scores"]:
            assert math.isfinite(c["score"])
            maxima[c["parent_id"]] = max(maxima.get(c["parent_id"], -math.inf), c["score"])
        rebuilt = [{"id": ident, "score": score} for ident, score in sorted(maxima.items(), key=lambda kv: (-kv[1], kv[0]))]
        assert len(rebuilt) == 805 and set(maxima) == set(docs)
        assert [(p["id"], p["score"]) for p in rebuilt] == [(p["id"], p["score"]) for p in row["parents"]]
        route = {"document": "D", "task": "T"}[row["representation"]]
        ranked = [{"rank": i, **p} for i, p in enumerate(rebuilt, 1)]
        routes[(row["query_id"], route)] = ranked
        full.append({"case_id": next(q["case_id"] for q in queries if q["query_id"] == row["query_id"]),
                     "query_id": row["query_id"], "route": route, "parents": ranked})
    assert len(routes) == 16
    dump("full-route-rankings.json", full)
    controls = {r["query_id"]: {p["id"] for p in r["candidates"]} for r in read(UNION / "query-unions.json")}
    results = []
    for policy in specs:
        for q in queries:
            case = cases[q["case_id"]]
            own = [t for t in targets if t["case_id"] == q["case_id"]]
            selected, route_info = set(), {}
            for route, rule in policy["route_rules"].items():
                pool = routes[(q["query_id"], route)]
                prefix = select(pool, rule)
                ids = {p["id"] for p in prefix}
                assert prefix == pool[:len(prefix)]
                assert len(prefix) == len(ids) <= 805
                selected |= ids
                nextscore = pool[len(prefix)]["score"] if len(prefix) < 805 else None
                route_info[route] = {"selected_count": len(prefix), "top_score": pool[0]["score"],
                    "last_selected_score": prefix[-1]["score"] if prefix else None,
                    "first_excluded_score": nextscore,
                    "boundary_gap": prefix[-1]["score"] - nextscore if prefix and nextscore is not None else None,
                    **assessed_state(case, own, ids)}
            if policy["policy_id"] == "DT_fixed_20":
                assert selected == controls[q["query_id"]]
            results.append({"policy_id": policy["policy_id"], "case_id": q["case_id"], "query_id": q["query_id"],
                "selectedIDs": sorted(selected), "selected_count": len(selected), "routes": route_info,
                **assessed_state(case, own, selected)})
    dump("results.json", results)
    summary = []
    for policy in specs:
        rows = [r for r in results if r["policy_id"] == policy["policy_id"]]
        counts = [r["selected_count"] for r in rows]
        entry = {**policy, "candidate_total": sum(counts), "candidate_min": min(counts), "candidate_max": max(counts),
                 "per_case_counts": {r["case_id"]: r["selected_count"] for r in rows},
                 "route_count_totals": {route: sum(r["routes"][route]["selected_count"] for r in rows) for route in policy["route_rules"]}}
        for key in ("known_grade3", "known_work_facets", "clear_grade3_sensitivity", "clear_work_facets_sensitivity"):
            ik, kk = ("retained_ids", "known_ids") if "grade3" in key else ("retained", "known")
            entry[key] = {"retained": sum(len(r[key][ik]) for r in rows), "known": sum(len(r[key][kk]) for r in rows),
                          "unassessed_cases": [r["case_id"] for r in rows if r[key]["known_coverage"] is None]}
        summary.append(entry)
    control = next(s for s in summary if s["policy_id"] == "DT_fixed_20")
    assert control["candidate_total"] == 247 and control["known_grade3"]["retained"] == 12 and control["known_work_facets"]["retained"] == 8
    assert all(s["known_grade3"]["unassessed_cases"] == ["H01"] for s in summary)
    dump("summary.json", summary)
    # Diagnostic frontier excludes known-negative claims; each case coverage remains in results.
    def dominates(a, b):
        ak = (a["known_grade3"]["retained"], a["known_work_facets"]["retained"], a["clear_grade3_sensitivity"]["retained"])
        bk = (b["known_grade3"]["retained"], b["known_work_facets"]["retained"], b["clear_grade3_sensitivity"]["retained"])
        return a["candidate_total"] <= b["candidate_total"] and all(x >= y for x, y in zip(ak, bk)) and (a["candidate_total"] < b["candidate_total"] or ak != bk)
    frontier = [s for s in summary if not any(dominates(other, s) for other in summary)]
    dump("frontier.json", sorted(frontier, key=lambda s: (s["candidate_total"], s["policy_id"])))
    diagnostic = []
    for family in sorted({s["family"] for s in summary}):
        group = [s for s in summary if s["family"] == family]
        eligible = [s for s in group if s["known_grade3"]["retained"] == 12 and s["known_work_facets"]["retained"] == 8]
        lowest = min((s["candidate_total"] for s in eligible), default=None)
        diagnostic.append({"family": family, "policies": len(group), "full_known_retention_policies": len(eligible),
            "smallest_full_retention_candidate_total": lowest,
            "smallest_full_retention_policy_ids": [s["policy_id"] for s in eligible if s["candidate_total"] == lowest],
            "candidate_total_range": [min(s["candidate_total"] for s in group), max(s["candidate_total"] for s in group)]})
    dump("family-diagnostics.json", diagnostic)
    assert all(filemeta(ROOT / relative) == expected for relative, expected in manifest.items())
    after = seals()
    assert before == after
    dump("verification.json", {"policies": len(specs), "rows": len(results), "full_rankings": len(full),
        "parents_per_route": 805, "chunk_to_parent_rebuild_matches": True, "control_N20_union_ids_match": True,
        "control_candidate_total": 247, "control_known_grade3": "12/12", "control_known_facets": "8/8",
        "input_hashes_unchanged": True, "prior_seals_before": before, "prior_seals_after": after,
        "H01_unassessed_preserved": True, "new_provider_calls": 0, "new_embedding_calls": 0,
        "new_reranker_calls": 0, "new_database_calls": 0, "fresh_latency_measured": False,
        "full_corpus_qrels_available": False})
    print(json.dumps({"policies": len(specs), "rows": len(results), "control": control,
                      "families": diagnostic}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
