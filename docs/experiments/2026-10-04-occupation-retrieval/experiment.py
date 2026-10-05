"""Bounded staged retrieval experiment; frozen labels, complete rankings, local BGE."""

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np

from evaluation import fuse_rankings, ranking_metrics, validate_dense
from prepare import HERE, sha, write_json


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class Embeddings:
    def __init__(self):
        self.client = httpx.Client(base_url="http://127.0.0.1:8082", timeout=300, trust_env=False)
        self.runtime = self.client.get("/runtime").raise_for_status().json()
        self.model_key = fingerprint(self.runtime)
        cache_dir = HERE / "cache"
        cache_dir.mkdir(exist_ok=True)
        self.path = cache_dir / f"{self.model_key}.jsonl"
        self.entries = {}
        self.used_keys = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                entry = json.loads(line)
                self.entries[entry["text_sha256"]] = entry

    def get(self, texts, label):
        if any(not text.strip() for text in texts):
            raise ValueError("Empty input cannot be vectorized")
        keys = [hashlib.sha256(text.encode()).hexdigest() for text in texts]
        self.used_keys.update(keys)
        missing = list(dict.fromkeys(key for key in keys if key not in self.entries))
        by_key = dict(zip(keys, texts, strict=True))
        for start in range(0, len(missing), 8):
            selected = missing[start:start + 8]
            batch = [by_key[key] for key in selected]
            lengths = self.client.post("/token-lengths", json={"texts": batch}).raise_for_status().json()["lengths"]
            if len(lengths) != len(batch) or max(lengths) > self.runtime["max_length"]:
                raise ValueError(f"Silent truncation forbidden: {label} {lengths}")
            began = time.perf_counter()
            response = self.client.post("/embed", json={"texts": batch}).raise_for_status().json()["embeddings"]
            validate_dense([row["dense"] for row in response], len(batch))
            elapsed = time.perf_counter() - began
            with self.path.open("a", encoding="utf-8") as out:
                for key, length, value in zip(selected, lengths, response, strict=True):
                    sp = value["sparse"]
                    if len(sp["indices"]) != len(sp["values"]) or not np.isfinite(sp["values"]).all():
                        raise ValueError("Invalid sparse output")
                    entry = {"text_sha256": key, "tokens": length, "embedding": value,
                             "batch_seconds": elapsed, "batch_size": len(batch),
                             "completed_utc": datetime.now(UTC).isoformat()}
                    out.write(json.dumps(entry) + "\n")
                    self.entries[key] = entry
            print(f"{label}: {min(start + 8, len(missing))}/{len(missing)} new texts; {elapsed:.2f}s", flush=True)
        entries = [self.entries[key] for key in keys]
        return (validate_dense([entry["embedding"]["dense"] for entry in entries], len(texts)),
                [dict(zip(entry["embedding"]["sparse"]["indices"],
                          entry["embedding"]["sparse"]["values"], strict=True)) for entry in entries],
                [entry["tokens"] for entry in entries])


def sparse_scores(query, corpus):
    return np.array([sum(value * row.get(token, 0) for token, value in query.items())
                     for row in corpus], dtype=float)


def sorted_ranking(scores, corpus):
    return [(corpus[index]["id"], float(scores[index])) for index in
            sorted(range(len(corpus)), key=lambda index: (-scores[index], corpus[index]["id"]))]


def group_summary(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["employee_group"]].append(row)
    result = {}
    for key in ["hit_1", "hit_5", "hit_10", "mrr", "ndcg_10", "recall_5"]:
        means = [np.mean([row[key] for row in group if row[key] is not None]) for group in groups.values()
                 if any(row[key] is not None for row in group)]
        result[key] = float(np.mean(means)) if means else None
    result["mean_tokens"] = float(np.mean([row["tokens"] for row in rows]))
    return result


def save_outcome(run, stage, rows, summary):
    write_json(run / f"{stage}-summary.json", summary)
    if rows:
        with (run / f"{stage}-metrics.csv").open("w", newline="", encoding="utf-8-sig") as out:
            fields = [key for key in rows[0] if key != "grades"]
            writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)


def record(run, stage, case, arm, ranking, tokens, corpus, elapsed=0):
    ids = [key for key, _ in ranking]
    metrics = ranking_metrics(ids, case["grades"])
    title = {row["id"]: row["title"] for row in corpus}
    row = {"stage": stage, "case_id": case["case_id"], "arm": arm,
           "employee_group": case.get("employee_group", case.get("family", case["case_id"])),
           "split": case.get("split", "input-pilot"), "tokens": tokens,
           "top1_id": ids[0] if ids else None, "top1_title": title.get(ids[0]) if ids else None,
           "top1_score": ranking[0][1] if ids else None, **metrics,
           "query_seconds": elapsed, "returned_candidates": len(ranking), "corpus_count": len(corpus),
           "hard_negative_best_rank": min([ids.index(key) + 1 for key in case.get("hard_negatives", [])
                                            if key in ids], default=None)}
    with (run / f"{stage}-rankings.jsonl").open("a", encoding="utf-8") as out:
        out.write(json.dumps({**row, "grades": case["grades"],
                              "ranking": [{"id": key, "title": title[key], "score": score}
                                          for key, score in ranking]}, ensure_ascii=False) + "\n")
    return row


