"""Prepare, then explicitly run one $0.05/900s comparison; never resume or retry."""

import argparse
import asyncio
import json
import os
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx2
from baseline_store import ROOT
from caliburn.adapters.openai_responses import (
    ResponseRequest,
    count_response_input,
    create_response,
    create_responses_client,
)
from caliburn.adapters.response_serialization import (
    function_result_item,
    response_input_items,
)
from openai.types.responses import ResponseFunctionToolCall
from reading_probe_materials import CASES, HERE, build_materials, invoke, probe_request
from study_guard import ResearchStop, StudyGuard
from study_manifest import claim_run, freeze_files, save_new, verify_files

OUTPUT = HERE / "reading-probe-01"
PRIOR = Decimal("1.425661625")
BUDGET = Decimal("0.05")
SECONDS = 900


def prepare() -> None:
    materials = build_materials()
    baseline = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
    files = [
        Path(__file__),
        *Path(__file__).parent.glob("reading_*.py"),
        HERE / "baseline_store.py",
        HERE / "memory_fixture.py",
        HERE / "study_guard.py",
        HERE / "study_manifest.py",
        HERE / "baseline.json",
        HERE / "continuation.json",
        HERE / "grading-cases.json",
        HERE / "live-01/trace.jsonl",
        ROOT / "apps/api/src/caliburn/adapters/openai_responses.py",
        ROOT / "apps/api/src/caliburn/adapters/response_serialization.py",
        ROOT / "apps/api/src/caliburn/adapters/openai_models.py",
        *[ROOT / item["path"] for item in baseline["source_files"]],
    ]
    files.extend(
        (ROOT / "apps/api/src/caliburn/contracts/generated/tools").glob("*.py")
    )
    hashes = freeze_files(files, root=ROOT, output=OUTPUT)
    schedule = []
    requests = {}
    for index, (case_id, (candidate, _)) in enumerate(CASES.items()):
        order = ("control", candidate) if index % 2 == 0 else (candidate, "control")
        for arm in order:
            schedule.append({"arm": arm, "case_id": case_id})
            requests[f"{arm}-{case_id}"] = probe_request(materials, arm, case_id)
    representatives = {
        arm: next(q for key, q in requests.items() if key.startswith(arm + "-"))
        for arm in ("control", "navigation", "precision")
    }
    grading = json.loads((HERE / "grading-cases.json").read_text(encoding="utf-8"))[
        "cases"
    ]
    save_new(OUTPUT / "materials.json", materials)
    save_new(OUTPUT / "requests.json", requests)
    save_new(
        OUTPUT / "criteria.json",
        {
            "map_present": {
                "facts": grading["c01"]["checks"],
                "navigation": "已有兩層 map；記錄額外 map 呼叫及其是否必要",
            },
            "map_absent": {
                "facts": grading["c01"]["checks"],
                "navigation": "仍能取得 map 並讀正文，不猜標題或向員工重問",
            },
            "historical": {
                "facts": grading["c04"]["checks"],
                "navigation": "舊期限可向原話查證；不拒查、不臆測舊期限",
            },
            "detail": {
                "facts": grading["c06"]["checks"],
                "scope": "未知不猜年限，不展開無關整份工作",
            },
            "narrow": {
                "facts": {"volume": "每日約15–20張進貨單；不是件數"},
                "scope": "不帶入整份工作，不捏造該數值的核准者",
            },
            "grade": ["complete", "partial", "omitted", "incorrect"],
            "restriction": "人工語意評分；不把關鍵詞命中、少讀取或API成功視為品質提升；不評JD保存",
        },
    )
    for name in ("materials.json", "requests.json", "criteria.json"):
        from study_manifest import file_hash

        hashes[(OUTPUT / name).relative_to(ROOT).as_posix()] = file_hash(OUTPUT / name)
    save_new(
        OUTPUT / "manifest.json",
        {
            "model": "gpt-6-luna",
            "effort": "high",
            "max_output_tokens": 16384,
            "batch_usd": str(BUDGET),
            "seconds": SECONDS,
            "prior_usd": str(PRIOR),
            "schedule": schedule,
            "files": hashes,
            "instructions": {
                arm: q["instructions"] for arm, q in representatives.items()
            },
            "tools": {arm: q["tools"] for arm, q in representatives.items()},
            "scope": "Frozen read-only source adapter; five Memory tools, no JD tools or database writes. Not full product replay.",
            "history": "Each episode starts fresh with original recent messages/maps. Precision cases additionally preload the same complete understanding. No opaque history reconstructed.",
            "limits": "One pair per case, no retries or post-result prompt changes; stop at first error/guard bound; max 8 model calls per episode.",
        },
    )
    print(json.dumps({"status": "prepared", "episodes": len(schedule), "paid": False}))


