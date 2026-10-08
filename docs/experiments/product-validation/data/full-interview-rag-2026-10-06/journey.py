"""HTTP-only synthetic employee driver; real installed app owns the agent/DB loop.

The evaluator supplies short responses using frozen private notes. No persona rubric
is sent to A; responses are not automatically synthesized or evaluated by another LLM.
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx2

HERE = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8106"


def save(name, body):
    with (HERE / name).open("x", encoding="utf-8") as output:
        json.dump(body, output, ensure_ascii=False, indent=2)


async def observe_activity(client, path, events):
    try:
        async with client.stream("GET", path + "/activity-stream", timeout=None) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith(("event:", "data:")):
                    events.append({"at": time.time(), "line": line})
    except asyncio.CancelledError:
        raise
    except Exception as error:
        events.append({"observer_error": type(error).__name__})


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "send", "read", "export"])
    parser.add_argument("text", nargs="?")
    arguments = parser.parse_args()
    async with httpx2.AsyncClient(base_url=BASE, timeout=120, trust_env=False,
                                  headers={"Origin": BASE}) as client:
        async def get(path):
            result = await client.get(path)
            result.raise_for_status()
            return result.json()
        if arguments.action == "create":
            response = await client.post("/api/job-files", json={"command_id": str(uuid4()),
                "display_name": "倉庫管理員完整訪談驗證", "employee_name": "小陳"})
            response.raise_for_status()
            state = {"file_id": response.json()["job_file_id"], "turn": 0}
            save("state.json", state)
            save("created.json", response.json())
            print(json.dumps(state))
            return
        state = json.loads((HERE / "state.json").read_text(encoding="utf-8"))
        path = "/api/job-files/" + state["file_id"]
        if arguments.action == "export":
            response = await client.get(path + "/jd/export.pdf")
            response.raise_for_status()
            filename = arguments.text or 'formal-jd.pdf'
            with (HERE / filename).open("xb") as output:
                output.write(response.content)
            print(json.dumps({"bytes": len(response.content), "signature": response.content[:4].decode()}))
            return
        if arguments.action == "read":
            messages = (await get(path + "/interviews"))["messages"]
            print(json.dumps(messages[-2:], ensure_ascii=False))
            return
        number = state["turn"] + 1
        stem = f"turn-{number:02}"
        before = {section: await get(path + "/jd/" + section)
                  for section in ["profile", "work", "sources"]}
        save(stem + "-before.json", before)
        command_id = str(uuid4())
        save(stem + "-input.json", {"command_id": command_id, "text": arguments.text})
        response = await client.post(path + "/inputs", json={"command_id": command_id, "text": arguments.text})
        response.raise_for_status()
        accepted = response.json()
        save(stem + "-accepted.json", accepted)
        execution = path + "/consultant-turns/" + accepted["execution_id"]
        print(json.dumps({"turn": number, "execution_id": accepted["execution_id"]}), flush=True)
        events = []
        observer = asyncio.create_task(observe_activity(client, execution, events))
        started = time.monotonic()
        captured = False
        try:
            while time.monotonic() - started < 600:
                current = await get(execution)
                if current.get("candidate") and not captured:
                    save(stem + "-preview.json", current)
                    captured = True
                if current["status"] in {"completed", "failed", "cancelled", "paused"}:
                    break
                await asyncio.sleep(2)
            else:
                raise RuntimeError("Turn observation timeout; do not submit again")
        finally:
            observer.cancel()
            try:
                await observer
            except asyncio.CancelledError:
                pass
            save(stem + "-activity.json", events)
        messages = await get(path + "/interviews")
        after = {section: await get(path + "/jd/" + section)
                 for section in ["profile", "work", "sources"]}
        summaries = await get(execution + "/reasoning-summaries")
        save(stem + "-result.json", {"status": current, "elapsed_seconds": time.monotonic() - started,
                                    "interviews": messages, "jd": after, "reasoning_summaries": summaries})
        state["turn"] = number
        (HERE / "state.json").write_text(json.dumps(state), encoding="utf-8")
        print(json.dumps({"status": current["status"], "elapsed_seconds": round(time.monotonic() - started, 1),
                          "activity_events": len(events), "summaries": len(summaries),
                          "last_messages": messages["messages"][-2:]}, ensure_ascii=False), flush=True)
        if current["status"] != "completed":
            raise RuntimeError("Non-completed Turn; no automatic retry")


if __name__ == "__main__":
    asyncio.run(main())
