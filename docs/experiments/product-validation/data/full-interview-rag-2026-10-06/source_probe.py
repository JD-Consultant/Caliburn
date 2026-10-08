"""Read saved fixed sources/diffs through public API; never confirm references implicitly."""

import asyncio
import json
from collections import Counter
from pathlib import Path

import httpx2

HERE = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8106"


async def main():
    state = json.loads((HERE / "state.json").read_text(encoding="utf-8"))
    path = "/api/job-files/" + state["file_id"] + "/jd/sources"
    async with httpx2.AsyncClient(base_url=BASE, timeout=120, trust_env=False) as client:
        response = await client.get(path)
        response.raise_for_status()
        before = response.json()
        records = []
        for reference in before["references"]:
            location = path + "/" + reference["citation_id"]
            parameters = {"revision_id": before["revision_id"]}
            content = await client.get(location, params=parameters)
            content.raise_for_status()
            fixed = content.json()
            if fixed["revision_id"] != before["revision_id"] or fixed["citation_id"] != reference["citation_id"]:
                raise RuntimeError("Fixed source identity mismatch")
            changes = await client.get(location + "/changes", params=parameters)
            changes.raise_for_status()
            records.append({"reference": reference, "fixed": fixed, "changes": changes.json()})
        response = await client.get(path)
        response.raise_for_status()
        after = response.json()
        if after != before:
            raise RuntimeError("Reading sources or diff changed the review state")
    with (HERE / f"turn-{state['turn']:02}-source-reads.json").open("x", encoding="utf-8") as output:
        json.dump({"before": before, "reads": records, "after": after}, output, ensure_ascii=False, indent=2)
    print(json.dumps({"sources_read": len(records), "kinds": dict(Counter(x['source_kind'] for x in before['references'])),
                      "pending_unchanged_by_read": sum(x['needs_recheck'] for x in before['references'])}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
