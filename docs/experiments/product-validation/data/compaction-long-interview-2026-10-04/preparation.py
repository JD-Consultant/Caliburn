"""Prepare synthetic sources and count-only payloads; never run an Agent or compact."""

import argparse
import asyncio
import hashlib
import json
import subprocess
import time
from collections.abc import Awaitable, Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any

from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_models import model_profile
from caliburn.adapters.openai_responses import (
    ResponseRequest,
    count_response_input,
    create_responses_client,
)
from caliburn.agent_execution.request_capacity import (
    MID_WORK_COMPACTION_THRESHOLD_TOKENS,
    allowed_input_tokens,
    require_request_limits,
)
from caliburn.agents.job_consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.agents.job_consultant.tools import consultant_tool_definitions

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent / "AGENTS.md").exists())
MODEL = "gpt-6-luna"
MAX_OUTPUT_TOKENS = 16_384
ARMS = (
    "compaction_hierarchical_memory",
    "compaction_flat_summary",
    "compaction_raw_history",
    "compaction_recent_history",
)
MEMORY_READ_NAMES = {
    "read_work_situation_map",
    "read_work_situation",
    "read_work_understanding_map",
    "read_work_understanding",
}


def load_scenario(path: Path) -> dict[str, Any]:
    scenario: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    events = scenario["events"]
    if not events or not isinstance(scenario["opening"], str) or not scenario["opening"].strip():
        raise ValueError("An opening and nonempty employee events are required")
    identifiers = []
    for event in events:
        if not isinstance(event["employee_text"], str) or not event["employee_text"].strip():
            raise ValueError("Employee text must be a nonempty original utterance")
        identifiers.append(event["event_id"])
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Employee event identifiers must be unique")
    return scenario


def employee_input(scenario: dict[str, Any], event_id: str) -> str:
    for event in scenario["events"]:
        if event["event_id"] == event_id:
            text = event["employee_text"]
            if not isinstance(text, str):
                raise ValueError("Employee text must be an original string")
            return text
    raise ValueError("Unknown employee event")


def validate_grading_sources(scenario: dict[str, Any], grading: dict[str, Any]) -> None:
    positions = {event["event_id"]: index for index, event in enumerate(scenario["events"])}
    for case in grading["cases"]:
        observation = case["observe_after_event_id"]
        for source in [observation, *case["source_event_ids"]]:
            if source not in positions:
                raise ValueError("Unknown grading source event")
            if positions[source] > positions[observation]:
                raise ValueError("A grading source comes from the future")


def preflight_requests(scenario: dict[str, Any]) -> dict[str, ResponseRequest]:
    """Four empty-JD start templates plus an employee-raw-only counterfactual.

    These are not saved product requests or future Agent traces. The opening is an
    App-authored formal source; future consultant replies and tools remain unknown.
    """
    requests = {}
    first_event = scenario["events"][0]["event_id"]
    for arm in ARMS:
        tools = consultant_tool_definitions()
        if arm != "compaction_hierarchical_memory":
            tools = [tool for tool in tools if tool["name"] not in MEMORY_READ_NAMES]
        if arm == "compaction_recent_history":
            tools = [tool for tool in tools if tool["name"] != "read_interview"]
        # Source batches are fixed by this comparison, not by generated notifications.
        tools = [tool for tool in tools if tool["name"] != "request_memory_consolidation"]
        app_data = {
            "data_kind": "consultant_turn_reference",
            "historical_interview": {
                "data_kind": "historical_interview",
                "messages": [
                    {"interview_sequence": 1, "speaker": "app", "text": scenario["opening"]}
                ],
            },
            "interview_read_boundary": {
                "covered_through_sequence": 0,
                "through_sequence": 1,
                "context_sequences": [1],
            },
        }
        if arm == "compaction_hierarchical_memory":
            app_data.update(work_situation_map={"items": []}, work_understanding_map={"items": []})
        elif arm == "compaction_flat_summary":
            app_data["work_summary"] = "尚無已整理摘要。"
        requests[arm] = make_request(
            input_items=[
                {"role": "user", "content": json.dumps(app_data, ensure_ascii=False)},
                {"role": "user", "content": employee_input(scenario, first_event)},
            ],
            tools=tools,
        )
    counterfactual = {
        "data_kind": "synthetic_employee_raw_preload_counterfactual",
        "notice": "容量預檢專用的員工原文集合；不是已完成訪談，不含尚未產生的顧問答覆或工具結果。",
        "employee_messages": [event["employee_text"] for event in scenario["events"]],
    }
    requests["raw_preload_counterfactual"] = make_request(
        input_items=[{"role": "user", "content": json.dumps(counterfactual, ensure_ascii=False)}],
        tools=requests["compaction_raw_history"].count_payload()["tools"],
    )
    return requests


def make_request(*, input_items: list[dict[str, Any]], tools: list[Any]) -> ResponseRequest:
    return ResponseRequest(
        model=MODEL,
        instructions=CONSULTANT_INSTRUCTIONS,
        input_items=input_items,
        tools=tools,
        reasoning_effort="high",
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )


