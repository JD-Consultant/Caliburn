"""Paired A/tool-description study; immutable Memory, no product or B2 writes."""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import study as pilot
from caliburn.agents.job_consultant.instructions import CONSULTANT_INSTRUCTIONS
from fixtures import reader_context, validate_references
from openai import APIError
from support import Budget, read_snapshot

shared = pilot.shared
HERE = Path(__file__).resolve().parent
CONTROL = HERE / "live-02"
PRIOR = Decimal("1.175334675")
LIMIT_USD = Decimal("0.10")
LIMIT_SECONDS = 1200


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def without_descriptions(value):
    if isinstance(value, list):
        return [without_descriptions(item) for item in value]
    if isinstance(value, dict):
        return {
            key: without_descriptions(item)
            for key, item in value.items()
            if key != "description"
        }
    return value


def validate_frozen_inputs(frozen):
    for key, fingerprint in frozen["manifest"]["input_sha256"].items():
        if shared.fingerprint(frozen[key]) != fingerprint:
            # Give schema drift a distinct diagnosis, rather than silently re-freezing it.
            if key == "tools" and without_descriptions(
                frozen["tools"]["control"]
            ) != without_descriptions(frozen["tools"]["candidate"]):
                raise ValueError("tool_structure_changed")
            raise ValueError("frozen_input_changed")
    if without_descriptions(frozen["tools"]["control"]) != without_descriptions(
        frozen["tools"]["candidate"]
    ):
        raise ValueError("tool_structure_changed")
    for relative, expected in frozen["manifest"]["source_sha256"].items():
        if (
            hashlib.sha256((shared.ROOT / relative).read_bytes()).hexdigest()
            != expected
        ):
            raise ValueError("source_changed_before_live")


def prepare_inputs():
    material, cases = load(CONTROL / "materials.json"), load(CONTROL / "cases.json")
    control_tools = load(CONTROL / "tools-memory.json")
    control_prompt = load(CONTROL / "instructions.json")["reader"]
    tools = {
        "control": control_tools,
        "candidate": [
            *shared.memory_read_definitions(names=shared.READ_NAMES),
            control_tools[-1],
        ],
    }
    sources = [
        HERE / "reading_policy.py",
        HERE / "test_reading_policy.py",
        HERE / "reading-policy-update.md",
        HERE / "study.py",
        HERE / "fixtures.py",
        pilot.SHARED / "experiment.py",
        pilot.SHARED / "support.py",
        HERE.parent / "design-comparisons-2026-10-04/provider_observations.py",
        *[
            CONTROL / name
            for name in (
                "materials.json",
                "cases.json",
                "instructions.json",
                "tools-memory.json",
            )
        ],
        shared.ROOT / "apps/api/src/caliburn/agents/job_consultant/instructions.py",
        shared.ROOT
        / "apps/api/src/caliburn/agents/work_understanding_analyst/instructions.py",
        shared.ROOT / "apps/api/src/caliburn/transport/model_tools/memory_reads.py",
        *[
            shared.ROOT / "apps/api/contracts/tools" / name
            for name in (
                "memory-map-arguments.schema.json",
                "read-memory-object-arguments.schema.json",
                "read-interview-arguments.schema.json",
            )
        ],
    ]
    frozen = {
        "materials": material,
        "cases": cases,
        "instructions": {
            "control": control_prompt,
            "candidate": CONSULTANT_INSTRUCTIONS + pilot.READER_SUPPLEMENT,
        },
        "tools": tools,
    }
    frozen["manifest"] = {
        "prepared_at": datetime.now(UTC).isoformat(),
        "kind": "paired-a-and-memory-tool-description-reading-policy",
        "authorization": "US$0.10 / 20 minutes, within cumulative US$2; user confirmed 2026-10-05.",
        "model": shared.MODEL,
        "effort": "high",
        "max_output_tokens": 8192,
        "max_estimated_usd": str(LIMIT_USD),
        "max_seconds": LIMIT_SECONDS,
        "prior_occupied_usd": str(PRIOR),
        "cumulative_limit_usd": "2.00",
        "grading_items": sum(len(case["criteria"]) for case in cases),
        "schedule": [
            {"case_id": case["case_id"], "arm": arm, "repeat": repeat}
            for repeat in (1, 2)
            for case in cases
            for arm in (
                ("control", "candidate") if repeat == 1 else ("candidate", "control")
            )
        ],
        "max_reader_steps": 6,
        "max_generations": 32,
        "max_outbound_calls": 64,
        "sdk_version": shared.version("openai"),
        "head": shared.subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=shared.ROOT, text=True
        ).strip(),
        "pricing_basis": shared.model_profile(shared.MODEL).pricing.cost_basis,
        "source_sha256": {
            str(path.relative_to(shared.ROOT)): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sources
        },
        "input_sha256": {
            key: shared.fingerprint(value) for key, value in frozen.items()
        },
    }
    validate_frozen_inputs(frozen)
    return frozen


