"""Recompute preserved rankings without a model service or a database connection."""

import argparse
import csv
import hashlib
import json
import math
import re
from datetime import UTC, datetime

import numpy as np

from evaluation import fuse_rankings, ranking_check, ranking_metrics, validate_dense
from experiment import group_summary, sorted_ranking, sparse_scores
from prepare import HERE, ROOT, sha, write_json


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_cache_prefix(path, length, digest):
    with path.open("rb") as stream:
        raw = stream.read(length)
    if len(raw) != length or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"Cache prefix differs: {path}")
    entries = [json.loads(line) for line in raw.splitlines()]
    result = {entry["text_sha256"]: entry for entry in entries}
    if len(result) != len(entries):
        raise ValueError("Duplicate cache key")
    return result


def compare_values(expected, actual, context="summary", tolerance=1e-9):
    for key, value in expected.items():
        other = actual.get(key)
        valid = (other is None if value is None else
                 isinstance(other, (int, float)) and math.isfinite(other)
                 and abs(value - other) <= tolerance)
        if not valid:
            raise ValueError(f"{context}: {key} differs: {value} vs {other}")


def verify_row(row, case, expected, limit=None, tolerance=1e-9):
    if row["grades"] != case["grades"]:
        raise ValueError("Saved relevance grades differ from frozen labels")
    actual = [(item["id"], item["score"]) for item in row["ranking"]]
    check = ranking_check(actual, expected, len(expected) if limit is None else limit, tolerance)
    if not check["correct"]:
        raise ValueError(f"Saved ranking differs from cached vector calculation: {check}")
    metrics = ranking_metrics([key for key, _ in actual], case["grades"])
    # The unit test also permits a minimal row; artifact audits supply all metrics.
    compare_values({key: value for key, value in metrics.items() if key in row}, row, "row metrics")
    return True


class Offline:
    def __init__(self, entries, corpus):
        self.entries = entries
        self.corpus = corpus
        self.used = set()
        self.documents = {}
        self.ranks = {}

    def embeddings(self, texts):
        keys = [hashlib.sha256(text.encode()).hexdigest() for text in texts]
        self.used.update(keys)
        rows = [self.entries[key] for key in keys]
        return (validate_dense([row["embedding"]["dense"] for row in rows], len(rows)),
                [dict(zip(row["embedding"]["sparse"]["indices"],
                          row["embedding"]["sparse"]["values"], strict=True)) for row in rows])

    def rankings(self, text, rep):
        key = (text, rep)
        if key not in self.ranks:
            if rep not in self.documents:
                texts = [(row["texts"]["description"] or row["texts"]["top"])
                         if rep == "description_or_top" else row["texts"][rep] for row in self.corpus]
                self.documents[rep] = self.embeddings(texts)
            docs, sparse = self.documents[rep]
            query, sp_query = self.embeddings([text])
            self.ranks[key] = {"dense": sorted_ranking(docs @ query[0], self.corpus),
                               "sparse": sorted_ranking(sparse_scores(sp_query[0], sparse), self.corpus)}
        return self.ranks[key]

    def ranking(self, text, rep, method="dense", depth=50, constant=60):
        rows = self.rankings(text, rep)
        return fuse_rankings(rows["dense"], rows["sparse"], depth, constant) if method == "rrf" else rows[method]


def audit_parameters(run, offline, probes, selected, grid):
    rep, method = selected["selected_representation"], selected["selected_method"]
    chosen = grid["chosen_development_only"]
    expected_chosen = max(grid["grid"], key=lambda row: (row["ndcg_10"], row["mrr"],
                                                       -row["depth"], -row["constant"]))
    if chosen != expected_chosen:
        raise ValueError("Development RRF choice differs from saved grid")

    def ranking(case, retrieval=method):
        return offline.ranking(case["text"], rep, retrieval, chosen["depth"], chosen["constant"])

    development = [case for case in probes.values() if case["split"] == "development"]
    positives = [case for case in development if case["grades"]]
    summary = read_json(run / "holdout-summary.json")
    for entry in summary["top_k_grid"]:
        k = entry["k"]
        counts = {"any_acceptable_cases": sum(any(case["grades"].get(key, 0) >= 2
                    for key, _ in ranking(case)[:k]) for case in positives),
                  "all_primary_roles_cases": sum(all(target in dict(ranking(case)[:k])
                    for target, grade in case["grades"].items() if grade == 3) for case in positives),
                  "positive_cases": len(positives)}
        compare_values(counts, entry, "top-k development")
    maximum = max(entry["all_primary_roles_cases"] for entry in summary["top_k_grid"])
    k = next(entry["k"] for entry in summary["top_k_grid"] if entry["all_primary_roles_cases"] == maximum)
    holdout = [case for case in probes.values() if case["split"] == "holdout" and case["grades"]]
    compare_values({"selected_k": k,
        "holdout_any_acceptable_at_selected_k": sum(any(case["grades"].get(key, 0) >= 2
             for key, _ in ranking(case)[:k]) for case in holdout),
        "holdout_all_primary_at_selected_k": sum(all(target in dict(ranking(case)[:k])
             for target, grade in case["grades"].items() if grade == 3) for case in holdout)}, summary, "top-k holdout")
    threshold = read_json(run / "threshold.json")
    for entry in threshold["development_grid"]:
        accepts = [case for case in development if ranking(case, "dense")[0][1] >= entry["threshold"]]
        compare_values({"positive_accepts": sum(bool(case["grades"]) for case in accepts),
                        "negative_accepts": sum(not case["grades"] for case in accepts)}, entry, "threshold grid")
    viable = [entry for entry in threshold["development_grid"] if entry["negative_accepts"] == 0
              and entry["positive_accepts"] / len(positives) >= 0.8]
    value = viable[0]["threshold"] if viable else None
    compare_values({"provisional_threshold": value}, threshold)
    for decision in threshold["decisions"]:
        case = probes[decision["case_id"]]
        score = ranking(case, "dense")[0][1]
        compare_values({"dense_top1_score": score}, decision, "threshold score")
        if (decision["expected_abstain"] != (not bool(case["grades"]))
                or decision["selected_threshold_accepts"] != (None if value is None else score >= value)):
            raise ValueError("Threshold accept/reject decision differs")


