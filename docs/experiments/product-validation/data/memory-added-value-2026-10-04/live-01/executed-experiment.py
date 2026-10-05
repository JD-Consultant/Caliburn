"""Bounded, fresh-context JD review proposals; frozen exported product data only."""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import subprocess
import time
from datetime import UTC, datetime
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from typing import Literal

import httpx2
from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_models import model_profile
from caliburn.adapters.openai_responses import (
    ResponseRequest,
    count_response_input,
    create_response,
    create_responses_client,
)
from caliburn.adapters.response_serialization import (
    response_input_items,
    snapshot_response,
)
from caliburn.agents.job_consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.transport.model_tools.memory_reads import memory_read_definitions
from openai import APIError
from pydantic import BaseModel, ConfigDict, Field
from support import (
    Budget,
    context_for,
    prepare_materials,
    read_snapshot,
    validate_submission,
)

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent / "AGENTS.md").exists())
SOURCE = (
    HERE.parent
    / "compaction-long-interview-2026-10-04/main-03/compaction_hierarchical_memory"
)
MODEL = "gpt-6-luna"
MAX_OUTPUT = 8192
OLD_OCCUPANCY = Decimal("1.000591120")
READ_NAMES = (
    "read_work_situation_map",
    "read_work_situation",
    "read_work_understanding_map",
    "read_work_understanding",
    "read_interview",
)
INSTRUCTIONS = (
    CONSULTANT_INSTRUCTIONS
    + """

本次是隔離研究中的 JD 核對提案，不是真正寫入產品。App 已提供完整歷史訪談和
JD文字，直接使用資料中的精確 target_ref；不需要再找 read_jd。
可按需使用本次列出的讀取工具，不要求固定路徑或閱讀次數；沒有提供的功能不要呼叫。
JD 是待核對文字而非事實來源，原話與已發布Memory可以作依據，但衝突仍須核對語意。
只交付有必要的修改：每個changes對應一個指定欄位的完整新文字及直接依據。
已正確的內容不需重寫，未知不需編造。由 submit_jd_review 一次提交所有必要修改、
有影響的待釐清問題及簡短結論；引用可以使用任何足以支持內容的可見來源，無固定偏好。
不要聲稱已正式保存、不要另造訪談序號；完成提案即可結束，不繼續無关追問。
"""
)


class Reference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["interview", "work_situation", "work_understanding"]
    interview_sequence: int | None = Field(
        ..., description="引用歷史訪談時填正式序號；引用Memory時為null。"
    )
    target_title: str | None = Field(
        ..., description="引用Memory時填可見導覽的精確標題；引用訪談時為null。"
    )


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_ref: str = Field(
        description="JD資料中已提供的精確欄位定位，不猜ID或新增目標。"
    )
    value: str = Field(description="該欄位核對後完整的新文字，保留有效舊內容。")
    references: list[Reference] = Field(
        min_length=1, description="支持本欄位內容的直接來源，跨多則事實可以分別選取。"
    )


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: list[Change] = Field(
        description="只有需要修改的欄位；沒有必要更改時為空陣列。"
    )
    questions: list[str] = Field(
        description="影響工作判斷而尚未確認的問題，已知資訊不要重問。"
    )
    note: str = Field(description="簡短交代已核對範圍與結論，不提供內部推理。")


def submit_tool():
    return {
        "type": "function",
        "name": "submit_jd_review",
        "strict": True,
        "description": "提交本次JD核對的修改提案與待釐清問題；只收集研究結果，不寫入正式JD。",
        "parameters": Proposal.model_json_schema(),
    }