async def execute() -> None:
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    verify_files(manifest["files"], root=ROOT)
    requests = json.loads((OUTPUT / "requests.json").read_text(encoding="utf-8"))
    materials = json.loads((OUTPUT / "materials.json").read_text(encoding="utf-8"))
    claim_run(
        OUTPUT,
        {
            "authorization": "User approved US$0.05 / 15 minutes, cumulative US$2; no production changes",
            "prior_usd": str(PRIOR),
        },
    )
    guard = StudyGuard(OUTPUT, batch_usd=BUDGET, seconds=SECONDS, prior_usd=PRIOR)
    guard.frozen_policy = manifest
    completed = []
    outcome = {"status": "running"}
    try:
        async with create_responses_client(
            api_key=os.environ["OPENAI_API_KEY"],
            timeout_seconds=180,
            http_client=httpx2.AsyncClient(
                timeout=180,
                trust_env=False,
                follow_redirects=False,
                event_hooks={"request": [guard.request], "response": [guard.response]},
            ),
        ) as client:
            async with asyncio.timeout(SECONDS):
                for phase in manifest["schedule"]:
                    verify_files(manifest["files"], root=ROOT)
                    guard.phase = phase
                    key = f"{phase['arm']}-{phase['case_id']}"
                    snapshot = deepcopy(requests[key])
                    tool_reads = []
                    before = guard.summary()
                    for step in range(1, 9):
                        request = ResponseRequest.from_snapshot(snapshot)
                        await count_response_input(client, request)
                        response = await create_response(client, request)
                        snapshot["input"].extend(response_input_items(response))
                        calls = [
                            item
                            for item in response.output
                            if isinstance(item, ResponseFunctionToolCall)
                        ]
                        for call in calls:
                            result = invoke(materials, call.name, call.arguments)
                            output = json.dumps(result, ensure_ascii=False)
                            snapshot["input"].append(function_result_item(call, output))
                            tool_reads.append(
                                {
                                    "name": call.name,
                                    "arguments": call.arguments,
                                    "output": result,
                                }
                            )
                        if calls:
                            continue
                        final = "\n".join(
                            part.text
                            for item in response.output
                            if item.type == "message" and item.phase == "final_answer"
                            for part in item.content
                            if part.type == "output_text"
                        )
                        if not final:
                            raise ResearchStop("no_final_answer")
                        after = guard.summary()
                        numeric = (
                            "input_tokens",
                            "output_tokens",
                            "reasoning_tokens",
                            "cached_input_tokens",
                            "generation_calls",
                        )
                        save_new(
                            OUTPUT / f"answer-{key}.json",
                            {
                                **phase,
                                "answer": final,
                                "reads": tool_reads,
                                "steps": step,
                                "usage": {
                                    name: after[name] - before[name] for name in numeric
                                },
                                "estimated_usd": str(
                                    Decimal(after["batch_occupied_usd"])
                                    - Decimal(before["batch_occupied_usd"])
                                ),
                            },
                        )
                        completed.append(key)
                        print(
                            json.dumps(
                                {
                                    "completed": key,
                                    "steps": step,
                                    "reads": [r["name"] for r in tool_reads],
                                    "batch_usd": after["batch_occupied_usd"],
                                }
                            ),
                            flush=True,
                        )
                        break
                    else:
                        raise ResearchStop("episode_step_limit")
        outcome = {"status": "completed"}
    except ResearchStop as error:
        outcome = {"status": "stopped", "reason": str(error)}
    except TimeoutError:
        outcome = {"status": "stopped", "reason": "batch_deadline"}
    except Exception as error:  # noqa: BLE001 -- terminal journal, no retry or unsafe error text
        outcome = {"status": "failed", "error_type": type(error).__name__}
    finally:
        save_new(
            OUTPUT / "result.json",
            {
                **outcome,
                "last_phase": guard.phase,
                "completed": completed,
                "usage": guard.summary(),
            },
        )
    print(
        json.dumps({**outcome, "completed": len(completed), "usage": guard.summary()}),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run"))
    arguments = parser.parse_args()
    if arguments.action == "prepare":
        prepare()
    else:
        # Load only the key; never print, serialize or upload dotenv contents.
        from dotenv import dotenv_values

        key = os.environ.get("OPENAI_API_KEY") or dotenv_values(
            ROOT / "apps/api/.env"
        ).get("OPENAI_API_KEY")
        if not key:
            raise SystemExit("OPENAI_API_KEY missing; no paid request sent")
        os.environ["OPENAI_API_KEY"] = key
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as loop:
            loop.run(execute())