async def run(run_dir, frozen):
    validate_frozen_inputs(frozen)
    if (run_dir / "trace.jsonl").exists() or (run_dir / "result.json").exists():
        raise ValueError("paid_run_already_started")
    spec = importlib.util.spec_from_file_location(
        "observations",
        HERE.parent / "design-comparisons-2026-10-04/provider_observations.py",
    )
    observations = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observations)
    budget = Budget(max_usd=LIMIT_USD, max_seconds=LIMIT_SECONDS)
    rates = shared.model_profile(shared.MODEL).pricing
    headers, results, current, failed_usage = {}, [], {}, []
    generations, failure, active = 0, None, None
    last_finished = time.monotonic()

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

    async def generate(client, window, key):
        nonlocal generations, last_finished
        if generations >= 32:
            raise ValueError("generation_limit")
        delay = observations.admission_delay(
            headers, time.monotonic() - last_finished, 25000
        )
        if time.monotonic() - budget.started + delay >= LIMIT_SECONDS:
            raise ValueError("time_limit_before_wait")
        if delay:
            event({"event": "rate_wait", "seconds": delay})
            await asyncio.sleep(delay)
        request = shared.ResponseRequest(
            model=shared.MODEL,
            instructions=frozen["instructions"][current["arm"]],
            input_items=window,
            tools=frozen["tools"][current["arm"]],
            reasoning_effort="high",
            max_output_tokens=8192,
        )
        count_key = f"count-{key}"
        budget.reserve(count_key, Decimal("0.0001"))
        event(
            {
                "event": "count_request",
                "request": shared.public_document(request.count_payload()),
            }
        )
        async with asyncio.timeout(
            max(0.001, LIMIT_SECONDS - (time.monotonic() - budget.started))
        ):
            counted = await shared.count_response_input(client, request)
        event({"event": "count_response", "input_tokens": counted.input_tokens})
        if (
            type(counted.input_tokens) is not int
            or not 0 < counted.input_tokens < 128000
        ):
            raise ValueError("unexpected_input_capacity")
        reserve = rates.reserve_response_cost(
            input_tokens=counted.input_tokens, max_output_tokens=8192
        )
        if PRIOR + budget.occupied + reserve > Decimal("2.00"):
            raise ValueError("cumulative_budget_limit")
        budget.reserve(key, reserve)
        generations += 1
        event(
            {
                "event": "generation_request",
                "request": shared.public_document(request.create_payload()),
            }
        )
        started = time.monotonic()
        async with asyncio.timeout(
            max(0.001, LIMIT_SECONDS - (started - budget.started))
        ):
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
            failed_usage.append(usage)
            raise ValueError(f"response_{response.status}")
        return response, usage

    event({"event": "paid_phase_started", "limit_seconds": LIMIT_SECONDS})
    try:
        async with (
            pilot.httpx2.AsyncClient(
                follow_redirects=False, event_hooks={"response": [response_hook]}
            ) as transport,
            shared.create_responses_client(
                api_key=shared.read_openai_api_key(shared.ROOT / "apps/api/.env"),
                timeout_seconds=120,
                http_client=transport,
            ) as client,
        ):
            case_by_id = {case["case_id"]: case for case in frozen["cases"]}
            for scheduled in frozen["manifest"]["schedule"]:
                current = {"phase": "reader", **scheduled}
                cell_id = f"{current['case_id']}-{current['arm']}-{current['repeat']}"
                window = reader_context(
                    frozen["materials"],
                    "memory",
                    case_by_id[current["case_id"]]["prompt"],
                )
                shared.dump(run_dir / f"initial-{cell_id}.json", window)
                active = {
                    **scheduled,
                    "cell_id": cell_id,
                    "status": "step_limit",
                    "reads": [],
                    "usage": [],
                    "answer": None,
                }
                cell_started = time.monotonic()
                available = {tool["name"] for tool in frozen["tools"][current["arm"]]}
                for step in range(1, 7):
                    current["step"] = step
                    response, usage = await generate(
                        client, window, f"{cell_id}-{step}"
                    )
                    active["usage"].append(usage)
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
                            answer = pilot.Answer.model_validate(arguments).model_dump(
                                mode="json"
                            )
                            output = validate_references(
                                frozen["materials"], "memory", answer["references"]
                            )
                            if output["status"] == "accepted":
                                active.update(answer=answer, status="completed")
                                submitted = True
                        elif call.name in available:
                            try:
                                output = read_snapshot(
                                    frozen["materials"],
                                    "raw_memory",
                                    call.name,
                                    arguments,
                                )
                            except (ValueError, KeyError):
                                output = {
                                    "status": "rejected",
                                    "code": "invalid_selection",
                                    "next_action": "使用導覽精確標題或1至105的正式序號。",
                                }
                            active["reads"].append(
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
                active["seconds"] = time.monotonic() - cell_started
                results.append(active)
                shared.dump(run_dir / f"result-{cell_id}.json", active)
                print(
                    json.dumps(
                        {
                            "cell_id": cell_id,
                            "status": active["status"],
                            "calls": len(active["usage"]),
                            "reads": len(active["reads"]),
                            "occupied_usd": str(budget.occupied),
                        }
                    ),
                    flush=True,
                )
                active = None
    except (
        APIError,
        pilot.httpx2.HTTPError,
        ValueError,
        KeyError,
        TypeError,
        TimeoutError,
        asyncio.CancelledError,
    ) as error:
        if active is not None:
            active["status"] = "stopped"
            results.append(active)
            shared.dump(run_dir / f"result-{active['cell_id']}.json", active)
        failure = {
            "type": type(error).__name__,
            "reason": str(error)
            if type(error) is ValueError
            else "provider_transport_or_protocol_failure",
            "current": current,
        }
        shared.dump(run_dir / "failure.json", failure)
        event({"event": "stopped", **failure})
    finally:
        attempted = {cell["cell_id"] for cell in results}
        final = {
            "status": "completed"
            if len(results) == 8
            and all(cell["status"] == "completed" for cell in results)
            else "incomplete",
            "failure": failure,
            "results": results,
            "failed_usage": failed_usage,
            "not_run": [
                s
                for s in frozen["manifest"]["schedule"]
                if f"{s['case_id']}-{s['arm']}-{s['repeat']}" not in attempted
            ],
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
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.prepare == args.live:
        parser.error("Choose exactly one phase")
    run_dir = HERE / "reading-policy-01"
    if args.prepare:
        frozen = prepare_inputs()
        run_dir.mkdir(exist_ok=False)
        for key, value in frozen.items():
            shared.dump(run_dir / f"{key}.json", value)
        print(
            json.dumps(
                {
                    "status": "prepared",
                    "cells": 8,
                    "grading_items": frozen["manifest"]["grading_items"],
                }
            )
        )
    else:
        frozen = {
            key: load(run_dir / f"{key}.json")
            for key in ("materials", "cases", "instructions", "tools", "manifest")
        }
        result = asyncio.run(run(run_dir, frozen))
        print(
            json.dumps(
                {
                    key: result[key]
                    for key in (
                        "status",
                        "failure",
                        "occupied_usd",
                        "cumulative_occupied_usd",
                        "seconds",
                    )
                }
            )
        )


if __name__ == "__main__":
    main()
