"""Bounded warehouse artifact-use pilot; no product writes or native compaction."""

import argparse
import ast
import asyncio
import hashlib
import importlib.util
import json
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "memory-added-value-2026-10-04"
sys.path.insert(0, str(SHARED))

import experiment as shared
import httpx2
from caliburn.adapters.response_serialization import restore_response
from fixtures import capture_batches, reader_context, validate_references
from openai import APIError
from pydantic import BaseModel, ConfigDict, Field
from support import Budget, prepare_materials, read_snapshot

PRIOR = Decimal("1.136057105")
PROMPTS = {
    "corrections": "請用已完成訪談核對進貨驗收、退貨核對及庫存帳齡表的工作事實，整理正確時點、比例範圍與責任。也比較設備異常比例的適用範圍，及帳齡表更正是否影響收貨異常週報。來源有早期說法及後續補充，請分清適用範圍，交付有依據的核對結果。",
    "boundaries": "請根據已完成訪談，核對產品召回、休假交接及單據保存要求：本人負責到哪裡、哪些決定不屬於本人。另指出冷藏退貨的溫度合格門檻及文件保存年限是否已足以寫成數字要求；不確定時給出適當追問。不把每次事件另造永久職責。",
}
READER_SUPPLEMENT = """

本次是隔離研究的工作事實核對，不編輯JD、不啟動Memory整理、不繼續一般訪談。
App提供工作資料與一則相同的近期顧問答覆，舊原話1至105可按需回查；本次問題不是新的工作事實。
本次若提供完整工作摘要，可先使用摘要；有具體缺口、指涉不明或衝突才回查必要原話。
若提供Memory導覽，依既有按需閱讀原則定位理解／情境，已讀正文充分即停止下查。
沒有提供的能力不要呼叫。依據足以回答時，不為重複驗證而讀遍原話；仍有未知就如實保留。
最後呼叫submit_recall一次，完整回答本題及必要追問，引用實際支持結論的可用來源。
可以直接引用已讀且足夠的理解或情境；單層摘要中的原話序號也可作來源定位，不必為引用而重讀。
這是研究回答，不宣稱已正式保存。不要另交JD修改或內部推理。
"""


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: str = Field(
        min_length=1, description="完整核對本題的工作事實，含適用範圍與必要細節。"
    )
    references: list[shared.Reference] = Field(
        min_length=1, description="實際支持回答的正式訪談序號或已讀Memory標題。"
    )
    questions: list[str] = Field(
        description="影響判斷但尚未確定的具體追問；已知資訊不重問。"
    )


def submit_tool():
    return {
        "type": "function",
        "name": "submit_recall",
        "strict": True,
        "description": "提交本题的工作事實核對結果、來源與必要追問，只收集研究回答，不寫入產品。",
        "parameters": Answer.model_json_schema(),
    }


