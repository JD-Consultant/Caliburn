"""Formal HTTP fixed citation bodies and anonymous quality-only bundles."""

import json
from uuid import uuid4


async def collect_sources(client, path, overview):
    revision = overview["revision_id"]
    references = overview["references"]
    if len(references) > 512:
        raise RuntimeError("Too many citations for this finite experiment")
    queue = [(item["citation_id"], None, 0) for item in references]
    visited = set()
    results = []
    while queue:
        citation, source_ref, depth = queue.pop(0)
        if (citation, source_ref) in visited:
            continue
        if len(visited) >= 2048:
            raise RuntimeError("Fixed source chain exceeds experiment bound")
        visited.add((citation, source_ref))
        params = {"revision_id": revision}
        if source_ref is not None:
            params["source_ref"] = source_ref
        response = await client.get(path + "/jd/sources/" + citation, params=params)
        response.raise_for_status()
        body = response.json()
        if body["revision_id"] != revision or body["citation_id"] != citation:
            raise RuntimeError("Fixed source response belongs to another citation")
        results.append({"source_ref": source_ref, **body})
        if depth < 3:
            queue.extend(
                (citation, link["source_ref"], depth + 1)
                for link in body["content"].get("references", [])
            )
    return {
        "formal_revision_id": revision,
        "entries": results,
        "read_policy": "exact formal citation revision and its fixed reachable source_ref chain; no latest replacement",
    }


def write_blind_bundle(case_directory, destination, mapping_path):
    destination.mkdir(exist_ok=True)
    opaque = uuid4().hex

    def read(name):
        return json.loads((case_directory / name).read_text(encoding="utf-8"))

    interviews = read("formal-interviews.json")
    originals = [
        {
            key: item[key]
            for key in ["source_id", "interview_sequence", "speaker", "interview_text"]
        }
        for item in interviews["messages"]
        if item["speaker"] == "employee"
    ]
    bundle = {
        "case_id": opaque,
        "formal_jd": read("formal-jd.json"),
        "employee_originals": originals,
        "fixed_source_contents": read("fixed-source-contents.json"),
    }
    (destination / (opaque + ".json")).write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    mapping = (
        json.loads(mapping_path.read_text(encoding="utf-8"))
        if mapping_path.exists()
        else {}
    )
    mapping[opaque] = str(case_directory)
    mapping_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return opaque
