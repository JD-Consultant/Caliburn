"""Fixed candidate evaluation. No choices or calibration from this holdout."""
import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime

import numpy as np
from qdrant_client import QdrantClient, models

from support import FIRST, HERE, decision, load_module, published_b2

sys.path.insert(0, str(FIRST))
baseline = load_module("occ2_fixed_retrieval", FIRST / "experiment.py")
from evaluation import ranking_check, validate_dense
sys.path.pop(0)
baseline.HERE = HERE


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summaries(rows):
    result = {}
    for arm in ("B2", "raw_employee"):
        result[arm] = {}
        for split in ("development", "holdout", "all"):
            group = [r for r in rows if r["arm"] == arm and (split == "all" or r["split"] == split)]
            positive = [r for r in group if r["kind"] == "positive"]
            negative = [r for r in group if r["kind"] != "positive"]
            result[arm][split] = {"positive_cases": len(positive),
                **{key: float(np.mean([r[key] for r in positive])) for key in ("hit_1", "hit_5", "hit_10", "mrr", "ndcg_10")},
                "primary_in_top10": sum(r["primary_in_top10"] for r in positive),
                "empty_positive_queries": sum(r["query_empty"] for r in positive),
                "negative_cases": len(negative), "empty_negative_queries": sum(r["query_empty"] for r in negative),
                "legacy_threshold_positive_accepts": sum(r["legacy_threshold_accepts"] for r in positive),
                "legacy_threshold_false_accepts": sum(r["legacy_threshold_accepts"] for r in negative),
                "negative_by_kind": {kind: {"cases": sum(r["kind"] == kind for r in negative),
                    "false_accepts": sum(r["legacy_threshold_accepts"] for r in negative if r["kind"] == kind)}
                    for kind in ("insufficient", "out_of_corpus")}}
    return result


def main(run_dir):
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    for path, expected in [(HERE / "cases.json", manifest["cases_sha256"]),
                            (HERE / "protocol.md", manifest["protocol_sha256"]),
                            (FIRST / "corpus.json", manifest["corpus_sha256"])]:
        if sha(path) != expected:
            raise ValueError("Frozen protocol or labels changed")
    assert json.loads((run_dir / "complete.json").read_text())["cases"] == 14
    out = run_dir / "retrieval"
    out.mkdir(exist_ok=False)
    (HERE / "cache").mkdir(exist_ok=True)
    old_cache = FIRST / "cache/20f95996a7ef4d574c29bed8625e84277aee1a73b8d097f5b45b5320ddb27bd8.jsonl"
    new_cache = HERE / "cache" / old_cache.name
    if new_cache.exists():
        raise ValueError("This run requires a fresh copied cache")
    shutil.copyfile(old_cache, new_cache)
    model = baseline.Embeddings()
    client = QdrantClient(url="http://127.0.0.1:6335", timeout=60, trust_env=False)
    corpus = json.loads((FIRST / "corpus.json").read_text(encoding="utf-8"))
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    name = json.loads((FIRST / "candidate-01/collection.json").read_text())["name"]
    try:
        assert model.path == new_cache
        docs, _, _ = model.get([r["texts"]["top"] for r in corpus], "fixed805TOP")
        info = client.get_collection(name)
        assert info.points_count == 805
        actual = []
        offset = None
        while True:
            points, offset = client.scroll(name, limit=256, offset=offset, with_vectors=["dense"], with_payload=True)
            actual.extend(points)
            if offset is None:
                break
        assert len(actual) == 805 and len({p.id for p in actual}) == 805
        errors = []
        for p in actual:
            assert p.payload == {"ocs_code": corpus[int(p.id)]["id"], "title": corpus[int(p.id)]["title"]}
            vector = validate_dense([p.vector["dense"]], 1)[0]
            errors.append(float(np.max(np.abs(vector - docs[int(p.id)]))))
        assert max(errors) < 1e-6
        dump(out / "manifest.json", {"started_utc": datetime.now(UTC).isoformat(), "generation_manifest_sha256": sha(run_dir / "manifest.json"),
            "corpus_sha256": sha(FIRST / "corpus.json"), "runtime": model.runtime, "model_key": model.model_key,
            "cache_original_bytes": old_cache.stat().st_size, "cache_original_sha256": sha(old_cache),
            "collection": name, "collection_configuration": info.model_dump(mode="json"),
            "database_corpus_points": len(actual), "database_vectors_max_error": max(errors),
            "fixed": {"input": "published_B2", "representation": "TOP", "method": "dense_exact", "k": 10},
            "legacy_threshold": 0.675, "threshold_status": "previously rejected, diagnostic only",
            "source_contents": {p.name: p.read_text(encoding="utf-8") for p in (HERE / "retrieve.py", HERE / "support.py", HERE / "test_support.py")}})
        prepared = []
        for case in cases:
            snapshot = json.loads((run_dir / case["case_id"] / "snapshot.json").read_text(encoding="utf-8"))
            prepared.append({"case_id": case["case_id"], "B2": published_b2(snapshot),
                "raw_employee": "\n\n".join(case["employee_messages"]), "snapshot_sha256": sha(run_dir / case["case_id"] / "snapshot.json")})
        dump(out / "queries.json", prepared)
        rows, db_checks = [], []
        for case, query in zip(cases, prepared, strict=True):
            for arm in ("B2", "raw_employee"):
                text = query[arm]
                if text is None:
                    ranking, tokens = [], 0
                else:
                    dense, _, sizes = model.get([text], f"{case['case_id']}-{arm}")
                    tokens = sizes[0]
                    ranking = baseline.sorted_ranking(docs @ dense[0], corpus)
                    response = client.query_points(name, query=dense[0].tolist(), using="dense", limit=10,
                        with_payload=True, search_params=models.SearchParams(exact=True)).points
                    returned = [(p.payload["ocs_code"], p.score) for p in response]
                    check = ranking_check(returned, ranking)
                    assert check["correct"]
                    db_checks.append({"case_id": case["case_id"], "arm": arm, "exact": True,
                        **check, "returned": [{"id": k, "score": v} for k, v in returned]})
                row = baseline.record(out, "fixed", case, arm, ranking, tokens, corpus)
                row.update({"kind": case["kind"], "query_empty": text is None, **decision(case, ranking)})
                rows.append(row)
                print(json.dumps({k: row[k] for k in ("case_id", "arm", "hit_10", "primary_rank", "top1_score", "legacy_threshold_accepts")}), flush=True)
        dump(out / "metrics.json", rows)
        dump(out / "summary.json", summaries(rows))
        dump(out / "database-checks.json", db_checks)
        with (out / "metrics.csv").open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        dump(out / "complete.json", {"finished_utc": datetime.now(UTC).isoformat(),
            "rows": len(rows), "database_queries": len(db_checks), "cache_path": model.path.relative_to(HERE).as_posix(),
            "cache_sha256": sha(model.path), "cache_bytes": model.path.stat().st_size,
            "used_cache_keys": sorted(model.used_keys)})
    finally:
        model.client.close()
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", default="run-02", nargs="?")
    args = parser.parse_args()
    main(HERE / args.run)
