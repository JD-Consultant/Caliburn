"""Fresh GPU query against the new frozen public-source index; no OpenAI calls."""

import json
import time
from pathlib import Path

import httpx


query = "物流中心倉庫管理員，負責收貨驗收、上架、揀貨補貨、庫存盤點與客戶退貨入庫"
start = time.monotonic()
with httpx.Client(base_url="http://ocs-indexer:8000", timeout=180, trust_env=False) as client:
    response = client.post("/occupation-references:search", json={"query": query, "limit": 3})
    response.raise_for_status()
    result = response.json()
    fixed = []
    for hit in result["references"]:
        reference = hit["reference"]
        read = client.get("/occupation-references/" + reference["reference_id"])
        read.raise_for_status()
        if read.json() != reference:
            raise RuntimeError("search and fixed source differ")
        first_task = reference["units"][0]["tasks"][0]
        task = client.get("/occupation-references/" + reference["reference_id"] + "/tasks/" + first_task["task_id"])
        task.raise_for_status()
        fixed.append({"reference_id": reference["reference_id"], "task": task.json()})
    unavailable = client.get("/occupation-references/not-an-id")
    if unavailable.status_code not in (404, 422):
        raise RuntimeError("invalid target not rejected")
record = {"query": query, "elapsed_seconds": time.monotonic() - start,
          "search": result, "fixed_reads": fixed, "invalid_target_status": unavailable.status_code}
with Path("/witness/rag-fresh-query.json").open("x", encoding="utf-8") as output:
    json.dump(record, output, ensure_ascii=False, indent=2)
print(json.dumps({"elapsed_seconds": record["elapsed_seconds"], "candidates": len(fixed),
                  "titles": [hit["reference"].get("title", hit["reference"].get("ocs_code"))
                             for hit in result["references"]]}, ensure_ascii=False))
