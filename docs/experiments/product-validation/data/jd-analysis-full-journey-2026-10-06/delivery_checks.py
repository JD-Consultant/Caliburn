"""Free HTTP checks, separate from the employee interview and model evaluation."""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

import httpx2

HERE = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8107"


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["replay", "manual"])
    parser.add_argument("--completed-turn", type=int, default=11)
    arguments = parser.parse_args()
    path = "/api/job-files/" + load("state.json")["file_id"]
    async with httpx2.AsyncClient(
        base_url=BASE, headers={"Origin": BASE}, timeout=120, trust_env=False
    ) as client:

        async def get(suffix):
            response = await client.get(path + suffix)
            response.raise_for_status()
            return response.json()

        if arguments.action == "replay":
            stem = f"turn-{arguments.completed_turn:02}"
            assert load(stem + "-result.json")["status"]["status"] == "completed"
            original = load(stem + "-accepted.json")
            response = await client.post(
                path + "/inputs", json=load(stem + "-input.json")
            )
            response.raise_for_status()
            assert response.json()["execution_id"] == original["execution_id"]
            result = {
                "original": original,
                "replayed": response.json(),
                "same_execution": True,
            }
        else:
            current = (await get("/consultant-turns/current"))["turn"]
            if current and current["status"] in ["active", "paused"]:
                raise RuntimeError("Do not edit a live consultant candidate")
            before = await get("/jd/conditions")
            old_sources = await get("/jd/sources")
            condition = next(
                item
                for item in before["conditions"]
                if item["kind"] == "schedule_travel"
            )
            value = condition["text"].replace("七", "7")
            assert value != condition["text"], (
                "Only change the already confirmed time's typography"
            )
            command = {
                "command_id": str(uuid4()),
                "expected_revision_id": before["revision_id"],
                "change": {
                    "action": "revise_condition",
                    "condition_id": condition["condition_id"],
                    "changes": [{"field": "text", "value": value}],
                },
            }
            response = await client.post(path + "/jd/conditions", json=command)
            response.raise_for_status()
            after = await get("/jd/conditions")
            assert after == response.json()
            sources = await get("/jd/sources")
            refs = [
                item
                for item in sources["references"]
                if item["target"]["item_id"] == condition["condition_id"]
            ]
            assert refs and all(
                item["jd_changed"] and item["needs_recheck"] for item in refs
            )
            reads = []
            for reference in refs:
                location = "/jd/sources/" + reference["citation_id"]
                revision = "?revision_id=" + sources["revision_id"]
                reads.append(
                    {
                        "reference": reference,
                        "content": await get(location + revision),
                        "changes": await get(location + "/changes" + revision),
                    }
                )
            assert await get("/jd/sources") == sources, (
                "Reading must not confirm a reference"
            )
            repeated = await client.post(path + "/jd/conditions", json=command)
            repeated.raise_for_status()
            assert repeated.json() == response.json(), "Replay created another revision"
            stale = {**command, "command_id": str(uuid4())}
            conflict = await client.post(path + "/jd/conditions", json=stale)
            assert conflict.status_code == 409
            result = {
                "before": before,
                "sources_before": old_sources,
                "command": command,
                "after": after,
                "sources_after": sources,
                "reads": reads,
                "same_command_replay": True,
                "stale_revision_status": conflict.status_code,
                "stale_revision_error": conflict.json(),
                "scope": "Separate typography probe, not a natural employee correction",
            }
    with (HERE / (arguments.action + "-delivery-probe.json")).open(
        "x", encoding="utf-8"
    ) as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    print(json.dumps({"action": arguments.action, "passed": True}))


if __name__ == "__main__":
    asyncio.run(main())
