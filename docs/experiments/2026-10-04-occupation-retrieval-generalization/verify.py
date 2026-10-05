"""Offline replay of labels, source receipts, vectors, rankings, metrics and seals."""
import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import UTC, datetime

import numpy as np

from support import FIRST, HERE, decision, generation_messages, published_b2
sys.path.insert(0, str(FIRST))
from evaluation import ranking_check, validate_dense
from experiment import sorted_ranking
sys.path.pop(0)
from retrieve import summaries


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def check(run_dir):
    first_seal = read(FIRST / "artifact-hashes.json")
    for path, entry in first_seal["files"].items():
        assert sha(FIRST / path) == entry["sha256"], path
    manifest = read(run_dir / "manifest.json")
    corpus = read(FIRST / "corpus.json")
    cases = read(HERE / "cases.json")
    assert sha(HERE / "cases.json") == manifest["cases_sha256"]
    assert sha(HERE / "protocol.md") == manifest["protocol_sha256"]
    assert sha(FIRST / "corpus.json") == manifest["corpus_sha256"]
    sources = read(run_dir / "supporting-sources.json")
    assert sha(run_dir / "supporting-sources.json") == manifest["supporting_sources_sha256"]
    # Text archives normalize CRLF; prove every original byte hash is reconstructible.
    for path, expected in manifest["files_sha256"].items():
        content = sources[path]
        assert expected in {hashlib.sha256(value.encode()).hexdigest() for value in
                            (content, content.replace("\n", "\r\n"))}, path
    complete = read(run_dir / "complete.json")
    captures = [json.loads(line) for line in (run_dir / "capture.jsonl").read_text().splitlines()]
    assert len(captures) == complete["cases"] == len(cases) == 14
    by_case = {c["case_id"]: c for c in cases}
    assert len(by_case) == 14
    assert {c["case_id"] for c in captures} == set(by_case)
    assert len({c["job_file_id"] for c in captures}) == 14
    assert len({c["execution_id"] for c in captures}) == 14
    evidence = read(run_dir / "source-evidence.json")
    assert set(evidence) == set(by_case)
    for capture in captures:
        case_id = capture["case_id"]
        assert read(run_dir / case_id / "messages.json") == generation_messages(by_case[case_id])
        actual = evidence[case_id]["messages"]
        assert [{k: r[k] for k in ("interview_sequence", "speaker", "text")} for r in actual] == generation_messages(by_case[case_id])
        snapshot = read(run_dir / case_id / "snapshot.json")
        assert snapshot["snapshot"]["covered_through_sequence"] == 6
        assert snapshot["snapshot"]["snapshot_id"] == capture["snapshot_id"] == evidence[case_id]["published_snapshot_id"]
        published_b2(snapshot)  # exact B1 revision guard; empty is permitted, never fabricated
        known = {r["source_id"] for r in actual if r["speaker"] == "employee"}
        for obj in snapshot["objects"]:
            if obj["layer"] == "work_situation":
                refs = set(re.findall(r"UUID\('([^']+)'\)", obj["interview_references"]))
                assert refs and refs <= known
    trace = [json.loads(line) for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    admitted = calls = input_tokens = output_tokens = cached_tokens = 0
    resolved_models = set()
    count = None
    codes = [r["id"] for r in corpus]
    for row in trace:
        payload = row.get("payload", {})
        if row["event"] == "response" and row.get("path", "").endswith("/input_tokens"):
            count = payload["input_tokens"]
        if row["event"] == "request" and row.get("path", "").endswith("/responses"):
            assert 0 < count <= 125_000
            admitted += count
            calls += 1
            assert payload["model"] == "gpt-6-luna"
            assert payload["max_output_tokens"] == 8192
            assert payload["reasoning"]["effort"] == "high"
            serialized = json.dumps(payload, ensure_ascii=False)
            assert not any(code in serialized for code in codes)
        if row["event"] == "response" and row.get("path", "").endswith("/responses"):
            usage = payload["usage"]
            resolved_models.add(payload["model"])
            input_tokens += usage["input_tokens"]
            output_tokens += usage["output_tokens"]
            cached_tokens += usage["input_tokens_details"]["cached_tokens"]
            assert usage["output_tokens"] <= 8192
        assert row["event"] not in ("provider_error", "compact_blocked_before_send")
    assert calls == complete["calls"] == sum(c["model_calls"] for c in captures) <= 256
    assert admitted == complete["admitted_input"] <= 4_000_000
    out = run_dir / "retrieval"
    retrieval_complete = read(out / "complete.json")
    cache_path = HERE / retrieval_complete["cache_path"]
    assert sha(cache_path) == retrieval_complete["cache_sha256"]
    cache = {r["text_sha256"]: r for r in map(json.loads, cache_path.read_text().splitlines())}
    retrieval_manifest = read(out / "manifest.json")
    prefix = cache_path.read_bytes()[:retrieval_manifest["cache_original_bytes"]]
    assert hashlib.sha256(prefix).hexdigest() == retrieval_manifest["cache_original_sha256"]
    documents = validate_dense([cache[hashlib.sha256(r["texts"]["top"].encode()).hexdigest()]["embedding"]["dense"] for r in corpus], 805)
    query_documents = read(out / "queries.json")
    assert len(query_documents) == 14
    queries = {q["case_id"]: q for q in query_documents}
    assert set(queries) == set(by_case)
    all_rankings = [json.loads(line) for line in (out / "fixed-rankings.jsonl").read_text(encoding="utf-8").splitlines()]
    metrics = read(out / "metrics.json")
    assert len(metrics) == len(all_rankings) == 28
    case_arms = {(c["case_id"], arm) for c in cases for arm in ("B2", "raw_employee")}
    assert {(r["case_id"], r["arm"]) for r in metrics} == case_arms
    assert {(r["case_id"], r["arm"]) for r in all_rankings} == case_arms
    titles = {r["id"]: r["title"] for r in corpus}
    expected_by_key = {}
    for record, metric in zip(all_rankings, metrics, strict=True):
        case = by_case[record["case_id"]]
        query = queries[case["case_id"]]
        snapshot_path = run_dir / case["case_id"] / "snapshot.json"
        assert query["snapshot_sha256"] == sha(snapshot_path)
        assert query["B2"] == published_b2(read(snapshot_path))
        assert query["raw_employee"] == "\n\n".join(case["employee_messages"])
        text = query[record["arm"]]
        if text is None:
            expected, tokens = [], 0
        else:
            entry = cache[hashlib.sha256(text.encode()).hexdigest()]
            expected = sorted_ranking(documents @ validate_dense([entry["embedding"]["dense"]], 1)[0], corpus)
            tokens = entry["tokens"]
            assert 0 < tokens <= 8192
        actual = [(r["id"], r["score"]) for r in record["ranking"]]
        assert len(actual) == len(expected) and len(dict(actual)) == len(actual)
        assert all(k == a and abs(s - b) < 1e-12 for (k, s), (a, b) in zip(actual, expected, strict=True))
        assert record["grades"] == case["grades"]
        assert all(r["title"] == titles[r["id"]] for r in record["ranking"])
        for key in ("case_id", "split", "arm"):
            assert metric[key] == record[key]
        assert metric["kind"] == case["kind"]
        assert metric["split"] == case["split"]
        assert metric["query_empty"] == (text is None)
        assert metric["returned_candidates"] == record["returned_candidates"] == len(expected)
        assert metric["corpus_count"] == record["corpus_count"] == 805
        top1 = {"top1_id": expected[0][0] if expected else None,
                "top1_title": titles[expected[0][0]] if expected else None,
                "top1_score": expected[0][1] if expected else None}
        for key, value in top1.items():
            assert metric[key] == record[key] == value, (case["case_id"], key)
        rank_by_id = {key: index for index, (key, _) in enumerate(expected, 1)}
        hard_negative_rank = min((rank_by_id[key] for key in case["hard_negatives"] if key in rank_by_id), default=None)
        assert metric["hard_negative_best_rank"] == record["hard_negative_best_rank"] == hard_negative_rank
        assert metric["tokens"] == tokens
        for key, value in decision(case, expected).items():
            assert metric[key] == value, (case["case_id"], key)
        expected_by_key[(case["case_id"], record["arm"])] = expected
    assert summaries(metrics) == read(out / "summary.json")
    with (out / "metrics.csv").open(encoding="utf-8-sig", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    assert csv_rows == [{key: str(value) if value is not None else "" for key, value in row.items()}
                        for row in metrics]
    checks = read(out / "database-checks.json")
    assert len(checks) == sum(not row["query_empty"] for row in metrics) == retrieval_complete["database_queries"]
    assert {(r["case_id"], r["arm"]) for r in checks} == {
        (r["case_id"], r["arm"]) for r in metrics if not r["query_empty"]}
    for check in checks:
        assert check["exact"] is True
        actual = [(r["id"], r["score"]) for r in check["returned"]]
        validation = ranking_check(actual, expected_by_key[(check["case_id"], check["arm"])])
        assert validation["correct"]
        assert all(check[key] == value for key, value in validation.items())
    cost_standard = (input_tokens - cached_tokens) * 0.10 / 1_000_000 + cached_tokens * 0.01 / 1_000_000 + output_tokens * 0.50 / 1_000_000
    cost_conservative = input_tokens * 0.125 / 1_000_000 + output_tokens * 0.50 / 1_000_000
    return {"verified_utc": datetime.now(UTC).isoformat(), "status": "passed", "synthetic_cases": 14,
        "exact_B1_revisions_and_employee_sources": True, "archived_source_hashes": len(sources),
        "frozen_labels": True, "ranking_rows": len(metrics), "database_exact_checks": len(checks),
        "cache_original_prefix_unchanged": True, "first_round_sealed_files_unchanged": len(first_seal["files"]),
        "usage": {"generation_calls": calls, "resolved_models": sorted(resolved_models),
            "admitted_input": admitted, "input_tokens": input_tokens, "cached_input_tokens": cached_tokens,
            "output_tokens": output_tokens, "estimated_standard_usd": cost_standard,
            "conservative_upper_usd": cost_conservative, "official_billing_confirmed": False}}


def inventory():
    excluded = {"artifact-hashes.json", "verification.json"}
    return {p.relative_to(HERE).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
            for p in sorted(HERE.rglob("*")) if p.is_file() and p.name not in excluded
            and "__pycache__" not in p.parts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--check-seal", action="store_true")
    args = parser.parse_args()
    result = check(HERE / "run-02")
    if args.seal:
        assert not (HERE / "artifact-hashes.json").exists()
        dump(HERE / "artifact-hashes.json", inventory())
    if args.check_seal:
        assert inventory() == read(HERE / "artifact-hashes.json")
        result["artifact_seal"] = "passed"
    dump(HERE / "verification.json", result)
    print(json.dumps(result, ensure_ascii=False))