def run_stage1(run, model, corpus, cases):
    docs, _, _ = model.get([row["texts"]["top"] for row in corpus], "corpus-top")
    rows = []
    summaries = {}
    for arm in ["A_facts", "B_b2", "C_b2_b1"]:
        queries, _, tokens = model.get([case["inputs"][arm] for case in cases], arm)
        for case, query, length in zip(cases, queries, tokens, strict=True):
            started = time.perf_counter()
            ranking = sorted_ranking(docs @ query, corpus)
            rows.append(record(run, "input", case, arm, ranking, length, corpus,
                               time.perf_counter() - started))
        summaries[arm] = group_summary([row for row in rows if row["arm"] == arm])
    # A is a human/engineering fact baseline, not an automatic Memory mechanism.
    selected = max(["B_b2", "C_b2_b1"],
                   key=lambda arm: (summaries[arm]["ndcg_10"], summaries[arm]["mrr"],
                                    -summaries[arm]["mean_tokens"]))
    summaries["selected_automatic_input"] = selected
    summaries["decision_scope"] = "two synthetic employee groups; provisional, A is fact baseline"
    save_outcome(run, "input", rows, summaries)
    return selected


def run_stage2(run, model, corpus, probes):
    queries, query_sparse, query_tokens = model.get([case["text"] for case in probes], "probes")
    outputs = {}
    corpora = {}
    rows = []
    # Representation selection is development dense only; hybrid not allowed to influence it.
    for rep in ["description_or_top", "top", "topks"]:
        texts = [(row["texts"]["description"] or row["texts"]["top"])
                 if rep == "description_or_top" else row["texts"][rep] for row in corpus]
        docs, sparse, tokens = model.get(texts, f"corpus-{rep}")
        corpora[rep] = (docs, sparse, tokens)
        for index, case in enumerate(probes):
            if case["split"] == "development":
                ranking = sorted_ranking(docs @ queries[index], corpus)
                rows.append(record(run, "representation", case, rep, ranking,
                                   query_tokens[index], corpus))
    summaries = {rep: group_summary([row for row in rows if row["arm"] == rep]) for rep in corpora}
    selected_rep = max(summaries, key=lambda rep: (summaries[rep]["ndcg_10"], summaries[rep]["mrr"]))
    summaries["selected"] = selected_rep
    summaries["description_fallback_ids"] = [row["id"] for row in corpus if not row["texts"]["description"]]
    save_outcome(run, "representation", rows, summaries)
    docs, sparse, _ = corpora[selected_rep]
    rows = []
    for index, case in enumerate(probes):
        dense = sorted_ranking(docs @ queries[index], corpus)
        lexical = sorted_ranking(sparse_scores(query_sparse[index], sparse), corpus)
        outputs[case["case_id"]] = {"dense": dense, "sparse": lexical}
        if case["split"] == "development":
            for method, ranking in [("dense", dense), ("sparse", lexical),
                                    ("rrf", fuse_rankings(dense, lexical, depth=50, constant=60))]:
                rows.append(record(run, "method", case, method, ranking, query_tokens[index], corpus))
    summaries = {method: group_summary([row for row in rows if row["arm"] == method])
                 for method in ["dense", "sparse", "rrf"]}
    selected_method = max(summaries, key=lambda method: (summaries[method]["ndcg_10"], summaries[method]["mrr"]))
    summaries["selected"] = selected_method
    save_outcome(run, "method", rows, summaries)
    return selected_rep, selected_method, corpora[selected_rep], (queries, query_sparse, query_tokens), outputs


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("run")
    args = parser.parse_args()
    run = HERE / args.run
    run.mkdir(exist_ok=False)
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    for name in ["corpus", "cases", "protocol", "probes"]:
        if sha(HERE / f"{name}.{'md' if name == 'protocol' else 'json'}") != manifest[f"{name}_sha256"]:
            raise ValueError(f"Frozen {name} changed")
    corpus = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    probes = json.loads((HERE / "probes.json").read_text(encoding="utf-8"))
    model = Embeddings()
    write_json(run / "manifest.json", {"started_utc": datetime.now(UTC).isoformat(),
               "base_manifest_sha256": sha(HERE / "manifest.json"),
               "probes_sha256": sha(HERE / "probes.json"), "runtime": model.runtime,
               "model_fingerprint": model.model_key,
               "script_sha256": sha(Path(__file__)), "evaluator_sha256": sha(HERE / "evaluation.py"),
               "validation_sha256": sha(HERE / "validation.py"),
               "environment_sha256": sha(HERE / "environment.json")})
    try:
        selected_input = run_stage1(run, model, corpus, cases)
        selected_rep, selected_method, docs, queries, outputs = run_stage2(run, model, corpus, probes)
        from validation import parameter_and_database_checks
        parameter_and_database_checks(run, corpus, probes, selected_rep, selected_method, docs, queries, outputs)
        write_json(run / "complete.json", {"selected_input": selected_input,
                   "selected_representation": selected_rep, "selected_method": selected_method,
                   "cache_sha256": sha(model.path), "cache_byte_prefix_length": model.path.stat().st_size,
                   "cache_path": model.path.relative_to(HERE).as_posix(),
                   "used_cache_keys": sorted(model.used_keys),
                   "finished_utc": datetime.now(UTC).isoformat()})
    except Exception as exc:
        write_json(run / "failure.json", {"type": type(exc).__name__, "message": str(exc),
                                          "utc": datetime.now(UTC).isoformat()})
        raise
    finally:
        model.client.close()


if __name__ == "__main__":
    main()