def public_document(value):
    if isinstance(value, list):
        return [public_document(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "encrypted_content":
            if item is not None:
                result["encrypted_length"] = len(item)
                result["encrypted_sha256"] = hashlib.sha256(item.encode()).hexdigest()
        elif not (value.get("type") == "reasoning" and key == "content"):
            result[key] = public_document(item)
    return result


def dump(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def append(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def materials_and_manifest(run_dir):
    product = json.loads((SOURCE / "product-052.json").read_text(encoding="utf-8"))
    memory = json.loads((SOURCE / "memory-e052.json").read_text(encoding="utf-8"))
    material = prepare_materials(product, memory)
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]
    sources = [
        SOURCE / "product-052.json",
        SOURCE / "memory-e052.json",
        HERE / "cases.json",
        HERE / "support.py",
        HERE / "experiment.py",
        ROOT / "apps/api/src/caliburn/agents/job_consultant/instructions.py",
    ]
    schedule = []
    for repeat in (1, 2):
        for case in cases:
            arms = ("raw", "raw_memory") if repeat == 1 else ("raw_memory", "raw")
            schedule.extend(
                {"arm": arm, "repeat": repeat, "case_id": case["case_id"]}
                for arm in arms
            )
    manifest = {
        "prepared_at": datetime.now(UTC).isoformat(),
        "model": MODEL,
        "effort": "high",
        "max_output_tokens": MAX_OUTPUT,
        "max_estimated_usd": "0.20",
        "max_seconds": 1800,
        "prior_occupied_usd": str(OLD_OCCUPANCY),
        "cumulative_limit_usd": "2.00",
        "kind": "fresh-context-review-proposals-not-product-writes",
        "schedule": schedule,
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources
        },
        "instructions_sha256": fingerprint(INSTRUCTIONS),
        "tools_sha256": {},
        "sdk_version": version("openai"),
        "pricing_basis": model_profile(MODEL).pricing.cost_basis,
    }
    for arm in ("raw", "raw_memory"):
        tools = [
            *memory_read_definitions(
                names=READ_NAMES if arm == "raw_memory" else ("read_interview",)
            ),
            submit_tool(),
        ]
        manifest["tools_sha256"][arm] = fingerprint(tools)
        dump(run_dir / f"tools-{arm}.json", tools)
    dump(run_dir / "materials.json", material)
    dump(run_dir / "manifest.json", manifest)
    return material, cases, manifest


async def run(run_dir):
    material, cases, manifest = materials_and_manifest(run_dir)
    case_by_id = {case["case_id"]: case for case in cases}
    module_path = HERE.parent / "design-comparisons-2026-10-04/provider_observations.py"
    spec = importlib.util.spec_from_file_location("provider_observations", module_path)
    observations = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observations)
    budget = Budget()
    rates = model_profile(MODEL).pricing
    headers = {}
    last_finished = time.monotonic()
    generation_calls = 0
    results = []
    current = {}
    active_cell = None

    def event(value):
        append(
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

    event({"event": "paid_phase_started", "limit_seconds": 1800})
    try:
        async with (
            httpx2.AsyncClient(
                follow_redirects=False, event_hooks={"response": [response_hook]}
            ) as transport,
            create_responses_client(
                api_key=read_openai_api_key(ROOT / "apps/api/.env"),
                timeout_seconds=120,
                http_client=transport,
            ) as client,
        ):
            for scheduled in manifest["schedule"]:
                current = dict(scheduled)
                case = case_by_id[current["case_id"]]
                arm = current["arm"]
                cell_id = f"{current['case_id']}-{arm}-{current['repeat']}"
                window = context_for(material, arm, case["prompt"])
                tools = [
                    *memory_read_definitions(
                        names=READ_NAMES if arm == "raw_memory" else ("read_interview",)
                    ),
                    submit_tool(),
                ]
                dump(run_dir / f"initial-{cell_id}.json", window)
                cell = {
                    **current,
                    "cell_id": cell_id,
                    "status": "step_limit",
                    "reads": [],
                    "usage": [],
                    "proposal": None,
                }
                active_cell = cell
                cell_started = time.monotonic()
                for step in range(1, 7):
                    current["step"] = step
                    if generation_calls >= 32:
                        raise ValueError("generation_limit")
                    delay = observations.admission_delay(
                        headers, time.monotonic() - last_finished, 25000
                    )
                    if time.monotonic() - budget.started + delay >= 1800:
                        raise ValueError("time_limit_before_wait")
                    if delay:
                        event({"event": "rate_wait", "seconds": delay})
                        await asyncio.sleep(delay)
                    request = ResponseRequest(
                        model=MODEL,
                        instructions=INSTRUCTIONS,
                        input_items=window,
                        tools=tools,
                        reasoning_effort="high",
                        max_output_tokens=MAX_OUTPUT,
                    )
                    count_key = f"count-{cell_id}-{step}"
                    budget.reserve(count_key, Decimal("0.0001"))
                    event(
                        {
                            "event": "count_request",
                            "request": public_document(request.count_payload()),
                        }
                    )
                    counted = await count_response_input(client, request)
                    event(
                        {
                            "event": "count_response",
                            "input_tokens": counted.input_tokens,
                        }
                    )
                    # Count endpoint gives no generation usage. Its tiny administrative
                    # allowance stays occupied; never declare it free in the ledger.
                    if (
                        type(counted.input_tokens) is not int
                        or not 0 < counted.input_tokens < 128000
                    ):
                        raise ValueError("unexpected_input_capacity")
                    key = f"model-{cell_id}-{step}"
                    budget.reserve(
                        key,
                        rates.reserve_response_cost(
                            input_tokens=counted.input_tokens,
                            max_output_tokens=MAX_OUTPUT,
                        ),
                    )
                    generation_calls += 1
                    event(
                        {
                            "event": "generation_request",
                            "request": public_document(request.create_payload()),
                        }
                    )
                    response_started = time.monotonic()
                    response = await create_response(client, request)
                    last_finished = time.monotonic()
                    event(
                        {
                            "event": "generation_response",
                            "response": public_document(snapshot_response(response)),
                            "seconds": last_finished - response_started,
                        }
                    )
                    estimated = rates.estimate_response_cost(response)
                    if estimated is None:
                        raise ValueError("unknown_provider_usage")
                    budget.settle(key, estimated)
                    cell["usage"].append(
                        {
                            "usage": response.usage.model_dump(mode="json"),
                            "estimated_usd": str(estimated),
                            "seconds": last_finished - response_started,
                        }
                    )
                    if response.status != "completed":
                        cell["status"] = f"response_{response.status}"
                        break
                    window.extend(response_input_items(response))
                    calls = [
                        item for item in response.output if item.type == "function_call"
                    ]
                    if not calls or len(calls) > 24:
                        cell["status"] = "missing_or_excess_calls"
                        break
                    submitted = False
                    for call in calls:
                        args = json.loads(call.arguments)
                        if call.name == "submit_jd_review":
                            if len(calls) != 1:
                                raise ValueError("mixed_submission")
                            proposal = Proposal.model_validate(args).model_dump(
                                mode="json"
                            )
                            output = validate_submission(material, arm, proposal)
                            if output["status"] == "accepted":
                                cell["proposal"] = proposal
                                cell["status"] = "completed"
                                submitted = True
                        elif call.name in {
                            tool["name"]
                            for tool in tools
                            if tool["name"] != "submit_jd_review"
                        }:
                            try:
                                output = read_snapshot(material, arm, call.name, args)
                            except (ValueError, KeyError):
                                output = {
                                    "status": "rejected",
                                    "code": "invalid_selection",
                                    "next_action": "使用導覽的精確標題或1至105之間的正式序號，不猜測。",
                                }
                            cell["reads"].append(
                                {
                                    "step": step,
                                    "name": call.name,
                                    "arguments": args,
                                    "result_characters": len(
                                        json.dumps(output, ensure_ascii=False)
                                    ),
                                }
                            )
                        else:
                            raise ValueError("unavailable_tool")
                        tool_item = {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": json.dumps(output, ensure_ascii=False),
                        }
                        window.append(tool_item)
                        event(
                            {
                                "event": "tool_result",
                                "name": call.name,
                                "arguments": args,
                                "item": tool_item,
                            }
                        )
                    if submitted:
                        break
                cell["seconds"] = time.monotonic() - cell_started
                results.append(cell)
                dump(run_dir / f"result-{cell_id}.json", cell)
                active_cell = None
                print(
                    json.dumps(
                        {
                            "cell_id": cell_id,
                            "status": cell["status"],
                            "model_calls": len(cell["usage"]),
                            "reads": len(cell["reads"]),
                            "occupied_usd": str(budget.occupied),
                        },
                        ensure_ascii=False,
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
        if active_cell is not None:
            active_cell["status"] = "stopped"
            results.append(active_cell)
            dump(run_dir / f"result-{active_cell['cell_id']}.json", active_cell)
        failure = {
            "type": type(error).__name__,
            "reason": str(error)
            if isinstance(error, ValueError)
            else "provider_or_transport_failure",
            "current": current,
        }
        dump(run_dir / "failure.json", failure)
        event({"event": "stopped", **failure})
    finally:
        dump(
            run_dir / "result.json",
            {
                "results": results,
                "generation_calls": generation_calls,
                "outbound_calls": budget.outbound_calls,
                "occupied_usd": str(budget.occupied),
                "cumulative_occupied_usd": str(OLD_OCCUPANCY + budget.occupied),
                "pending": {key: str(value) for key, value in budget.pending.items()},
                "seconds": time.monotonic() - budget.started,
            },
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if Path(args.run).name != args.run or args.run in (".", ".."):
        parser.error("A new plain run name is required")
    run_dir = HERE / args.run
    run_dir.mkdir(exist_ok=False)
    if not args.live:
        material, cases, manifest = materials_and_manifest(run_dir)
        for case in cases:
            for arm in ("raw", "raw_memory"):
                dump(
                    run_dir / f"initial-{case['case_id']}-{arm}.json",
                    context_for(material, arm, case["prompt"]),
                )
        dump(
            run_dir / "offline-check.json",
            {
                "messages": len(material["messages"]),
                "objects": len(material["objects"]),
                "slots": len(material["slots"]),
                "schedule_cells": len(manifest["schedule"]),
                "provider_calls": 0,
            },
        )
        print("Prepared isolated paired inputs; zero provider calls.")
        return
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(asyncio.wait_for(run(run_dir), timeout=1800))


if __name__ == "__main__":
    main()