def artifact_inventory():
    return {path.relative_to(HERE).as_posix(): {"bytes": path.stat().st_size, "sha256": sha(path)}
            for path in sorted(HERE.rglob("*")) if path.is_file()
            and "__pycache__" not in path.parts
            and path.name not in {"artifact-hashes.json", "verification.json"}}


def check_seal():
    sealed = read_json(HERE / "artifact-hashes.json")["files"]
    if sealed != artifact_inventory():
        raise ValueError("Artifact seal differs: changed, missing, or additional experiment files")


def audit():
    manifest = read_json(HERE / "manifest.json")
    for name in ["corpus", "cases", "probes", "protocol"]:
        path = HERE / (name + (".md" if name == "protocol" else ".json"))
        if sha(path) != manifest[name + "_sha256"]:
            raise ValueError(f"Frozen {name} changed")
    corpus = read_json(HERE / "corpus.json")
    cases = {case["case_id"]: case for case in read_json(HERE / "cases.json")}
    probes = {case["case_id"]: case for case in read_json(HERE / "probes.json")}
    development_count = sum(case["split"] == "development" for case in probes.values())
    holdout_count = len(probes) - development_count
    expected_counts = {
        "run-05": {"input": len(cases) * 3, "representation": development_count * 3,
                   "method": development_count * 3, "rrf-grid": development_count * 16,
                   "holdout": holdout_count, "selected-memory": len(cases)},
        "candidate-01": {"rrf-grid": development_count * 16, "holdout": holdout_count,
                         "selected-memory": len(cases)},
        "memory-01": {"memory-method": len(cases) * 6},
        "memory-02": {"memory-method": len(cases) * 6}}
    sources = {row["source"]: row["source_sha256"]
               for row in corpus + read_json(HERE / "quarantine.json")}
    sources.update({source["path"]: source["sha256"] for case in cases.values() for source in case["sources"]})
    for path, digest in sources.items():
        if sha(ROOT / path) != digest:
            raise ValueError(f"Source changed: {path}")
    if len(corpus) != manifest["corpus_count"] or len({row["id"] for row in corpus}) != len(corpus):
        raise ValueError("Corpus count or unique ID mismatch")
    complete = read_json(HERE / "candidate-01/complete.json")
    entries = read_cache_prefix(HERE / complete["cache_path"], complete["cache_byte_prefix_length"],
                                complete["cache_sha256"])
    model_runtime = read_json(HERE / "candidate-01/manifest.json")["runtime"]
    max_tokens = max(row["tokens"] for row in entries.values())
    if max_tokens > model_runtime["max_length"]:
        raise ValueError("Embedding cache includes truncated text")
    validate_dense([row["embedding"]["dense"] for row in entries.values()], len(entries))
    for row in entries.values():
        sparse = row["embedding"]["sparse"]
        if (len(sparse["indices"]) != len(set(sparse["indices"]))
                or len(sparse["indices"]) != len(sparse["values"])
                or not np.isfinite(sparse["values"]).all()):
            raise ValueError("Invalid sparse cache entry")
    offline = Offline(entries, corpus)
    output = []
    checks = []
    database_checks = []
    audited_stages = {}
    for run_name in ["run-05", "memory-01", "memory-02", "candidate-01"]:
        run = HERE / run_name
        run_manifest = read_json(run / "manifest.json")
        if run_manifest["base_manifest_sha256"] != sha(HERE / "manifest.json"):
            raise ValueError(f"{run_name}: base manifest differs")
        if run_manifest["runtime"] != model_runtime:
            raise ValueError("Mixed runtime fingerprint")
        script = ("validate_final_candidate.py" if run_name == "candidate-01" else
                  "compare_memory_methods.py" if run_name.startswith("memory") else "experiment.py")
        for field, filename in [("script_sha256", script), ("evaluator_sha256", "evaluation.py"),
                                ("validation_sha256", "validation.py"), ("environment_sha256", "environment.json")]:
            if field in run_manifest and sha(HERE / filename) != run_manifest[field]:
                raise ValueError(f"Completed run executable provenance differs: {run_name}/{filename}")
        selected = read_json(run / "complete.json") if (run / "complete.json").exists() else None
        if selected:
            prefix = read_cache_prefix(HERE / selected["cache_path"], selected["cache_byte_prefix_length"],
                                       selected["cache_sha256"])
            if not set(selected["used_cache_keys"]) <= prefix.keys():
                raise ValueError("Used cache keys are absent")
        else:
            reference = read_json(run / "cache-reference.json")
            read_cache_prefix(HERE / reference["path"], reference["byte_prefix_length"], reference["sha256"])
        grid = read_json(run / "rrf-grid.json") if selected else None
        paths = sorted(run.glob("*-rankings.jsonl"))
        if {path.name.removesuffix("-rankings.jsonl") for path in paths} != expected_counts[run_name].keys():
            raise ValueError(f"Missing or additional ranking stage: {run_name}")
        for path in paths:
            stage = path.name.removesuffix("-rankings.jsonl")
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            if (len(rows) != expected_counts[run_name][stage]
                    or len({(row["case_id"], row["arm"]) for row in rows}) != len(rows)):
                raise ValueError(f"Missing or duplicate observations: {path}")
            audited_stages[run_name + "/" + stage] = len(rows)
            for row in rows:
                case = cases[row["case_id"]] if row["case_id"] in cases else probes[row["case_id"]]
                if (row["employee_group"] != case.get("employee_group", case.get("family", case["case_id"]))
                        or row["split"] != case.get("split", "input-pilot")
                        or row["corpus_count"] != len(corpus)
                        or row["returned_candidates"] != len(row["ranking"])):
                    raise ValueError("Case grouping, split, or candidate count differs")
                text = case.get("text", case.get("inputs", {}).get("B_b2"))
                rep, method, depth, constant = "top", "dense", 50, 60
                if stage == "input":
                    text = case["inputs"][row["arm"]]
                elif stage == "representation":
                    rep = row["arm"]
                elif stage == "memory-method":
                    rep, method = row["arm"].split("-")
                else:
                    rep = selected["selected_representation"]
                    if stage == "method":
                        method = row["arm"]
                    elif stage == "rrf-grid":
                        depth, constant = map(int, re.fullmatch(r"depth(\d+)-k(\d+)", row["arm"]).groups())
                        method = "rrf"
                    else:
                        method = selected["selected_method"]
                        depth, constant = (grid["chosen_development_only"][key] for key in ["depth", "constant"])
                expected = offline.ranking(text, rep, method, depth, constant)
                verify_row(row, case, expected, 10 if stage == "selected-memory" else None,
                           1e-6 if stage == "selected-memory" else 1e-9)
                output.append({"run": run_name, **{key: value for key, value in row.items()
                                                   if key not in ["grades", "ranking"]}})
            summary_path = run / f"{stage}-summary.json"
            if summary_path.exists():
                summary = read_json(summary_path)
                if stage in ["holdout", "selected-memory"]:
                    compare_values(group_summary(rows), summary["metrics"], str(summary_path))
                else:
                    for arm in {row["arm"] for row in rows}:
                        compare_values(group_summary([row for row in rows if row["arm"] == arm]),
                                       summary[arm], str(summary_path) + ":" + arm)
            elif stage == "rrf-grid":
                for entry in grid["grid"]:
                    arm = f"depth{entry['depth']}-k{entry['constant']}"
                    compare_values(group_summary([row for row in rows if row["arm"] == arm]), entry, "RRF grid")
            checks.append({"path": path.relative_to(HERE).as_posix(), "rows": len(rows),
                           "cached_scores_and_frozen_grades_and_metrics": True})
        if selected:
            audit_parameters(run, offline, probes, selected, grid)
            rep = selected["selected_representation"]
            for row in read_json(run / "database.json"):
                expected = offline.ranking(probes[row["case_id"]]["text"], rep,
                                           "rrf" if row.get("method") == "rrf-exact" else "dense",
                                           grid["chosen_development_only"]["depth"],
                                           grid["chosen_development_only"]["constant"])
                actual = [(point["id"], point["score"]) for point in row["results"]]
                check = ranking_check(actual, expected, 10, 1e-5)
                if row.get("exact") or row.get("method") == "rrf-exact":
                    if not check["correct"]:
                        raise ValueError(f"Database exact ranking mismatch: {run_name}/{row['case_id']}")
                elif not (check["sufficient"] and check["unique"] and check["ordered"] and check["score_valid"]):
                    raise ValueError("ANN score/list inconsistency")
                target = {key for key, _ in expected[:10]}
                recall = len({key for key, _ in actual} & target) / 10
                if "top10_set_recall" in row:
                    compare_values({"top10_set_recall": recall}, row, "ANN recall")
                database_checks.append({"run": run_name, "case_id": row["case_id"],
                                        "method": row.get("method", "dense"),
                                        "exact": row.get("exact"), "hnsw_ef": row.get("hnsw_ef"),
                                        "correct": check["correct"], "recall": recall})
    original = read_json(HERE / "memory-01/memory-method-summary.json")
    replay = read_json(HERE / "memory-02/memory-method-summary.json")
    if original != replay:
        raise ValueError("Persistent Memory comparison script differs from original exploratory results")
    input_summary = read_json(HERE / "run-05/input-summary.json")
    chosen_input = max(["B_b2", "C_b2_b1"], key=lambda arm: (input_summary[arm]["ndcg_10"],
                       input_summary[arm]["mrr"], -input_summary[arm]["mean_tokens"]))
    chosen_method = max([key for key in original if key != "provisional_choice"],
                        key=lambda arm: (original[arm]["ndcg_10"], original[arm]["mrr"]))
    if (chosen_input != complete["selected_input"] or chosen_method != "top-dense"
            or complete["selected_representation"] != "top" or complete["selected_method"] != "dense"
            or complete["fresh_holdout"] or complete["production_adoption"]):
        raise ValueError("Final candidate differs from recorded exploratory choice or scope")
    with (HERE / "results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    summary = {
        "status": "provisional_isolated_pilot", "production_adoption": False, "fresh_holdout": False,
        "choice": {"input": "published_B2_body", "corpus": "description_and_TOP_body",
                   "embedding": "BGE-M3", "retrieval": "Qdrant_exact_dense_cosine", "candidate_top_k": 10,
                   "production_acceptance_threshold": None},
        "input": read_json(HERE / "run-05/input-summary.json"),
        "whole_memory_methods": read_json(HERE / "memory-01/memory-method-summary.json"),
        "original_short_probe_holdout": read_json(HERE / "run-05/holdout-summary.json"),
        "final_candidate_regression": read_json(HERE / "candidate-01/holdout-summary.json"),
        "final_candidate_whole_memory": read_json(HERE / "candidate-01/selected-memory-summary.json"),
        "limitations": ["2 synthetic employee contexts; 5 correlated snapshots",
                        "32 hand-written work probes, holdout has overlapping occupation domains",
                        "manual incomplete relevance labels, not expert ground truth",
                        "method reconsidered after original holdout; final holdout is regression only",
                        "exact=false / hnsw_ef measurements began at yellow; stable dense ANN indexing not verified",
                        "no real-employee, JD completion, task-coverage, or database-product comparison"]}
    write_json(HERE / "summary.json", summary)
    verification = {"completed_utc": datetime.now(UTC).isoformat(), "passed": True,
                    "source_files_sha256_verified": len(sources), "corpus_count": len(corpus),
                    "cache_entries": len(entries), "used_texts_in_recomputation": len(offline.used),
                    "maximum_tokens": max_tokens, "silent_truncation": False,
                    "ranking_rows_recomputed": len(output), "stages": audited_stages,
                    "database_rows_recomputed": len(database_checks),
                    "database_exact_or_rrf_rows_correct": sum(row["correct"] for row in database_checks
                        if row["exact"] or row["method"] == "rrf-exact"),
                    "checks": checks, "scope": "Offline recomputation of saved live results; not a new trial",
                    "script_sha256": sha(HERE / "verify_results.py")}
    write_json(HERE / "verification.json", verification)
    print(json.dumps({key: value for key, value in verification.items()
                      if key not in ["checks", "stages"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seal", action="store_true", help="Create a new artifact inventory after finalization")
    parser.add_argument("--check-seal", action="store_true", help="Verify the saved inventory before recomputing")
    args = parser.parse_args()
    if args.seal and (HERE / "artifact-hashes.json").exists():
        raise ValueError("Seal already exists; preserve it rather than silently replacing it")
    if args.check_seal:
        check_seal()
    audit()
    if args.seal:
        write_json(HERE / "artifact-hashes.json", {"completed_utc": datetime.now(UTC).isoformat(),
                   "excluded": ["artifact-hashes.json", "verification.json", "__pycache__/"],
                   "files": artifact_inventory()})