def describe_capacity(input_tokens: int | None, max_output_tokens: int) -> dict[str, Any]:
    if input_tokens is not None and (type(input_tokens) is not int or input_tokens < 0):
        raise ValueError("Input capacity requires a nonnegative integer or unknown")
    request = ResponseRequest(
        model=MODEL,
        instructions="",
        input_items=[],
        tools=[],
        reasoning_effort="high",
        max_output_tokens=max_output_tokens,
    )
    limits = model_profile(MODEL).capacity_limits()
    require_request_limits(request, limits)
    allowed = allowed_input_tokens(request, limits)
    return {
        "allowed_input_tokens": allowed,
        "output_reserve_tokens": max_output_tokens,
        "fits_model": input_tokens <= allowed if input_tokens is not None else None,
        "pre_turn_threshold_reached": input_tokens >= 128_000 if input_tokens is not None else None,
        "complete_step_threshold_reached": (
            input_tokens >= MID_WORK_COMPACTION_THRESHOLD_TOKENS
            if input_tokens is not None
            else None
        ),
    }


async def measure_requests(
    requests: dict[str, ResponseRequest],
    count: Callable[[ResponseRequest], Awaitable[int]],
) -> list[dict[str, Any]]:
    """Count at most five prepared inputs; stop on first error, never guess or retry."""
    if len(requests) > 5:
        raise ValueError("Preflight permits at most five count requests")
    started = time.monotonic()
    results = []
    for name, request in requests.items():
        remaining = 180 - (time.monotonic() - started)
        tokens = None
        row: dict[str, Any] = {"name": name, "status": "count_failed", "input_tokens": None}
        try:
            if remaining <= 0:
                raise TimeoutError("Preflight total time exhausted")
            async with asyncio.timeout(min(60, remaining)):
                tokens = await count(request)
            capacity = describe_capacity(tokens, request.create_payload()["max_output_tokens"])
            if tokens is None:
                raise ValueError("The count endpoint returned no count")
            row.update(status="counted", input_tokens=tokens, capacity=capacity)
        except Exception as error:
            # A diagnostic class/status is enough. Provider error text can contain payloads.
            row["error_type"] = type(error).__name__
            status_code = getattr(error, "status_code", None)
            if type(status_code) is int:
                row["http_status"] = status_code
            row["capacity"] = describe_capacity(None, request.create_payload()["max_output_tokens"])
        results.append(row)
        if row["status"] != "counted":
            break
    return results


def digest(document: Any) -> str:
    encoded = json.dumps(document, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def count_remote_requests(
    requests: dict[str, ResponseRequest], *, api_key: str
) -> list[dict[str, Any]]:
    async with create_responses_client(api_key=api_key, timeout_seconds=60) as client:

        async def count(request: ResponseRequest) -> int:
            response = await count_response_input(client, request)
            return response.input_tokens

        return await measure_requests(requests, count)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="Up to five direct input-token counts; no generation",
    )
    arguments = parser.parse_args()
    # Keep unsuccessful preflights too. A later run must choose a new output path.
    arguments.output.mkdir(parents=True, exist_ok=False)
    scenario = load_scenario(HERE / "employee-scenario.json")
    grading = json.loads((HERE / "grading-cases.json").read_text(encoding="utf-8"))
    validate_grading_sources(scenario, grading)
    requests = preflight_requests(scenario)
    for name, request in requests.items():
        (arguments.output / f"{name}.json").write_text(
            json.dumps(request.count_payload(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    counts = []
    if arguments.count_only:
        counts = asyncio.run(
            count_remote_requests(
                requests,
                api_key=read_openai_api_key(ROOT / "apps/api/.env"),
            )
        )
    source_paths = [
        HERE / "employee-scenario.json",
        HERE / "grading-cases.json",
        Path(__file__).resolve(),
        ROOT / "apps/api/src/caliburn/agents/job_consultant/instructions.py",
        ROOT / "apps/api/src/caliburn/adapters/openai_responses.py",
        ROOT / "apps/api/src/caliburn/adapters/openai_models.py",
    ]
    status = "offline_prepared"
    if arguments.count_only:
        status = (
            "counted"
            if len(counts) == 5 and all(row["status"] == "counted" for row in counts)
            else "count_failed"
        )
    report = {
        "status": status,
        "scope": "Initial templates only; later Agent history and outputs are not generated",
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "file_hashes": {
            str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in source_paths
        },
        "openai_sdk_version": version("openai"),
        "employee_events": len(scenario["events"]),
        "employee_characters": sum(len(event["employee_text"]) for event in scenario["events"]),
        "case_count": len(grading["cases"]),
        "fact_units": sum(len(case["fact_units"]) for case in grading["cases"]),
        "generation_calls": 0,
        "compaction_calls": 0,
        "count_attempts": len(counts),
        "requests": [
            {
                "name": name,
                "payload_sha256": digest(request.count_payload()),
                "tool_names": [tool["name"] for tool in request.count_payload()["tools"]],
            }
            for name, request in requests.items()
        ],
        "counts": counts,
    }
    (arguments.output / "result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "status",
                    "employee_events",
                    "employee_characters",
                    "case_count",
                    "fact_units",
                    "generation_calls",
                    "compaction_calls",
                    "count_attempts",
                    "counts",
                )
            },
            ensure_ascii=False,
        )
    )
    return 1 if report["status"] == "count_failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