def prepare(run_dir):
    inspection = json.loads(
        (HERE / "material-inspection.json").read_text(encoding="utf-8")
    )
    for item in inspection["source_files"]:
        if (
            hashlib.sha256((shared.ROOT / item["path"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("inspected_source_changed")
    product = json.loads(
        (shared.SOURCE / "product-052.json").read_text(encoding="utf-8")
    )
    memory = json.loads(
        (shared.SOURCE / "memory-e052.json").read_text(encoding="utf-8")
    )
    all_material = prepare_materials(product, memory)
    material = {
        key: all_material[key] for key in ("messages", "maps", "objects", "snapshot")
    }
    batches = capture_batches(material["messages"])
    policy_dir = HERE.parent / "memory-reading-policy-2026-10-04/live-01"
    policy = json.loads((policy_dir / "instructions.json").read_text(encoding="utf-8"))[
        "candidate"
    ]
    reader = (
        policy.split("\n\n本次是隔離研究中的 JD 核對提案", 1)[0] + READER_SUPPLEMENT
    )
    old_script = HERE.parent / "long-interview-memory-2026-10-04/experiment.py"
    tree = ast.parse(old_script.read_text(encoding="utf-8"))
    flat = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "FLAT_INSTRUCTIONS"
            for t in node.targets
        )
    )
    original_cases = json.loads(
        (policy_dir / "cases.json").read_text(encoding="utf-8")
    )["cases"]
    cases = [
        {
            "case_id": c["case_id"],
            "prompt": PROMPTS[c["case_id"]],
            "criteria": [row for row in c["criteria"] if row[0] != "locality"],
        }
        for c in original_cases
    ]
    if sum(len(c["criteria"]) for c in cases) != 19:
        raise ValueError("unexpected_grading_scope")
    schedule = [
        {"case_id": case["case_id"], "arm": arm, "repeat": repeat}
        for repeat in (1, 2)
        for case in cases
        for arm in (("memory", "flat") if repeat == 1 else ("flat", "memory"))
    ]
    tools = {
        arm: [
            *shared.memory_read_definitions(
                names=shared.READ_NAMES if arm == "memory" else ("read_interview",)
            ),
            submit_tool(),
        ]
        for arm in ("memory", "flat")
    }
    sources = [
        HERE / "README.md",
        HERE / "material-inspection.json",
        HERE / "study.py",
        HERE / "fixtures.py",
        HERE / "test_fixtures.py",
        SHARED / "experiment.py",
        SHARED / "support.py",
        policy_dir / "instructions.json",
        policy_dir / "cases.json",
        old_script,
        HERE.parent / "design-comparisons-2026-10-04/provider_observations.py",
        shared.ROOT / "apps/api/src/caliburn/adapters/openai_responses.py",
        shared.ROOT / "apps/api/src/caliburn/adapters/response_serialization.py",
    ]
    manifest = {
        "prepared_at": datetime.now(UTC).isoformat(),
        "kind": "artifact-use-pilot-not-capacity-test",
        "authorization": "User approved added US$0.10/20 minutes, including capture/count/read/failures; cumulative US$2.",
        "model": shared.MODEL,
        "effort": "high",
        "max_output_tokens": shared.MAX_OUTPUT,
        "max_estimated_usd": "0.10",
        "max_seconds": 1200,
        "prior_occupied_usd": str(PRIOR),
        "cumulative_limit_usd": "2.00",
        "schedule": schedule,
        "capture_boundaries": [24, 56, 88, 104],
        "grading_items": 19,
        "max_generations": 32,
        "max_outbound_calls": 64,
        "max_reader_steps": 6,
        "sdk_version": shared.version("openai"),
        "head": shared.subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=shared.ROOT, text=True
        ).strip(),
        "pricing_basis": shared.model_profile(shared.MODEL).pricing.cost_basis,
        "source_sha256": {
            str(p.relative_to(shared.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sources
        },
        "reader_prompt_sha256": shared.fingerprint(reader),
        "flat_prompt_sha256": shared.fingerprint(flat),
        "tools_sha256": {
            arm: shared.fingerprint(value) for arm, value in tools.items()
        },
    }
    for name, value in (
        ("materials", material),
        ("cases", cases),
        ("instructions", {"reader": reader, "flat": flat}),
        ("manifest", manifest),
    ):
        shared.dump(run_dir / f"{name}.json", value)
    for arm, value in tools.items():
        shared.dump(run_dir / f"tools-{arm}.json", value)
    shared.dump(run_dir / "capture-source-batches.json", batches)
    (run_dir / "executed-protocol.md").write_text(
        (HERE / "README.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return material, cases, batches, reader, flat, tools, manifest


async def run(run_dir, prepared, continuation=None):
    material, cases, batches, reader, flat_prompt, tools, manifest = prepared
    spec = importlib.util.spec_from_file_location(
        "observations",
        HERE.parent / "design-comparisons-2026-10-04/provider_observations.py",
    )
    observations = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observations)
    budget = Budget(max_usd=Decimal("0.10"), max_seconds=1200)
    rates = shared.model_profile(shared.MODEL).pricing
    headers, results, capture_usage = {}, [], []
    generations = 0
    current = {}
    last_finished = time.monotonic()
    active = None
    failure = None
    failed_usage = []
    if continuation is not None:
        old = json.loads((continuation / "result.json").read_text(encoding="utf-8"))
        if (
            old["failure"]["reason"] != "response_incomplete"
            or len(old["capture_usage"]) != 3
            or old["results"]
        ):
            raise ValueError("unexpected_continuation_state")
        first = None
        for line in (continuation / "trace.jsonl").open(encoding="utf-8"):
            item = json.loads(line)
            if item["event"] == "paid_phase_started":
                first = datetime.fromisoformat(item["at"])
            if (
                item["event"] == "generation_response"
                and item["response"]["status"] != "completed"
            ):
                cost = rates.estimate_response_cost(restore_response(item["response"]))
                failed_usage.append(
                    {"usage": item["response"]["usage"], "estimated_usd": str(cost)}
                )
        elapsed = (datetime.now(UTC) - first).total_seconds()
        if not 0 <= elapsed < 1200:
            raise ValueError("original_time_limit_before_continuation")
        budget.started -= elapsed
        budget.occupied = Decimal(old["occupied_usd"])
        budget.pending = {k: Decimal(v) for k, v in old["pending"].items()}
        budget.outbound_calls = old["outbound_calls"]
        generations = old["generation_calls"]
        capture_usage.extend(old["capture_usage"])

    def event(value):
        shared.append(
            run_dir / "trace.jsonl",
            {"at": datetime.now(UTC).isoformat(), **current, **value},
        )

    async def response_hook(response):
        nonlocal headers
        headers = observations.rate_headers(response.headers)
        event(
            {
                "event": "http_response",
                "path": response.request.url.path,
                "status": response.status_code,
                "rate_headers": headers,
            }
        )

    async def generate(client, window, instructions, definitions, key, max_output=8192):
        nonlocal generations, last_finished
        if generations >= 32:
            raise ValueError("generation_limit")
        # Same conservative pacing as the prior experiments; waits consume the one clock.
        delay = observations.admission_delay(
            headers, time.monotonic() - last_finished, 25000
        )
        if time.monotonic() - budget.started + delay >= budget.max_seconds:
            raise ValueError("time_limit_before_wait")
        if delay:
            event({"event": "rate_wait", "seconds": delay})
            await asyncio.sleep(delay)
        request = shared.ResponseRequest(
            model=shared.MODEL,
            instructions=instructions,
            input_items=window,
            tools=definitions,
            reasoning_effort="high",
            max_output_tokens=max_output,
        )
        count_key = f"count-continuation-{key}" if continuation else f"count-{key}"
        budget.reserve(count_key, Decimal("0.0001"))
        event(
            {
                "event": "count_request",
                "request": shared.public_document(request.count_payload()),
            }
        )
        counted = await shared.count_response_input(client, request)
        event({"event": "count_response", "input_tokens": counted.input_tokens})
        if (
            type(counted.input_tokens) is not int
            or not 0 < counted.input_tokens < 128000
        ):
            raise ValueError("unexpected_input_capacity")
        budget.reserve(
            key,
            rates.reserve_response_cost(
                input_tokens=counted.input_tokens, max_output_tokens=max_output
            ),
        )
        generations += 1
        event(
            {
                "event": "generation_request",
                "request": shared.public_document(request.create_payload()),
            }
        )
        started = time.monotonic()
        response = await shared.create_response(client, request)
        last_finished = time.monotonic()
        event(
            {
                "event": "generation_response",
                "response": shared.public_document(shared.snapshot_response(response)),
                "seconds": last_finished - started,
            }
        )
        estimated = rates.estimate_response_cost(response)
        if estimated is None:
            raise ValueError("unknown_provider_usage")
        budget.settle(key, estimated)
        usage = {
            "usage": response.usage.model_dump(mode="json"),
            "estimated_usd": str(estimated),
            "seconds": last_finished - started,
            "counted_input_tokens": counted.input_tokens,
        }
        if response.status != "completed":
            raise ValueError(f"response_{response.status}")
        return response, usage

    event({"event": "paid_phase_started", "limit_seconds": 1200})
    try:
        async with (
            httpx2.AsyncClient(
                follow_redirects=False, event_hooks={"response": [response_hook]}
            ) as transport,
            shared.create_responses_client(
                api_key=shared.read_openai_api_key(shared.ROOT / "apps/api/.env"),
                timeout_seconds=120,
                http_client=transport,
            ) as client,
        ):
            summary = (
                ""
                if continuation is None
                else (continuation / "flat-summary-3.md")
                .read_text(encoding="utf-8")
                .strip()
            )
            for n, source in enumerate(batches, 1):
                if continuation is not None and n <= 3:
                    continue
                current = {"phase": "flat_capture", "batch": n}
                window = [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "previous_work_summary": summary,
                                "historical_interview": source,
                            },
                            ensure_ascii=False,
                        ),
                    }
                ]
                shared.dump(run_dir / f"capture-input-{n}.json", window)
                response, usage = await generate(
                    client,
                    window,
                    flat_prompt,
                    [],
                    f"capture-{n}",
                    max_output=16384 if continuation else 8192,
                )
                capture_usage.append({"batch": n, **usage})
                summary = response.output_text.strip()
                if not summary or any(
                    item.type == "function_call" for item in response.output
                ):
                    raise ValueError("invalid_flat_capture")
                (run_dir / f"flat-summary-{n}.md").write_text(
                    summary + "\n", encoding="utf-8"
                )
                print(
                    json.dumps(
                        {
                            "capture_batch": n,
                            "characters": len(summary),
                            "occupied_usd": str(budget.occupied),
                        }
                    ),
                    flush=True,
                )
            case_by_id = {case["case_id"]: case for case in cases}
            for scheduled in manifest["schedule"]:
                current = {"phase": "reader", **scheduled}
                arm = current["arm"]
                cell_id = f"{current['case_id']}-{arm}-{current['repeat']}"
                window = reader_context(
                    material, arm, case_by_id[current["case_id"]]["prompt"], summary
                )
                shared.dump(run_dir / f"initial-{cell_id}.json", window)
                cell = {
                    **scheduled,
                    "cell_id": cell_id,
                    "status": "step_limit",
                    "reads": [],
                    "usage": [],
                    "answer": None,
                }
                active = cell
                cell_start = time.monotonic()
                for step in range(1, 7):
                    current["step"] = step
                    response, usage = await generate(
                        client, window, reader, tools[arm], f"{cell_id}-{step}"
                    )
                    cell["usage"].append(usage)
                    window.extend(shared.response_input_items(response))
                    calls = [
                        item for item in response.output if item.type == "function_call"
                    ]
                    if not calls or len(calls) > 24:
                        raise ValueError("missing_or_excess_calls")
                    submitted = False
                    for call in calls:
                        arguments = json.loads(call.arguments)
                        if call.name == "submit_recall":
                            if len(calls) != 1:
                                raise ValueError("mixed_submission")
                            answer = Answer.model_validate(arguments).model_dump(
                                mode="json"
                            )
                            output = validate_references(
                                material, arm, answer["references"]
                            )
                            if output["status"] == "accepted":
                                cell.update(answer=answer, status="completed")
                                submitted = True
                        elif call.name in {
                            t["name"]
                            for t in tools[arm]
                            if t["name"] != "submit_recall"
                        }:
                            try:
                                output = read_snapshot(
                                    material,
                                    "raw_memory" if arm == "memory" else "raw",
                                    call.name,
                                    arguments,
                                )
                            except (ValueError, KeyError):
                                output = {
                                    "status": "rejected",
                                    "code": "invalid_selection",
                                    "next_action": "使用導覽精確標題或1至105的正式序號。",
                                }
                            cell["reads"].append(
                                {
                                    "step": step,
                                    "name": call.name,
                                    "arguments": arguments,
                                    "result_characters": len(
                                        json.dumps(output, ensure_ascii=False)
                                    ),
                                }
                            )
                        else:
                            raise ValueError("unavailable_tool")
                        item = {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": json.dumps(output, ensure_ascii=False),
                        }
                        window.append(item)
                        event(
                            {
                                "event": "tool_result",
                                "name": call.name,
                                "arguments": arguments,
                                "item": item,
                            }
                        )
                    if submitted:
                        break
                cell["seconds"] = time.monotonic() - cell_start
                results.append(cell)
                shared.dump(run_dir / f"result-{cell_id}.json", cell)
                active = None
                print(
                    json.dumps(
                        {
                            "cell_id": cell_id,
                            "status": cell["status"],
                            "calls": len(cell["usage"]),
                            "reads": len(cell["reads"]),
                            "occupied_usd": str(budget.occupied),
                        }
                    ),
                    flush=True,
                )
    except (
        APIError,
        httpx2.HTTPError,
        ValueError,
        KeyError,
        TypeError,
        asyncio.CancelledError,
    ) as error:
        if active is not None:
            active["status"] = "stopped"
            results.append(active)
            shared.dump(run_dir / f"result-{active['cell_id']}.json", active)
        failure = {
            "type": type(error).__name__,
            "reason": str(error)
            if isinstance(error, ValueError)
            else "provider_or_transport_failure",
            "current": current,
        }
        shared.dump(run_dir / "failure.json", failure)
        event({"event": "stopped", **failure})
    finally:
        completed_ids = {cell["cell_id"] for cell in results}
        not_run = [
            scheduled
            for scheduled in manifest["schedule"]
            if f"{scheduled['case_id']}-{scheduled['arm']}-{scheduled['repeat']}"
            not in completed_ids
        ]
        final = {
            "status": "completed"
            if len(results) == 8
            and all(cell["status"] == "completed" for cell in results)
            else "incomplete",
            "failure": failure,
            "not_run": not_run,
            "results": results,
            "capture_usage": capture_usage,
            "failed_usage": failed_usage,
            "generation_calls": generations,
            "outbound_calls": budget.outbound_calls,
            "occupied_usd": str(budget.occupied),
            "cumulative_occupied_usd": str(PRIOR + budget.occupied),
            "pending": {key: str(value) for key, value in budget.pending.items()},
            "seconds": time.monotonic() - budget.started,
        }
        shared.dump(run_dir / "result.json", final)
    return final


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--continue-from")
    args = parser.parse_args()
    if Path(args.run).name != args.run or args.run in (".", ".."):
        parser.error("A new plain run name is required")
    run_dir = HERE / args.run
    run_dir.mkdir(exist_ok=False)
    prepared = prepare(run_dir)
    continuation = None
    if args.continue_from:
        if args.continue_from != "live-01" or not args.live:
            parser.error("Only the stopped live-01 capture may continue")
        continuation = HERE / args.continue_from
        manifest = prepared[-1]
        original = json.loads(
            (continuation / "manifest.json").read_text(encoding="utf-8")
        )
        for key in (
            "reader_prompt_sha256",
            "flat_prompt_sha256",
            "tools_sha256",
            "schedule",
        ):
            if original[key] != manifest[key]:
                raise ValueError("changed_reader_or_capture_protocol")
        manifest.update(
            continuation_of="live-01",
            max_capture_output_tokens=16384,
            continuation_note="Only capture output reserve increased; original clock, cost and failures retained. Readers still 8192.",
        )
        shared.dump(run_dir / "manifest.json", manifest)
    if not args.live:
        shared.dump(
            run_dir / "offline-check.json",
            {
                "provider_calls": 0,
                "capture_batches": 4,
                "schedule_cells": 8,
                "grading_items": 19,
            },
        )
        print("Prepared pilot; zero provider calls.")
        return
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        result = runner.run(
            asyncio.wait_for(run(run_dir, prepared, continuation), timeout=1200)
        )
    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
