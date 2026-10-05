"""Offline reference navigation spike. Never performs retrieval or model calls."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CORPUS = HERE.parent / "2026-10-04-occupation-retrieval/corpus.json"
PREVIOUS = HERE.parent / "2026-10-04-retrieval-input-boundaries"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(name: str, data) -> None:
    # A failed or completed run must remain visible; use a new packet to revise it.
    with (HERE / name).open("x", encoding="utf-8", newline="\n") as out:
        json.dump(data, out, ensure_ascii=False, indent=2)
        out.write("\n")


def reference(doc: dict, pointer: str) -> dict:
    return {"doc_id": doc["id"], "source_sha256": doc["source_sha256"],
            "pointer": pointer}


def main() -> None:
    bound_paths = [CORPUS, PREVIOUS / "cases-observed.json",
                   PREVIOUS / "inputs.json", PREVIOUS / "metrics.jsonl",
                   HERE / "prepare.py", HERE / "verify.py", HERE / "protocol.md",
                   ROOT / "docs/specs/2026-10-04-public-reference-retrieval-design.md"]
    save("execution-manifest.json", {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "offline_structure_only_no_new_rankings",
        "variant": "original_messages", "method": "quota_rerank", "n": 20, "k": 5,
        "inputs": {str(p.relative_to(ROOT)).replace("\\", "/"): {
            "sha256": digest(p.read_bytes()), "bytes": p.stat().st_size}
            for p in bound_paths},
    })
    corpus = read_json(CORPUS)
    inputs = {(x["case_id"], x["variant"]): x for x in read_json(PREVIOUS / "inputs.json")}
    cases = read_json(PREVIOUS / "cases-observed.json")
    metrics = [json.loads(line) for line in (PREVIOUS / "metrics.jsonl").read_text(
        encoding="utf-8").splitlines()]
    rows = [x for x in metrics if x["variant"] == "original_messages"
            and x["method"] == "quota_rerank" and x["n"] == 20 and x["k"] == 5]
    if len(corpus) != 805 or len(rows) != 22 or len(cases) != 22:
        raise ValueError("Unexpected frozen corpus or case scope")
    by_id = {x["id"]: x for x in corpus}
    if len(by_id) != len(corpus):
        raise ValueError("Duplicate document identity")
    sources, catalog = [], []
    for doc in corpus:
        source = ROOT / doc["source"]
        raw = source.read_bytes()
        if digest(raw) != doc["source_sha256"]:
            raise ValueError(f"Frozen source changed: {doc['id']}")
        original = raw.decode("utf-8")
        parsed = json.loads(original)
        sources.append({"doc_id": doc["id"], "source_path": doc["source"],
                        "source_sha256": doc["source_sha256"], "source_utf8_exact": original})
        units = []
        for ui, unit in enumerate(parsed["ocs_content"]["ocu_units"]):
            unit_pointer = f"/ocs_content/ocu_units/{ui}"
            groups = []
            for ti, task in enumerate(unit["tasks"]):
                groups.append({"group_ref": reference(doc, f"{unit_pointer}/tasks/{ti}"),
                               "task_codes": task["task_codes"],
                               "block_count": len(task["competency_blocks"])})
            units.append({"unit_ref": reference(doc, unit_pointer),
                          "unit_code": unit["ocu_code"], "unit_name": unit["ocu_name"],
                          "groups": groups})
        catalog.append({"doc_id": doc["id"], "title": doc["title"],
                        "profile_ref": reference(doc, "/ocs_profile"),
                        "version_ref": reference(doc, "/version_info"),
                        "task_catalog_scope": "all_groups_in_frozen_json_not_pdf_completeness",
                        "units": units})
    with (HERE / "sources.jsonl").open("x", encoding="utf-8", newline="\n") as out:
        for source in sources:
            out.write(json.dumps(source, ensure_ascii=False) + "\n")
    save("catalog.json", catalog)
    views = []
    for row in rows:
        original = inputs[row["case_id"], "original_messages"]
        if len(original["passages"]) != row["query_count"]:
            raise ValueError("Query count changed")
        queries = [{"query_id": i, "text": text, "origin": original["origins"][i - 1],
                    "matches": []} for i, text in enumerate(original["passages"], 1)]
        roles = []
        for selected in row["selected"]:
            doc = by_id[selected["id"]]
            query_ids = []
            for edge in selected["matches"]:
                index = edge["passage"] - 1
                if index < 0 or index >= len(queries):
                    raise ValueError("Match has an unknown query")
                queries[index]["matches"].append({
                    "doc_id": doc["id"], "source_ref": reference(doc, ""),
                    "match_level": "document", "task_alignment": "not_evaluated",
                    "retrieval_evidence": edge,
                })
                query_ids.append(edge["passage"])
            roles.append({"doc_id": doc["id"], "title": doc["title"],
                          "catalog_doc_id": doc["id"], "source_ref": reference(doc, ""),
                          "query_ids": query_ids, "task_alignment": "not_evaluated"})
        for query in queries:
            query["matches"].sort(key=lambda x: x["retrieval_evidence"]["rerank_rank"])
        views.append({"case_id": row["case_id"], "input_variant": "original_messages",
                      "work_content_references": queries, "occupation_overviews": roles,
                      "baseline_top_characters": row["characters"]})
    save("reference-views.json", views)
    print(json.dumps({"sources": len(sources), "cases": len(views),
                      "status": "prepared_not_yet_verified"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
