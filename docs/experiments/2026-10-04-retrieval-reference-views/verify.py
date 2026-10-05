"""Independently audit saved navigation against frozen inputs and exact sources."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_inputs():
    manifest = read(HERE / "execution-manifest.json")
    for relative, identity in manifest["inputs"].items():
        raw = (ROOT / relative).read_bytes()
        require(len(raw) == identity["bytes"] and sha(raw) == identity["sha256"],
                f"Bound input changed: {relative}")
    corpus = read(HERE.parent / "2026-10-04-occupation-retrieval/corpus.json")
    previous = HERE.parent / "2026-10-04-retrieval-input-boundaries"
    rows = [json.loads(line) for line in (previous / "metrics.jsonl").read_text(
        encoding="utf-8").splitlines()]
    selected = [x for x in rows if (x["variant"], x["method"], x["n"], x["k"])
                == ("original_messages", "quota_rerank", 20, 5)]
    originals = {x["case_id"]: x for x in read(previous / "inputs.json")
                 if x["variant"] == "original_messages"}
    return corpus, selected, originals


def resolve(sources: dict, ref: dict):
    require(set(ref) == {"doc_id", "source_sha256", "pointer"}, "Invalid reference shape")
    require(ref["doc_id"] in sources, "Missing referenced document")
    record = sources[ref["doc_id"]]
    raw = record["source_utf8_exact"].encode("utf-8")
    require(ref["source_sha256"] == record["source_sha256"] == sha(raw),
            "Reference source hash mismatch")
    value = json.loads(record["source_utf8_exact"])
    pointer = ref["pointer"]
    require(isinstance(pointer, str) and (pointer == "" or pointer.startswith("/")),
            "Invalid JSON Pointer")
    if pointer:
        for part in pointer[1:].split("/"):
            key = part.replace("~1", "/").replace("~0", "~")
            if isinstance(value, list):
                require(key.isdecimal() and str(int(key)) == key, "Invalid array index")
                require(int(key) < len(value), "Missing array entry")
                value = value[int(key)]
            else:
                require(isinstance(value, dict) and key in value, "Missing object entry")
                value = value[key]
    return value


def audit(corpus: list, rows: list, originals: dict, records: list,
          catalog: list, views: list) -> dict:
    require(len(corpus) == len(records) == len(catalog) == 805, "Source scope mismatch")
    require(len(rows) == len(originals) == len(views) == 22, "Case scope mismatch")
    by_id = {d["id"]: d for d in corpus}
    sources = {r["doc_id"]: r for r in records}
    outlines = {d["doc_id"]: d for d in catalog}
    require(len(by_id) == len(sources) == len(outlines) == 805, "Duplicate source identity")
    require(set(by_id) == set(sources) == set(outlines), "Missing source identity")
    groups = blocks = shared_groups = uncoded_groups = 0
    for identifier, doc in by_id.items():
        record, outline = sources[identifier], outlines[identifier]
        raw = record["source_utf8_exact"].encode("utf-8")
        require(record["source_path"] == doc["source"], "Source path changed")
        require(sha(raw) == record["source_sha256"] == doc["source_sha256"], "Source bytes changed")
        require(raw == (ROOT / doc["source"]).read_bytes(), "Source is not exact frozen bytes")
        data = json.loads(raw)
        require(outline["title"] == doc["title"], "Occupation label changed")
        require(outline["task_catalog_scope"] == "all_groups_in_frozen_json_not_pdf_completeness",
                "Unqualified catalog completeness")
        for key, pointer in [("profile_ref", "/ocs_profile"), ("version_ref", "/version_info")]:
            require(outline[key] == {"doc_id": identifier, "source_sha256": doc["source_sha256"],
                                     "pointer": pointer}, "Wrong profile/version location")
            require(resolve(sources, outline[key]) == data[pointer[1:]], "Unreadable metadata")
        units = data["ocs_content"]["ocu_units"]
        require(len(outline["units"]) == len(units), "Missing unit")
        for ui, unit in enumerate(units):
            saved = outline["units"][ui]
            pointer = f"/ocs_content/ocu_units/{ui}"
            require(saved["unit_ref"] == {"doc_id": identifier, "source_sha256": doc["source_sha256"],
                                          "pointer": pointer}, "Wrong unit location")
            require(resolve(sources, saved["unit_ref"]) == unit, "Unreadable unit")
            require((saved["unit_code"], saved["unit_name"]) == (unit["ocu_code"], unit["ocu_name"]),
                    "Unit label changed")
            require(len(saved["groups"]) == len(unit["tasks"]), "Missing or duplicated task group")
            for ti, task in enumerate(unit["tasks"]):
                group = saved["groups"][ti]
                require(group["group_ref"] == {"doc_id": identifier,
                        "source_sha256": doc["source_sha256"], "pointer": f"{pointer}/tasks/{ti}"},
                        "Wrong task group location")
                require(resolve(sources, group["group_ref"]) == task, "Unreadable whole task group")
                require(group["task_codes"] == task["task_codes"], "Task names changed")
                require(group["block_count"] == len(task["competency_blocks"]), "Shared blocks changed")
                groups += 1
                blocks += len(task["competency_blocks"])
                shared_groups += len(task["task_codes"]) > 1
                uncoded_groups += not task["task_codes"] or any(not t.get("code") for t in task["task_codes"])
    view_by_case = {v["case_id"]: v for v in views}
    require(len(view_by_case) == 22 and set(view_by_case) == set(originals)
            == {r["case_id"] for r in rows}, "Missing or duplicated case")
    query_count = edge_count = role_count = role_groups = repeated_roles = chars = 0
    for row in rows:
        view, original = view_by_case[row["case_id"]], originals[row["case_id"]]
        require(set(view) == {"case_id", "input_variant", "work_content_references",
                            "occupation_overviews", "baseline_top_characters"}, "Unvalidated case claims")
        require(view["input_variant"] == "original_messages", "Misidentified input")
        queries, roles = view["work_content_references"], view["occupation_overviews"]
        require(len(queries) == row["query_count"] == len(original["passages"]), "Query lost")
        expected_ids = [d["id"] for d in row["selected"]]
        require([r["doc_id"] for r in roles] == expected_ids and len(set(expected_ids)) == len(roles),
                "Returned documents changed")
        require(len(roles) == row["returned"], "Returned count changed")
        expected_edges = {i: [] for i in range(1, len(queries) + 1)}
        for selected, role in zip(row["selected"], roles):
            identifier = selected["id"]
            require(set(role) == {"doc_id", "title", "catalog_doc_id", "source_ref", "query_ids",
                                  "task_alignment"}, "Unvalidated occupation claim")
            require(role["title"] == by_id[identifier]["title"] and role["catalog_doc_id"] == identifier,
                    "Wrong occupation outline")
            require(role["source_ref"] == {"doc_id": identifier, "source_sha256": by_id[identifier]["source_sha256"],
                                           "pointer": ""}, "Wrong whole source reference")
            require(role["query_ids"] == [e["passage"] for e in selected["matches"]], "Merged query lost")
            require(role["task_alignment"] == "not_evaluated", "False occupation task alignment")
            resolve(sources, role["source_ref"])
            # Other tasks remain reachable through the whole outline, irrespective of query scores.
            for unit in outlines[identifier]["units"]:
                for group in unit["groups"]:
                    resolve(sources, group["group_ref"])
                    role_groups += 1
            repeated_roles += len(role["query_ids"]) > 1
            for edge in selected["matches"]:
                expected_edges[edge["passage"]].append((identifier, edge))
        for i, query in enumerate(queries, 1):
            require(set(query) == {"query_id", "text", "origin", "matches"}, "Unvalidated work claim")
            require((query["query_id"], query["text"], query["origin"])
                    == (i, original["passages"][i - 1], original["origins"][i - 1]), "Query provenance changed")
            actual = []
            for match in query["matches"]:
                require(set(match) == {"doc_id", "source_ref", "match_level", "task_alignment",
                                       "retrieval_evidence"}, "Unvalidated work alignment claim")
                require(match["match_level"] == "document" and match["task_alignment"] == "not_evaluated",
                        "Document retrieval presented as task alignment")
                require(match["source_ref"] == {"doc_id": match["doc_id"],
                        "source_sha256": by_id[match["doc_id"]]["source_sha256"], "pointer": ""},
                        "Document match presented as a fragment")
                resolve(sources, match["source_ref"])
                actual.append((match["doc_id"], match["retrieval_evidence"]))
            require(actual == sorted(expected_edges[i], key=lambda x: x[1]["rerank_rank"]),
                    "Query match or score lost/changed")
            query_count += 1
            edge_count += len(actual)
        count_chars = sum(len(by_id[x]["texts"]["top"]) for x in expected_ids)
        require(count_chars == row["characters"] == view["baseline_top_characters"], "Body count changed")
        chars += count_chars
        role_count += len(roles)
    return {"sources": len(sources), "task_groups": groups, "competency_blocks": blocks,
            "multi_name_shared_groups": shared_groups, "uncoded_task_groups": uncoded_groups,
            "cases": len(views), "queries": query_count, "query_document_edges": edge_count,
            "occupation_entries_across_cases": role_count, "multi_query_occupation_entries": repeated_roles,
            "readable_catalog_groups_across_returned_sources": role_groups,
            "mean_documents": role_count / len(views), "mean_top_characters": chars / len(views)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    corpus, rows, originals = load_inputs()
    records = [json.loads(line) for line in (HERE / "sources.jsonl").read_text(encoding="utf-8").splitlines()]
    catalog, views = read(HERE / "catalog.json"), read(HERE / "reference-views.json")
    stats = audit(corpus, rows, originals, records, catalog, views)
    rejected = []
    sources = {r["doc_id"]: r for r in records}
    first_ref = catalog[0]["profile_ref"]
    for name, change in [
        ("wrong_hash", {**first_ref, "source_sha256": "0" * 64}),
        ("missing_pointer", {**first_ref, "pointer": "/ocs_content/ocu_units/999999"}),
        ("negative_array_index", {**first_ref, "pointer": "/ocs_content/ocu_units/-1"}),
        ("missing_document", {**first_ref, "doc_id": "missing"}),
    ]:
        try:
            resolve(sources, change)
        except ValueError:
            rejected.append(name)
        else:
            raise ValueError(f"Negative reference accepted: {name}")
    broken_catalog = copy.deepcopy(catalog)
    broken_catalog[0]["units"][0]["groups"].pop()
    lost_edge = copy.deepcopy(views)
    lost_edge[0]["work_content_references"][0]["matches"].pop()
    false_fragment = copy.deepcopy(views)
    false_fragment[0]["work_content_references"][0]["matches"][0]["match_level"] = "task"
    changed_source = copy.deepcopy(records)
    changed_source[0]["source_utf8_exact"] += " "
    for name, fixture in [
        ("missing_catalog_group", (records, broken_catalog, views)),
        ("lost_query_edge", (records, catalog, lost_edge)),
        ("false_task_alignment", (records, catalog, false_fragment)),
        ("changed_source_body", (changed_source, catalog, views)),
    ]:
        try:
            audit(corpus, rows, originals, *fixture)
        except ValueError:
            rejected.append(name)
        else:
            raise ValueError(f"Negative packet accepted: {name}")
    result = {"scope": "offline_structure_only", "passed": True,
              "statistics": stats, "negative_checks_rejected": rejected,
              "new_retrieval_calls": 0, "model_calls": 0}
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as out:
            json.dump(result, out, ensure_ascii=False, indent=2)
            out.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
